# Cẩm Nang Triển Khai Hệ Thống TechX Corp (Helm & EKS)

Tài liệu ghi chép toàn bộ kiến thức cốt lõi về cơ chế hoạt động của Helm và các bước vận hành thực tế trên EKS/AWS.

---

## 1. Bản đồ Hoạt động của Helm Chart

Helm là trình quản lý gói giúp đóng gói toàn bộ ứng dụng thành 1 Chart duy nhất và cấu hình tập trung qua file `values.yaml`.

### 1.1 Giải thích vai trò chi tiết của từng file/thư mục

| Đường dẫn file / thư mục | Vai trò | Tác dụng & Chi tiết nội dung |
| :--- | :--- | :--- |
| 📄 **`Chart.yaml`** | Khai báo thư viện phụ thuộc | Khai báo tên chart, phiên bản và các service cài thêm bên ngoài như **Jaeger** (Distributed Tracing), **Prometheus** (Metrics), **Grafana** (Dashboards), **OpenSearch** (Logs). |
| 📄 **`values.yaml`** | Cấu hình mặc định (Baseline) | Chứa cấu hình Key-Value mặc định cho cả 18+ service (như `replicas: 1`, RAM/CPU limits, biến môi trường env, cổng kết nối). |
| 📄 **`values.schema.json`** | File kiểm tra cú pháp (Schema validation) | Quy định luật gõ code cho file `values.yaml`. Giúp trình soạn thảo tự động gợi ý code (auto-complete) và báo lỗi cú pháp khi gõ sai định dạng. |
| 📂 **`templates/`** | Thư mục chứa các file mẫu (Templates) | Chứa các file mẫu để sinh tài nguyên cho Kubernetes: |
| └── 📄 `component.yaml` | Bộ sinh manifest chính | Quét qua danh sách các service trong `values.yaml` để tự sinh ra Deployment/Service cho Kubernetes. |
| └── 📄 `_objects.tpl` | Hàm tạo Object | Chứa hàm mẫu vẽ Deployment, Service, Ingress cho container. Được gọi bởi `component.yaml`. |
| └── 📄 `_pod.tpl` | Hàm cấu hình Pod | Chứa hàm mẫu cấu hình chi tiết bên trong Pod (env, bảo mật, container spec). |
| └── 📄 `_helpers.tpl` | Hàm bổ trợ đặt tên | Tự tạo tên dịch vụ chuẩn hóa và gắn nhãn (labels) để tránh xung đột tên trên Kubernetes. |
| └── 📄 `flagd-config.yaml` | Cấu hình ConfigMap flag | Tạo ConfigMap chứa danh sách flag để nạp vào container `flagd`. |
| └── 📄 `postgresql-init-config.yaml` | Cấu hình ConfigMap DB | Tạo ConfigMap chứa các lệnh SQL khởi tạo Database PostgreSQL. |
| └── 📄 `grafana-config.yaml` | Cấu hình ConfigMap Grafana | Tạo ConfigMap chứa cấu hình dashboard mẫu và datasources cho Grafana. |
| └── 📄 `serviceaccount.yaml` | Cấu hình tài khoản K8s | Tạo định danh bảo mật cho các Pod chạy ứng dụng (giúp tích hợp IRSA để phân quyền AWS IAM). |
| └── 📄 `NOTES.txt` | File hướng dẫn sau cài đặt | Hướng dẫn port-forward để truy cập web sau khi deploy thành công. |
| 📂 **`postgresql/init.sql`** | File SQL khởi tạo | Các câu lệnh tạo bảng và nạp dữ liệu sản phẩm mẫu cho Database PostgreSQL. |
| 📂 **`grafana/provisioning/`** | Thư mục dashboard mẫu | Cấu hình sẵn biểu đồ đo đạc SLO, CPU/RAM, Traces cho Grafana. |
| 📂 **`flagd/demo.flagd.json`** | File flag sự cố mặc định | Chứa cấu hình mặc định dùng để tắt/bật các sự cố của hệ thống. |

