# Báo cáo Khảo sát Bảo mật Hệ thống (Security Inventory Report)
**Dự án**: TechX Corp Microservices Platform
**Đội ngũ thực hiện**: Nhóm CDO-05 - Squad A (Security Core)
**Tác giả**: SEC-1 (Tech Lead / Security Specialist)
**Phạm vi rà soát (Scope)**: Terraform, EKS Cluster, RBAC/ServiceAccount, và Container securityContext.

---

## 1. Bảng Tổng hợp Rủi ro Bảo mật (Top Security Risks)

Dưới đây là danh sách các rủi ro bảo mật thuộc phạm vi **Terraform / EKS / RBAC / securityContext** được phát hiện trong codebase:

| ID | Rủi ro Bảo mật | Phân loại | Mức độ | Độ ưu tiên | Bằng chứng (Evidence) |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **SEC-01** | EKS Public API Endpoint không giới hạn nguồn | Terraform / EKS | Trung bình | **P0** | [eks/main.tf#L17](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf#L17) |
| **SEC-02** | Chia sẻ chung một ServiceAccount cho toàn bộ Microservices | RBAC / ServiceAccount | Cao | **P0** | [_objects.tpl#L35](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/techx-corp-chart/templates/_objects.tpl#L35), [serviceaccount.yaml](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/techx-corp-chart/templates/serviceaccount.yaml) |
| **SEC-03** | Thiếu container securityContext cho hơn 10+ Workload | securityContext | Trung bình | **P1** | [values.yaml](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/techx-corp-chart/values.yaml) |
| **SEC-04** | ECR Image Tag Mutability (Dễ bị tấn công ghi đè image) | Terraform / ECR | Thấp | **P1** | [ecr/main.tf#L3](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/ecr/main.tf#L3) |
| **SEC-05** | Tự động gán quyền ClusterAdmin thô cho Access Entries | Terraform / EKS RBAC | Thấp | **P2** | [eks/main.tf#L22-L34](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf#L22-L34) |
| **SEC-06** | Thiếu mã hóa KMS cho Kubernetes Secrets (etcd encryption) | Terraform / EKS | Cao | **P1** | [eks/main.tf](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf) |
| **SEC-07** | Vô hiệu hóa EKS Control Plane Logging (Thiếu audit log) | Terraform / EKS | Trung bình | **P2** | [eks/main.tf](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf) |

---

## 2. Phân tích Chi tiết Lỗ hổng & Rủi ro Bảo mật

### SEC-01: EKS Public API Endpoint không giới hạn nguồn
* **Mô tả**: Endpoint API Server của Kubernetes Cluster được mở công khai ra Internet (`cluster_endpoint_public_access = true`) nhưng không giới hạn dải địa chỉ IP (CIDR blocks) được phép truy cập.
* **Tác động**: API Server phơi ra môi trường công cộng làm tăng bề mặt tấn công. Kẻ tấn công có thể cố gắng brute-force hoặc khai thác các lỗ hổng zero-day trên API Server của Kubernetes để chiếm quyền kiểm soát cụm.
* **Bằng chứng**: [eks/main.tf:L17](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf#L17):
  ```hcl
  cluster_endpoint_public_access = true
  ```

### SEC-02: Chia sẻ chung một ServiceAccount cho toàn bộ Microservices
* **Mô tả**: Template Helm Deployment cấu hình thuộc tính `serviceAccountName` của toàn bộ các component trỏ chung về một ServiceAccount duy nhất được tạo ra ở cấp độ Chart.
* **Tác động**: Vi phạm nghiêm trọng nguyên tắc đặc quyền tối thiểu (Least Privilege). Nếu một pod (ví dụ: `checkout` hoặc `accounting`) cần quyền truy cập AWS (thông qua IRSA) hoặc API Kubernetes để làm việc, toàn bộ các pod khác (bao gồm cả `frontend` mở ra Internet) cũng sẽ được cấp quyền tương đương. Nếu pod `frontend` bị hack, kẻ tấn công dễ dàng chiếm đoạt quyền hạn của ServiceAccount chung này.
* **Bằng chứng**:
  * Định nghĩa nạp ServiceAccount chung trong [_objects.tpl:L35](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/techx-corp-chart/templates/_objects.tpl#L35):
    ```yaml
    serviceAccountName: {{ include "techx-corp.serviceAccountName" .}}
    ```
  * Định nghĩa duy nhất một ServiceAccount trong [serviceaccount.yaml](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/techx-corp-chart/templates/serviceaccount.yaml).

### SEC-03: Thiếu container securityContext cho hơn 10+ Workload
* **Mô tả**: Hơn 10 service trong file `values.yaml` của Helm Chart không khai báo thuộc tính `securityContext` ở container level hoặc `podSecurityContext` ở pod level để giới hạn quyền lực của container.
* **Tác động**: Các container chạy mặc định không bị giới hạn quyền sẽ chạy bằng user `root` (UID 0) của container image. Kẻ tấn công chiếm được container sẽ có quyền root trên container đó và dễ dàng thực hiện leo thang đặc quyền để kiểm soát node máy chủ vật lý.
* **Bằng chứng**: Rà soát file [values.yaml](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/techx-corp-chart/values.yaml) cho thấy các components: `accounting`, `ad`, `cart`, `checkout`, `currency`, `email`, `fraud-detection`, `image-provider`, `load-generator`, `product-catalog`, `product-reviews`, `recommendation`, `shipping`, `flagd`, `llm`, `postgresql` hoàn toàn không có trường cấu hình `securityContext` để cấm chạy dưới quyền root hoặc tắt privilege escalation.

### SEC-04: ECR Image Tag Mutability
* **Mô tả**: Kho chứa Docker image ECR được thiết lập cho phép ghi đè thẻ tag (`image_tag_mutability = "MUTABLE"`).
* **Tác động**: Tạo cơ hội cho các cuộc tấn công chuỗi cung ứng (supply chain attack). Kẻ tấn công có quyền push image có thể đẩy đè một Docker image độc hại hoặc chứa mã lỗi lên một tag cố định đang chạy trên production (ví dụ: `v1.0` hoặc `latest`). Khi Kubernetes scale-out hoặc restart Pod, nó sẽ kéo image độc hại đã bị đè về chạy.
* **Bằng chứng**: [ecr/main.tf:L3](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/ecr/main.tf#L3):
  ```hcl
  image_tag_mutability = "MUTABLE"
  ```

### SEC-05: Tự động gán quyền ClusterAdmin thô cho Access Entries
* **Mô tả**: Terraform EKS module bật cấu hình tự động gán quyền Admin cho người khởi tạo cụm (`enable_cluster_creator_admin_permissions = true`) và gán thẳng Cluster Role Admin (`AmazonEKSClusterAdminPolicy`) cho tất cả Admin ARNs mà không phân quyền chi tiết.
* **Tác động**: Cấp quyền quản trị tối cao (`ClusterAdmin`) quá rộng rãi thay vì phân ranh giới quyền lực (Role-Based Access Control) cho từng nhóm quản trị hạ tầng và vận hành.
* **Bằng chứng**: [eks/main.tf:L22-L34](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf#L22-L34):
  ```hcl
  enable_cluster_creator_admin_permissions = true
  ...
  policy_associations = {
    admin = {
      policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  ```

### SEC-06: Thiếu mã hóa KMS cho Kubernetes Secrets (etcd encryption)
* **Mô tả**: Terraform module cấu hình EKS không định nghĩa cấu hình mã hóa cho các Kubernetes Secrets lưu trữ trong database etcd của Control Plane.
* **Tác động**: Mặc định, các thông tin nhạy cảm (secrets như DB password, API keys) lưu trong etcd chỉ được mã hóa dạng base64 thô. Nếu etcd bị lộ hoặc bị backup trái phép, kẻ tấn công dễ dàng giải mã được toàn bộ secrets của hệ thống.
* **Bằng chứng**: Rà soát file [eks/main.tf](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf) cho thấy module `eks` hoàn toàn thiếu khối cấu hình `cluster_encryption_config` kết hợp với AWS KMS.

### SEC-07: Vô hiệu hóa EKS Control Plane Logging (Thiếu audit log)
* **Mô tả**: Cluster EKS không được cấu hình ghi log cho các thành phần điều khiển (Control Plane components như API server, Audit log, Authenticator...).
* **Tác động**: Thiếu nhật ký kiểm toán (audit trails) khi có sự cố bảo mật hoặc tấn công vào cụm Kubernetes. Đội vận hành sẽ không có bằng chứng lịch sử (ví dụ: ai đã ra lệnh xóa pod, ai đã cấu hình sai...) để điều tra sự cố (Postmortem).
* **Bằng chứng**: File [eks/main.tf](file:///c:/Users/THANH%20TRUNG/Desktop/Phase3/capstone-phase-3/terraform/modules/eks/main.tf) thiếu thuộc tính cấu hình `enabled_cluster_log_types` của module `eks` để đẩy log lên CloudWatch Logs.

---

## 3. Đề xuất Khắc phục & Kế hoạch Hardening (Recommendations)

### Nhóm ưu tiên P0 (Khắc phục ngay trong Tuần 2)
1. **Khắc phục SEC-02 (Cách ly ServiceAccount cho từng Service)**:
   * Sửa đổi Helm Chart templates để tự động hoặc cho phép cấu hình tạo riêng biệt ServiceAccount cho mỗi microservice (ví dụ: `cart-sa`, `checkout-sa`, `payment-sa`...).
   * Thay vì chỉ định một ServiceAccount chung, trỏ `serviceAccountName` của mỗi pod về ServiceAccount riêng tương ứng để đảm bảo phân quyền Least Privilege.

### Nhóm ưu tiên P1 (Khắc phục tiếp theo trong Tuần 2)
2. **Khắc phục SEC-03 (Thiết lập securityContext Baseline)**:
   * Bổ dung cấu hình `securityContext` mặc định cho toàn bộ các workload trong `values.yaml` cấm chạy dưới quyền root (`runAsNonRoot: true`, `allowPrivilegeEscalation: false`).
3. **Khắc phục SEC-06 (Mã hóa KMS cho Secrets)**:
   * Khởi tạo một KMS Key trên AWS thông qua Terraform và cấu hình trường `cluster_encryption_config` của module `eks` để tự động mã hóa tài nguyên `secrets` trong etcd.

### Nhóm ưu tiên P2 (Cải tiến cơ sở hạ tầng ở Tuần 2 - 3)
4. **Khắc phục SEC-01 (Giới hạn IP truy cập Endpoint API EKS)**:
   * Cập nhật Terraform module EKS để giới hạn tham số `public_access_cidrs` về dải IP cụ thể.
5. **Khắc phục SEC-04 (Bảo vệ tính toàn vẹn ECR Image)**:
   * Cập nhật cấu hình ECR repository thành `image_tag_mutability = "IMMUTABLE"` trong file `terraform/modules/ecr/main.tf`.
6. **Khắc phục SEC-07 (Bật EKS Control Plane Logging)**:
    * Thêm cấu hình `enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]` vào module `eks` để đẩy logs lên CloudWatch.

---

## 4. Chi tiết Rà soát Workload Runtime Security (Workload Security Inventory)

Thực hiện rà soát chi tiết tất cả các container, initContainer và sidecar được sinh ra từ Helm Chart ở môi trường sandbox. Kết quả được kiểm tra tự động đối với các tiêu chí: `runAsNonRoot`, `runAsUser`, `allowPrivilegeEscalation`, `capabilities.drop`, và `readOnlyRootFilesystem`.

### 4.1. Bảng Kiểm kê Chi tiết (Workload Inventory Table)

| Workload (Kind/Name) | Container (Type) | Image | nonRoot | User | allowPrivEsc | Drop Caps | readOnlyFS | Status | Chi tiết / Điểm thiếu |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `DaemonSet/otel-collector-agent` | `opentelemetry-collector` (container) | `otel/opentelemetry-collector-contrib:0.151.0` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/accounting` | `accounting` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-accounting` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/accounting` | `wait-for-kafka` (initContainer) | `busybox:latest` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/ad` | `ad` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-ad` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/cart` | `cart` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-cart` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/cart` | `wait-for-valkey-cart` (initContainer) | `busybox:latest` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/checkout` | `checkout` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-checkout` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/checkout` | `wait-for-kafka` (initContainer) | `busybox:latest` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/currency` | `currency` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-currency` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/email` | `email` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-email` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/flagd` | `flagd` (container) | `ghcr.io/open-feature/flagd:v0.12.9` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/flagd` | `init-config` (initContainer) | `busybox` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/fraud-detection` | `fraud-detection` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-fraud-detection` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/fraud-detection` | `wait-for-kafka` (initContainer) | `busybox:latest` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/frontend` | `frontend` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-frontend` | True | 1001 | None | [] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/frontend-proxy` | `frontend-proxy` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-frontend-proxy` | True | 101 | None | [] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/grafana` | `grafana-sc-alerts` (container) | `quay.io/kiwigrid/k8s-sidecar:2.7.1` | True | 472 | False | ['ALL'] | None | **Cần xác minh** | thiếu readOnlyRootFilesystem |
| `Deployment/grafana` | `grafana-sc-dashboard` (container) | `quay.io/kiwigrid/k8s-sidecar:2.7.1` | True | 472 | False | ['ALL'] | None | **Cần xác minh** | thiếu readOnlyRootFilesystem |
| `Deployment/grafana` | `grafana-sc-datasources` (container) | `quay.io/kiwigrid/k8s-sidecar:2.7.1` | True | 472 | False | ['ALL'] | None | **Cần xác minh** | thiếu readOnlyRootFilesystem |
| `Deployment/grafana` | `grafana` (container) | `docker.io/grafana/grafana:13.0.1` | True | 472 | False | ['ALL'] | None | **Cần xác minh** | thiếu readOnlyRootFilesystem |
| `Deployment/image-provider` | `image-provider` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-image-provider` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/jaeger` | `jaeger` (container) | `jaegertracing/jaeger:2.17.0` | None | 10001 | None | [] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/llm` | `llm` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-llm` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/load-generator` | `load-generator` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-load-generator` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/payment` | `payment` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-payment` | True | 1000 | None | [] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/product-catalog` | `product-catalog` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-product-catalog` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/product-reviews` | `product-reviews` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-product-reviews` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/prometheus` | `prometheus-server` (container) | `quay.io/prometheus/prometheus:v3.11.3` | True | 65534 | None | [] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/quote` | `quote` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-quote` | True | 33 | None | [] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/recommendation` | `recommendation` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-recommendation` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `Deployment/shipping` | `shipping` (container) | `804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-shipping` | None | None | None | [] | None | **Fail** | chạy quyền root / thiếu runAsNonRoot, thiếu allowPrivilegeEscalation=false, thiếu drop capabilities (ALL), thiếu readOnlyRootFilesystem |
| `StatefulSet/opensearch` | `opensearch` (container) | `opensearchproject/opensearch:3.6.0` | True | 1000 | None | ['ALL'] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu readOnlyRootFilesystem |
| `StatefulSet/opensearch` | `configfile` (initContainer) | `opensearchproject/opensearch:3.6.0` | True | 1000 | None | ['ALL'] | None | **Fail** | thiếu allowPrivilegeEscalation=false, thiếu readOnlyRootFilesystem |

### 4.2. Phân tích Các trường hợp Đặc biệt (Exceptions & Custom Configurations)

* **Các Container của bên thứ ba (Third-party Images)**:
  * `grafana`, `jaeger`, `opensearch`, `prometheus`: Các container này được cấu hình mặc định chạy với user non-root cố định (ví dụ: Grafana là `472`, Prometheus là `65534`, Opensearch là `1000`). Tuy nhiên, chúng vẫn thiếu cấu hình `allowPrivilegeEscalation: false` và `readOnlyRootFilesystem: true` để chạy an toàn tuyệt đối.
  * `otel-collector-agent`: Hiện tại đang cấu hình chạy hoàn toàn mặc định (chạy dưới quyền root, không có securityContext). Do otel-collector-agent chạy dưới dạng DaemonSet thu thập metric trực tiếp từ Host (máy vật lý), nó sẽ cần một số đặc quyền cấu hình, cần được rà soát và cấu hình các quyền tối thiểu khi hardening.
* **Các initContainer sử dụng `busybox` (như `wait-for-kafka`, `wait-for-valkey-cart`, `init-config`)**:
  * Các container này dùng để kiểm tra cổng kết nối trước khi app chính khởi động. Vì image `busybox` mặc định không định nghĩa user non-root, chúng chạy dưới quyền root trừ khi Pod cấu hình `podSecurityContext.runAsNonRoot: true`. Chúng cần được gán quyền User ID cố định ở container level.
