# Danh mục Tài nguyên (Resource Catalog)

Tổng hợp các tài nguyên hạ tầng AWS (Terraform) và Kubernetes (Helm) trong cụm.

---

## 1. Hạ tầng AWS (Terraform) - Region us-east-1

- **VPC (`techx-vpc-dev`):** Dải mạng `10.0.0.0/16`.
  - 3 Subnets Public (chứa ELB).
  - 3 Subnets Private (chứa EKS Nodes).
  - 1 Internet Gateway & 1 NAT Gateway dùng chung.
- **ECR (`techx-corp`):** Registry lưu trữ Docker Images.
- **EKS (`techx-eks-dev`):** Cụm Kubernetes phiên bản **1.36**.
- **EKS Node Group (`techx-node-group-dev`):** 3 nodes instance **t3.medium** chạy trong mạng Private.

---

## 2. Tài nguyên trong Kubernetes (Namespace: techx-tf1)

### 2.1 Cổng vào (Proxy)
- **`frontend-proxy` (Port 8080 - LoadBalancer):** Envoy Proxy tiếp nhận toàn bộ traffic đầu vào, định tuyến đến app hoặc các dashboard giám sát.

### 2.2 Microservices ứng dụng (19 dịch vụ)
- `frontend` (8080 - Node/NextJS): Giao diện Webstore.
- `product-catalog` (8080 - Go): Danh mục sản phẩm.
- `product-reviews` (3551 - Python): Review và hỏi đáp AI.
- `llm` (8000 - Python): Giả lập OpenAI API.
- `cart` (8080 - .NET): Giỏ hàng.
- `checkout` (8080 - Go): Đặt hàng & thanh toán.
- `payment` (8080 - Node): Xử lý thanh toán.
- `shipping` (8080 - Rust): Tính phí và giao hàng.
- `quote` (8080 - PHP): Báo giá.
- `currency` (8080 - C++): Đổi tiền.
- `email` (8080 - Ruby): Gửi mail xác nhận.
- `recommendation` (8080 - Python): Gợi ý mua kèm.
- `ad` (8080 - Java): Quảng cáo.
- `accounting` (Kafka consumer - C#): Ghi sổ kế toán.
- `fraud-detection` (Kafka consumer - Kotlin): Phát hiện gian lận.
- `image-provider` (8081 - Nginx): Cung cấp ảnh sản phẩm.
- `load-generator` (8089 - Locust): Giả lập người dùng ảo mua hàng tạo tải.
- `flagd` (8013/8016 - Go): Đồng bộ Feature Flag từ ban tổ chức.

### 2.3 Databases & Message Queue
- **`postgresql` (5432):** DB lưu danh mục, review, kế toán.
- **`valkey-cart` (6379):** Lưu thông tin giỏ hàng tạm thời.
- **`kafka` (9092/9093):** Hàng đợi checkout đơn hàng.

### 2.4 Giám sát & Đo lường (Observability)
- **`otel-collector` (4317/4318):** Thu thập Metrics, Traces, Logs.
- **`prometheus` (9090):** Lưu trữ Metrics.
- **`jaeger` (16686):** Phân tích Distributed Tracing (luồng request).
- **`opensearch` (9200):** Lưu trữ Logs tập trung.
- **`grafana` (80):** Dashboard biểu đồ SLO và tài nguyên.
