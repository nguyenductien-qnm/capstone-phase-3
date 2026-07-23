# Báo Cáo Minh Chứng Bảo Mật - Xác Nhận Guardrails Mandate 9 (Develop Environment)

Tài liệu này ghi nhận kết quả xác minh thực tế (evidence) để chứng minh toàn bộ các chốt chặn bảo mật (Security Guardrails) của hệ thống **TechX Corp** trên môi trường **Develop** vẫn được giữ vững và không bị nới lỏng hoặc cấu hình sai trong suốt quá trình chạy kiểm thử và vận hành **Mandate 9**.

---

## 👥 Thông Tin Thực Hiện (Metadata)

* **Mã Task**: `[md9-sec] Validate private endpoint and TLS guardrails during M9`
* **Nhiệm vụ**: Xác nhận các guardrail bảo mật không bị phá trong quá trình chạy Mandate 9.
* **Người thực hiện chính**: **Mai Phước Khoa**
* **Người duyệt (Reviewer)**: **Hưng Nguyễn Đỗ Khánh**
* **Cộng tác viên**: **Lê Hưng**, **Nguyễn Duy Nghĩa**
* **Ngày thực hiện**: 20/07/2026
* **Hạn hoàn thành**: 18/07/2026 (Đã cập nhật sau kiểm thử ngày 20/07)
* **Trạng thái xác minh**: 🟢 **HOÀN TOÀN ĐẠT** (All Guardrails Confirmed Active)

---

## 📋 1. Tóm Tắt Trạng Thế Guardrail (Executive Summary Checklist)

| Chốt chặn bảo mật (Guardrail) | Nội dung kiểm tra | Trạng thái | Bằng chứng cụ thể (Summary of Proof) |
| :--- | :--- | :---: | :--- |
| **Managed Store (RDS/Valkey/MSK)** | DB/Cache/MQ chỉ dùng IP private, không public ra internet. | 🟢 **Đạt** | Phân giải domain qua DNS công cộng (`8.8.8.8`) trả về duy nhất IP nội bộ VPC (`10.60.0.0/16`). |
| **Ops UI (Grafana/Jaeger/ArgoCD/Locust)** | Các dashboard vận hành không công khai ra internet. | 🟢 **Đạt** | Trên cụm Develop, các dịch vụ này cấu hình dạng `ClusterIP`, không có Ingress, chỉ truy cập an toàn bằng `kubectl port-forward`. |
| **Storefront Separation (Ops Block)** | Đường dẫn quản trị trên domain storefront công cộng phải bị chặn. | 🟢 **Đạt** | Truy cập `/grafana`, `/jaeger`, `/argocd`, `/locust` qua Public LoadBalancer trả về lỗi `404 Not Found` từ Next.js. |
| **TLS/Auth Guardrails** | Kết nối mã hóa TLS và xác thực thông tin không bị gỡ bỏ để debug. | 🟢 **Đạt** | Enforce `sslmode=require` cho Postgres. Valkey sử dụng `auth_token` và bật TLS. MSK sử dụng xác thực SASL/SCRAM. |
| **flagd Central Configuration** | Tính năng Feature Flag (`flagd`) không bị vô hiệu hóa. | 🟢 **Đạt** | Pod `flagd` hoạt động bình thường, nạp cấu hình từ ConfigMap `flagd-config`. |

---

## 🔍 2. Chi Tiết Minh Chứng Thực Tế (Evidence Logs)

### 2.1. Phân Giải DNS Ngoại Mạng (Public DNS Resolution - Negative Proof)
Khi truy cập từ internet thông qua DNS Google (`8.8.8.8`), toàn bộ các endpoint dữ liệu nội bộ chỉ phân giải ra địa chỉ IP riêng tư của AWS VPC (`10.60.x.x`) hoặc bị chặn hoàn toàn.

#### **PostgreSQL RDS Proxy Host**
* **Câu lệnh**:
  ```powershell
  nslookup ecommerce-develop-dev-rds-proxy.proxy-cgduc4gcisdx.us-east-1.rds.amazonaws.com 8.8.8.8
  ```
* **Kết quả**:
  ```text
  Non-authoritative answer:
  Server:  dns.google
  Address:  8.8.8.8

  Name:    vpce-08073b3666ebff45a-cd5tm928.vpce-svc-019250331ee4ee660.us-east-1.vpce.amazonaws.com
  Addresses:  10.60.22.154
              10.60.21.211
  Aliases:  ecommerce-develop-dev-rds-proxy.proxy-cgduc4gcisdx.us-east-1.rds.amazonaws.com
  ```
  *(Minh chứng: Endpoint Proxy ánh xạ trực tiếp vào VPC Endpoint Service với các IP private `10.60.22.154` và `10.60.21.211`).*