### 1.2 Quy trình chạy cụ thể khi thực hiện lệnh deploy

Khi chạy lệnh deploy:
```bash
helm upgrade --install techx-corp ./platform/charts/application \
  -n techx-tf4 --create-namespace \
  --set default.image.repository=<ĐỊA_CHỈ_ECR> \
  -f platform/gitops/environments/sandbox/values-observability.yaml \
  -f platform/gitops/environments/sandbox/values-flagd-sync.yaml
```

**Thứ tự các file được gọi và chạy trong nền:**

1. **Đọc Metadata (`Chart.yaml`):** Helm đọc file `Chart.yaml` đầu tiên để biết thông tin gói và kiểm tra xem các thư viện dependencies (Prometheus, Grafana...) đã được tải về thư mục `charts/` chưa.
2. **Đọc Cấu hình & Trộn (Merge values):** Helm đọc tiếp file `values.yaml` để lấy các giá trị mặc định. Sau đó, nó đè các cấu hình từ file `values-observability.yaml` và `values-flagd-sync.yaml` lên trên để tạo thành bộ cấu hình hoàn chỉnh duy nhất trong bộ nhớ.
3. **Nạp Thư viện Code (Các file `_`):** Helm đọc các file có dấu gạch dưới `_` ở đầu trong thư mục `templates/` (`_helpers.tpl`, `_objects.tpl`, `_pod.tpl`) để nạp các hàm tạo deployment/service/ingress vào bộ nhớ.
4. **Biên dịch sinh Manifest:** Helm chạy file `component.yaml` và các file `.yaml` khác trong `templates/`. Nó lấy giá trị cấu hình (ở Bước 2) lắp vào các hàm mẫu (ở Bước 3) để xuất ra các file manifest chuẩn Kubernetes.
5. **Gửi lên Kubernetes API:** Helm đóng gói toàn bộ manifest thành một chuỗi văn bản lớn gửi lên cụm EKS.
6. **Kubernetes tạo tài nguyên (Thứ tự mặc định K8s):** Cụm EKS tiếp nhận và tạo tài nguyên theo thứ tự: Tạo Namespace $\rightarrow$ Tạo ServiceAccount $\rightarrow$ Tạo ConfigMap (đọc từ `postgresql/init.sql`, `grafana/provisioning/`) $\rightarrow$ Tạo Service/Ingress $\rightarrow$ Tạo Pod (Deployment) chạy app.
7. **Cứu hộ khởi động (`initContainers`):** Các Pod chạy app chạy `initContainers` trước để chờ các phụ thuộc sẵn sàng (ví dụ: checkout/payment chờ Kafka/Postgres mở cổng). Khi phụ thuộc sẵn sàng thì ứng dụng chính mới chính thức khởi động.
8. **In hướng dẫn (`NOTES.txt`):** Helm đọc file `NOTES.txt` hiển thị hướng dẫn port-forward lên terminal của bạn.

### 1.3 Cơ chế ghi đè cấu hình (Values Overwrite)

Việc ghi đè cấu hình từ `platform/gitops/environments/sandbox/` lên Chart mặc định hoàn toàn được kiểm soát bởi các tham số `-f` (hoặc `--values`) trong câu lệnh Helm CLI:

1. **Helm nạp `values.yaml` mặc định:** Tự động đọc file gốc `platform/charts/application/values.yaml` trước để làm Baseline.
2. **Ghi đè lần 1 (`-f platform/gitops/environments/sandbox/values-observability.yaml`):** Helm nạp file này tiếp theo, các Key trùng lặp sẽ bị ghi đè (ví dụ: bật Prometheus/Grafana từ `false` thành `true`).
3. **Ghi đè lần 2 (`-f platform/gitops/environments/sandbox/values-flagd-sync.yaml`):** Helm nạp file này cuối cùng, ghi đè lệnh chạy mặc định của `flagd` để trỏ về server sync sự cố trung tâm của BTC.

