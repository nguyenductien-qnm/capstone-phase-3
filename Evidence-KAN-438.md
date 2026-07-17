# Minh Chứng Kiểm Tra Toàn Bộ Vòng Đời Secret (Evidence) - Task CDO-09

Tài liệu này cung cấp các minh chứng thực tế thu thập từ EKS Cluster `ecommerce-dev-eks` trong namespace `techx-tf1` để phục vụ kế hoạch kiểm tra Secret Path trước khi thực hiện xoay vòng Credential (Credential Rotation).

---

## 1. Xác Định Target Store Cho Rotation (Ưu Tiên RDS PostgreSQL & RDS Proxy)

*   **Lựa chọn xoay vòng**: RDS PostgreSQL được chọn làm mục tiêu ưu tiên vì hệ thống sử dụng RDS Proxy hỗ trợ việc thay đổi credential giảm thiểu tối đa downtime.
*   **Xác minh endpoint thực tế của ứng dụng**:
    *   **accounting**: Kết nối qua RDS Proxy (`ecommerce-dev-rds-proxy.proxy-c2x20s086fm5.us-east-1.rds.amazonaws.com`).
    *   **product-catalog**: Kết nối qua RDS Replica Endpoint (`ecommerce-dev-postgres-replica.c2x20s086fm5.us-east-1.rds.amazonaws.com`).
    *   **product-reviews**: Kết nối qua RDS Replica Endpoint (`ecommerce-dev-postgres-replica.c2x20s086fm5.us-east-1.rds.amazonaws.com`).

---

## 2. Bản Đồ Ánh Xạ Secret & Trách Nhiệm (Mapping & Owners)