#### **PostgreSQL Database Replica**
* **Câu lệnh**:
  ```powershell
  nslookup ecommerce-develop-dev-postgres-replica.cgduc4gcisdx.us-east-1.rds.amazonaws.com 8.8.8.8
  ```
* **Kết quả**:
  ```text
  Non-authoritative answer:
  Server:  dns.google
  Address:  8.8.8.8

  Name:    ecommerce-develop-dev-postgres-replica.cgduc4gcisdx.us-east-1.rds.amazonaws.com
  Address:  10.60.21.114
  ```
  *(Minh chứng: Phân giải duy nhất ra IP private `10.60.21.114` thuộc Data Subnet).*

#### **Valkey Cache Host**
* **Câu lệnh**:
  ```powershell
  nslookup master.ecommerce-develop-dev-valkey.7ystjr.use1.cache.amazonaws.com 8.8.8.8
  ```
* **Kết quả**:
  ```text
  Non-authoritative answer:
  Server:  dns.google
  Address:  8.8.8.8

  Name:    ecommerce-develop-dev-valkey-002.ecommerce-develop-dev-valkey.7ystjr.use1.cache.amazonaws.com
  Address:  10.60.22.247
  Aliases:  master.ecommerce-develop-dev-valkey.7ystjr.use1.cache.amazonaws.com
  ```
  *(Minh chứng: Valkey Cache chỉ sử dụng IP private `10.60.22.247`).*

#### **Amazon MSK Kafka Broker**
* **Câu lệnh**:
  ```powershell
  nslookup b-1.ecommercedevelopdevms.m8n2u6.c16.kafka.us-east-1.amazonaws.com 8.8.8.8
  ```
* **Kết quả**:
  ```text
  Non-authoritative answer:
  Server:  dns.google
  Address:  8.8.8.8

  Name:    b-1.ecommercedevelopdevms.m8n2u6.c16.kafka.us-east-1.amazonaws.com
  Address:  10.60.31.142
  ```
  *(Minh chứng: MSK Broker chỉ sử dụng IP private `10.60.31.142` thuộc Private Subnet).*

---

### 2.2. Bảo Vệ Ops UI Đường Biên (Private Access Protection)
Trên môi trường **Develop**, các tài nguyên quản trị (Grafana, Jaeger, ArgoCD, Locust) được cấu hình thuần dưới dạng `ClusterIP` và **không cấu hình bất kỳ Ingress nào**. 
Điều này triệt tiêu hoàn toàn nguy cơ rò rỉ hoặc truy cập trái phép từ bên ngoài. Để truy cập/debug, vận hành viên bắt buộc phải đi qua cổng bảo mật của Kubernetes thông qua kết nối port-forward (được phân quyền chặt chẽ bằng AWS IAM EKS Access Entry):

```powershell
# Ví dụ port-forward bảo mật từ Client tới EKS Control Plane
kubectl port-forward svc/grafana -n techx-develop 3000:80
kubectl port-forward svc/load-generator -n techx-develop 8089:8089
```

---

### 2.3. Chặn Dò Quét Qua Storefront LoadBalancer (Negative HTTP Routing Proof)
Khi cố gắng truy cập các đường dẫn quản trị nhạy cảm thông qua địa chỉ LoadBalancer công cộng của storefront (`k8s-techxdev-frontend-84edcba41b-35b30c8f5d0b2ce3.elb.us-east-1.amazonaws.com`), Envoy router chặn đứng và chuyển tiếp tới Next.js app để trả về lỗi `404 Not Found`.

* **Câu lệnh**:
  ```powershell
  curl.exe -I -m 5 http://k8s-techxdev-frontend-84edcba41b-35b30c8f5d0b2ce3.elb.us-east-1.amazonaws.com/grafana
  curl.exe -I -m 5 http://k8s-techxdev-frontend-84edcba41b-35b30c8f5d0b2ce3.elb.us-east-1.amazonaws.com/jaeger
  curl.exe -I -m 5 http://k8s-techxdev-frontend-84edcba41b-35b30c8f5d0b2ce3.elb.us-east-1.amazonaws.com/argocd
  curl.exe -I -m 5 http://k8s-techxdev-frontend-84edcba41b-35b30c8f5d0b2ce3.elb.us-east-1.amazonaws.com/locust
  ```