> [!WARNING]
> File khai báo sau cùng luôn có quyền ưu tiên cao nhất. Nếu bạn quên đính kèm file cấu hình sự cố (`values-flagd-sync.yaml`) khi deploy, Helm sẽ tự động reset flagd về mặc định (chạy local file), dẫn đến mất kết nối sự cố của BTC và vi phạm quy chế thi.

---

## 2. Quy Trình Vận Hành & Deploy lên AWS EKS (Step-by-Step)

### Bước 0: Tạo hạ tầng AWS bằng Terraform (Nếu chưa có cụm EKS)

Nếu tài khoản AWS cá nhân của bạn chưa có cụm EKS và ECR Registry, hãy chạy bộ code Terraform mẫu được chia Module ở thư mục `terraform/`:

1.  **Cấu hình:** Mở file `terraform/environments/sandbox/terraform.tfvars` cấu hình region, instance_types, node sizes tùy ý.
2.  **Khởi chạy Terraform:**
    ```bash
    cd terraform/environments/sandbox
    terraform init      # Tải các module AWS VPC, EKS từ registry
    terraform plan      # Xem trước các tài nguyên sẽ được tạo
    terraform apply     # Tạo hạ tầng (VPC, EKS, ECR) - mất khoảng 15 phút
    ```
3.  **Lấy Kubeconfig kết nối cụm:** Lấy lệnh được hiển thị ở output `eks_kubeconfig_command` chạy trên terminal của bạn để trỏ `kubectl` vào EKS mới tạo.

### Bước 1: Kết nối EKS Cluster
Cấu hình local `kubectl` kết nối tới AWS EKS của Task Force (hoặc dùng lệnh xuất ra ở Bước 0):
```bash
aws eks update-kubeconfig --region <VÙNG_AWS> --name <TÊN_CỤM_EKS>
```
Kiểm tra kết nối:
```bash
kubectl get nodes
```

### Bước 2: Build & Đẩy Docker Image lên ECR
1.  Mở file `techx-corp-platform/.env.override` sửa `IMAGE_NAME` thành địa chỉ ECR của TF bạn:
    ```env
    IMAGE_NAME=<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/techx-corp
    ```
2.  Đăng nhập Docker vào AWS ECR:
    ```bash
    aws ecr get-login-password --region <VÙNG_AWS> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<VÙNG_AWS>.amazonaws.com
    ```
3.  Chạy script build và push:
    ```bash
    ./scripts/build/build-push-images.sh
    ```

### Bước 3: Tải Dependencies và Deploy Helm Chart
1.  Add các repo Helm:
    ```bash
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
    helm repo add opensearch https://opensearch-project.github.io/helm-charts
    ```
2.  Tải các Subcharts:
    ```bash
    helm dependency build ./platform/charts/application
    ```
3.  Cấu hình token BTC cấp trong file `platform/gitops/environments/sandbox/values-flagd-sync.yaml`.
4.  Chạy lệnh deploy:
    ```bash
    REG=<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/techx-corp
    NS=techx-<tên_đội_bạn> # Ví dụ: techx-tf4
    
    helm upgrade --install techx-corp ./platform/charts/application -n $NS --create-namespace \
      --set default.image.repository=$REG \
      -f platform/gitops/environments/sandbox/values-observability.yaml \
      -f platform/gitops/environments/sandbox/values-flagd-sync.yaml
    ```

### Bước 4: Kiểm tra & Truy cập cổng
1.  Kiểm tra Pods chạy thành công:
    ```bash
    kubectl get pods -n $NS
    ```
2.  Mở cổng truy cập (Port-forward):
    ```bash
    kubectl port-forward -n $NS svc/frontend-proxy 8080:8080
    ```
3.  Truy cập:
    *   Storefront: [http://localhost:8080](http://localhost:8080)
    *   Grafana: [http://localhost:8080/grafana/](http://localhost:8080/grafana/)
    *   Jaeger: [http://localhost:8080/jaeger/ui/](http://localhost:8080/jaeger/ui/)

