# Kiến trúc VPC (Virtual Private Cloud) - E-commerce Infrastructure

Tài liệu này mô tả chi tiết thiết kế mạng VPC trong dự án hạ tầng E-commerce, được triển khai hoàn toàn tự động bằng Terraform.

---

## 1. Chi tiết phân bổ Subnets (Subnet Allocation)

VPC sử dải mạng chính **`10.0.0.0/16`** và được chia thành **10 subnets** trải rộng trên các Availability Zones (AZs) khác nhau để đảm bảo Sẵn sàng cao (High Availability):

| Tên Subnet | Dải CIDR | Availability Zone | Mục đích sử dụng | Cấu hình Route | Tags đặc trưng cho EKS / AWS |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **public-1** | `10.0.1.0/24` | `us-east-1a` | NAT Gateway, NLB, Bastion Host | Internet Gateway | `"kubernetes.io/role/elb" = "1"` |
| **public-2** | `10.0.2.0/24` | `us-east-1b` | NLB | Internet Gateway | `"kubernetes.io/role/elb" = "1"` |
| **public-3** | `10.0.3.0/24` | `us-east-1c` | NLB | Internet Gateway | `"kubernetes.io/role/elb" = "1"` |
| **app-1** | `10.0.11.0/24` | `us-east-1a` | EKS Worker Nodes / Pods | NAT Gateway | `"kubernetes.io/cluster/ecommerce-dev-cluster" = "shared"` |
| **app-2** | `10.0.12.0/24` | `us-east-1b` | EKS Worker Nodes / Pods | NAT Gateway | `"kubernetes.io/cluster/ecommerce-dev-cluster" = "shared"` |
| **app-3** | `10.0.13.0/24` | `us-east-1c` | EKS Worker Nodes / Pods | NAT Gateway | `"kubernetes.io/cluster/ecommerce-dev-cluster" = "shared"` |
| **data-1** | `10.0.21.0/24` | `us-east-1a` | RDS PostgreSQL, Valkey Cache | **Isolated** (Chỉ local) | Không có tag ngoại lai |
| **data-2** | `10.0.22.0/24` | `us-east-1b` | RDS PostgreSQL, Valkey Cache | **Isolated** (Chỉ local) | Không có tag ngoại lai |
| **mq-1** | `10.0.31.0/24` | `us-east-1a` | Message Queue (RabbitMQ) | NAT Gateway | Không có tag ngoại lai |
| **mq-2** | `10.0.32.0/24` | `us-east-1b` | Message Queue (RabbitMQ) | NAT Gateway | Không có tag ngoại lai |

---

## 2. Bảng định tuyến (Route Tables)

Mạng VPC được quản trị định tuyến thông qua các bảng định tuyến tách biệt để bảo vệ các tài nguyên bên trong:

1. **Bảng định tuyến Công cộng (Public Route Table)**:
   - Áp dụng cho: **3 Public Subnets**.
   - Quy tắc định tuyến:
     - `10.0.0.0/16` $\rightarrow$ `local` (Định tuyến nội bộ).
     - `0.0.0.0/0` $\rightarrow$ `Internet Gateway (IGW)` (Cho phép đi ra Internet công cộng).

2. **Bảng định tuyến Riêng tư (Private Route Table)**:
   - Áp dụng cho: **3 Private App Subnets** và **2 Private MQ Subnets**.
   - Quy tắc định tuyến:
     - `10.0.0.0/16` $\rightarrow$ `local`.
     - `0.0.0.0/0` $\rightarrow$ `NAT Gateway` (Cho phép các Pod/Server bên trong kết nối một chiều ra Internet để tải thư viện, cập nhật hệ điều hành, gọi API ngoài qua cổng NAT).

3. **Bảng định tuyến Cô lập (Isolated Route Table)**:
   - Áp dụng cho: **2 Private Data Subnets**.
   - Quy tắc định tuyến:
     - `10.0.0.0/16` $\rightarrow$ `local`.
     - **Không có route `0.0.0.0/0`**: Dữ liệu hoàn toàn không thể thoát ra ngoài hoặc bị truy cập từ ngoài Internet, ngăn ngừa hoàn toàn rủi ro rò rỉ dữ liệu.

---

## 3. Tích hợp EKS Auto-Discovery

Để EKS cluster và các Controller (như AWS Load Balancer Controller) tự động phát hiện và liên kết hạ tầng mạng một cách chuẩn xác:

* **Mạng công cộng (Public Subnets)**:
  Gắn thẻ `"kubernetes.io/role/elb" = "1"`. Khi bạn deploy một Service dạng `LoadBalancer` trong Kubernetes, AWS Controller sẽ tự động tìm các subnet này để tạo public NLB/ALB.
* **Mạng nội bộ (Private App Subnets)**:
  Gắn thẻ `"kubernetes.io/cluster/ecommerce-dev-cluster" = "shared"`. Giúp EKS cluster nhận diện các subnet thích hợp để deploy Worker Nodes và gắn ENI mạng. 
  *(Lưu ý: Thẻ `"kubernetes.io/role/internal-elb"` đã được lược bỏ vì toàn bộ microservices giao tiếp trực tiếp qua mạng lưới gRPC nội bộ).*

---

## 4. Các điểm lưu ý về Bảo mật (Security Highlights)

* **Nguyên tắc Đặc quyền Tối thiểu**: Tầng dữ liệu nhạy cảm (RDS, Valkey) không có bất kỳ khả năng kết nối Internet nào.
* **NAT Gateway Dự phòng**: Hạ tầng hỗ trợ tạo 1 NAT duy nhất cho môi trường Dev (tiết kiệm phí) hoặc 3 NAT chạy song song ở 3 AZ cho môi trường Prod (sẵn sàng cao).
* **Kiểm soát cổng vào**: Các dịch vụ Database và Cache được cấu hình Security Group chấp nhận kết nối từ mọi hướng (`0.0.0.0/0`) để phục vụ kiểm tra và cấu hình của đội ngũ bảo mật sau này.