* **Kết quả trả về (ví dụ cho `/grafana`)**:
  ```text
  HTTP/1.1 404 Not Found
  cache-control: private, no-cache, no-store, max-age=0, must-revalidate
  x-powered-by: Next.js
  etag: "byk4zpe8az7j7"
  content-type: text/html; charset=utf-8
  content-length: 9763
  vary: Accept-Encoding
  date: Mon, 20 Jul 2026 14:12:26 GMT
  x-envoy-upstream-service-time: 7
  server: envoy
  ```
  *(Minh chứng: Response Header chứa `server: envoy` và `x-powered-by: Next.js` với status `404 Not Found` chứng tỏ các request đã bị định tuyến trực tiếp vào Next.js frontend thay vì chạm tới hệ thống quản trị).*

---

### 2.4. Trạng Thái Cấu Hình TLS/Auth Không Bị Tắt (TLS/Auth Config Audit)

#### **1. Database Secret Audit (`sslmode=require`)**
* **Câu lệnh**:
  ```powershell
  kubectl get secret db-secret -n techx-develop -o json
  ```
* **Trạng thái phân tích (Đã Redact)**:
  - `catalog-db-conn` (Decoded): `postgresql://db_admin:[REDACTED_PASSWORD]@ecommerce-develop-dev-postgres-replica.cgduc4gcisdx.us-east-1.rds.amazonaws.com:5432/ecommerce_db?sslmode=require`
  - `reviews-db-conn` (Decoded): `postgresql://db_admin:[REDACTED_PASSWORD]@ecommerce-develop-dev-postgres-replica.cgduc4gcisdx.us-east-1.rds.amazonaws.com:5432/ecommerce_db?sslmode=require`
  *(Nhận xét: Tham số `sslmode=require` được áp dụng đầy đủ, đảm bảo mã hóa dữ liệu trên đường truyền).*

#### **2. Valkey Secret Audit (`auth_token`)**
* **Câu lệnh**:
  ```powershell
  kubectl get secret valkey-secret -n techx-develop -o json
  ```
* **Trạng thái phân tích (Đã Redact)**:
  - `address` (Decoded): `master.ecommerce-develop-dev-valkey.7ystjr.use1.cache.amazonaws.com:6379`
  - `auth_token` (Decoded): `[REDACTED_AUTH_TOKEN]`
  *(Nhận xét: Valkey Cache yêu cầu xác thực thông qua AUTH token, không sử dụng anonymous connection).*

#### **3. MSK Secret Audit (Kafka Authentication)**
* **Câu lệnh**:
  ```powershell
  kubectl get secret msk-secret -n techx-develop -o json
  ```
* **Trạng thái phân tích (Đã Redact)**:
  - `username` (Decoded): `msk_user`
  - `password` (Decoded): `[REDACTED_PASSWORD]`
  - `brokers_sasl_scram` (Decoded): `b-1.ecommercedevelopdevms.m8n2u6.c16.kafka.us-east-1.amazonaws.com:9096,b-2.ecommercedevelopdevms.m8n2u6.c16.kafka.us-east-1.amazonaws.com:9096`
  *(Nhận xét: Sử dụng cổng bảo mật 9096 với cơ chế xác thực SASL/SCRAM).*

---

### 2.5. Trạng Thái flagd (flagd Status Audit)
Dịch vụ `flagd` đang chạy bình thường, nạp cấu hình cục bộ an toàn từ ConfigMap `flagd-config`.

* **Câu lệnh**:
  ```powershell
  kubectl get deployment flagd -n techx-develop -o yaml
  ```
* **Trạng thái phân tích**:
  - Command:
    ```yaml
    - /flagd-build
    - start
    - --port
    - "8013"
    - --ofrep-port
    - "8016"
    - --uri
    - file:./etc/flagd/demo.flagd.json
    ```
  *(Minh chứng: flagd đang hoạt động độc lập và an toàn, nạp cấu hình từ ConfigMap của cụm).*

---

## 📖 3. Gap Note & Khác Biệt Giữa Các Môi Trường (Develop vs Production)

> [!IMPORTANT]
> Trong quá trình rà soát, ghi nhận các khác biệt bảo mật giữa môi trường **Develop** và **Production**:
> 1. **OPA Gatekeeper (Constraints)**: Không được cài đặt trên Develop EKS. Các constraints bảo mật cấp runtime (`run-as-non-root`, `psp-capabilities`, v.v.) hiện chỉ được thực thi trên môi trường Production để tối ưu hiệu năng và tính linh hoạt trong quá trình phát triển (Develop).
> 2. **Tailscale VPN**: Không được deploy trên Develop. Thay vào đó, việc bảo vệ đường biên của Develop dựa hoàn toàn vào việc loại bỏ Ingress (không public endpoint) và giao thức `kubectl port-forward` thông qua quyền hạn AWS IAM/EKS Control Plane.
> 3. **flagd Sources**: Môi trường Develop sử dụng ConfigMap local thay vì sync trực tiếp từ remote server của BTC để hỗ trợ kiểm thử tính năng cục bộ.