| AWS Secrets Manager Source | ESO ExternalSecret | K8s Secret Đích | Keys Sử Dụng | App Env/Config Mount | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ecommerce-dev-rds-endpoint` | `db-secret` | `db-secret` | `accounting-db-conn`<br/>`catalog-db-conn`<br/>`reviews-db-conn` | `accounting`: `DB_CONNECTION_STRING`<br/>`product-catalog`: `DB_CONNECTION_STRING`<br/>`product-reviews`: `DB_CONNECTION_STRING` | **Infra Team** (AWS)<br/>**GitOps Team** (ESO) |
| `ecommerce-dev-valkey-secret` | `valkey-secret` | `valkey-secret` | `auth_token`<br/>`address` | `cart`: `VALKEY_AUTH_TOKEN`<br/>`cart`: `VALKEY_ADDRESS` | **Infra Team** (AWS)<br/>**GitOps Team** (ESO) |
| `AmazonMSK_ecommerce-dev-msk-secret`<br/>`ecommerce-dev-msk-endpoint` | `msk-secret` | `msk-secret` | `username`<br/>`password`<br/>`brokers_sasl_scram` | Tương tác nội bộ Kafka | **Infra Team** (AWS)<br/>**GitOps Team** (ESO) |

---

## 3. Trạng Thái External Secrets Operator (ESO)

Kiểm tra trạng thái đồng bộ của các thực thể `ExternalSecret` trên cluster:

```bash
$ kubectl get externalsecret -n techx-tf1
NAME            STORE                 REFRESH INTERVAL   STATUS         READY
db-secret       aws-secrets-manager   1h                 SecretSynced   True
msk-secret      aws-secrets-manager   1h                 SecretSynced   True
valkey-secret   aws-secrets-manager   1h                 SecretSynced   True
```

> [!NOTE]
> Tất cả các `ExternalSecret` đều hiển thị trạng thái **SecretSynced** (Ready: **True**), chứng tỏ ESO đang hoạt động bình thường và kết nối thành công tới AWS Secrets Manager thông qua cơ chế OIDC AssumeRole.

---

## 4. Kiểm Tra Cấu Trúc Các Kubernetes Secret (Không Lộ Plaintext)

Các khóa (keys) bên trong mỗi Secret đích được sinh ra tự động bởi ESO. Minh chứng này xác nhận các keys khớp chính xác với thiết kế mapping:

### a) RDS PostgreSQL Secret (`db-secret`)
```bash
$ kubectl get secret db-secret -n techx-tf1 -o jsonpath='{.data}' | jq 'keys'
[
  "accounting-db-conn",
  "catalog-db-conn",
  "reviews-db-conn"
]
```

### b) Valkey Secret (`valkey-secret`)
```bash
$ kubectl get secret valkey-secret -n techx-tf1 -o jsonpath='{.data}' | jq 'keys'
[
  "address",
  "auth_token"
]
```

### c) MSK (Kafka) Secret (`msk-secret`)
```bash
$ kubectl get secret msk-secret -n techx-tf1 -o jsonpath='{.data}' | jq 'keys'
[
  "brokers_sasl_scram",
  "password",
  "username"
]
```

---

## 5. Xác Minh Cấu Hình Biến Môi Trường Trong Deployment (No Plaintext)

Xác minh các Deployment sử dụng `valueFrom.secretKeyRef` để nạp dữ liệu từ Secret thay vì khai báo plaintext trong Pod Spec:

### a) Product Catalog (`product-catalog`)
```bash
$ kubectl get deployment product-catalog -n techx-tf1 -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="DB_CONNECTION_STRING")]}' | jq
{
  "name": "DB_CONNECTION_STRING",
  "valueFrom": {
    "secretKeyRef": {
      "key": "catalog-db-conn",
      "name": "db-secret"
    }
  }
}
```

### b) Cart (`cart`)
```bash
$ kubectl get deployment cart -n techx-tf1 -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="VALKEY_AUTH_TOKEN")]}' | jq
{
  "name": "VALKEY_AUTH_TOKEN",
  "valueFrom": {
    "secretKeyRef": {
      "key": "auth_token",
      "name": "valkey-secret"
    }
  }
}
```

---

## 6. Minh Chứng Cấu Hình Helm Mapping (values.yaml)

Cấu hình chi tiết về việc mapping các secret key vào ứng dụng được quản lý tập trung thông qua Helm Chart tại file:
*   [values.yaml](file:capstone-phase-3/platform/charts/application/values.yaml)

---

## 7. Xác Nhận Hot-Reload Gap & Quy Trình Rollout An Toàn

> [!WARNING]
> **Hot-Reload Gap Confirmation:**
> K8s không tự động cập nhật các biến môi trường (`env` từ `secretKeyRef`) vào container đang chạy khi Secret nguồn thay đổi. Do đó, sau khi xoay vòng mật khẩu trên AWS Secrets Manager, ứng dụng vẫn sẽ tiếp tục kết nối bằng mật khẩu cũ cho đến khi tiến trình Container bị khởi động lại.

### Quy trình Xoay Vòng Không Downtime (0 Dropped Request):
1.  **Dual-password**: Bật đồng thời cả mật khẩu cũ và mới trên cơ sở dữ liệu (PostgreSQL, Valkey, Kafka).
2.  **ESO Sync**: Chờ ESO đồng bộ mật khẩu mới xuống Kubernetes Secret (hoặc trigger thủ công qua command `kubectl annotate es db-secret force-sync=$(date +%s) -n techx-tf1`).
3.  **Graceful Restart**: Thực hiện cập nhật Pods thông qua cơ chế Rolling Update:
    ```bash
    kubectl rollout restart deployment accounting -n techx-tf1
    kubectl rollout restart deployment product-catalog -n techx-tf1
    kubectl rollout restart deployment product-reviews -n techx-tf1
    kubectl rollout restart deployment cart -n techx-tf1
    ```
4.  **Verification & Cleanup**: Kiểm tra log để đảm bảo toàn bộ pod mới kết nối thành công với mật khẩu mới, sau đó tiến hành vô hiệu hóa mật khẩu cũ.
