# Cấu hình RDS PostgreSQL - E-commerce Infrastructure

Tài liệu này mô tả chi tiết cấu hình cơ sở dữ liệu RDS PostgreSQL được triển khai tự động qua Terraform.

---

## 1. Thông số Kỹ thuật Database (Database Specs)

* **Database Engine**: PostgreSQL phiên bản `16.1`.
* **Instance Class (Primary & Replica)**: `db.t4g.micro` (Dòng chip Graviton thế hệ mới tiết kiệm điện năng và chi phí).
* **Storage**: `20 GB gp3` (SSD đa dụng thế hệ mới, hỗ trợ IOPS độc lập).
* **Mã hóa dữ liệu tĩnh (At-rest Encryption)**: Bật mã hóa đĩa cứng (`storage_encrypted = true`) sử dụng khóa mặc định của RDS nhằm bảo vệ dữ liệu vật lý.

---

## 2. Cơ chế Sẵn sàng cao & Chia tải đọc (HA & Read Scaling)

* **Multi-AZ Deployment**: Bật (`rds_multi_az = true`). AWS tự động tạo thêm một database Standby ở Availability Zone (AZ) dự phòng và thực hiện sao chép đồng bộ (Synchronous replication). Khi AZ chính gặp sự cố, AWS tự động Failover sang standby.
* **Read Replica**: Bật (`enable_read_replica = true`). Tạo thêm một database bản sao độc lập (Asynchronous replication) chuyên phục vụ cho các truy vấn đọc từ ứng dụng, giúp giảm tải tối đa cho Primary DB.

---

## 3. Cầu nối RDS Proxy (Connection Pooling)

* **Mục đích**: Làm trung gian quản lý và tối ưu hóa hàng ngàn kết nối đồng thời từ các EKS Pods (microservices).
* **Lợi ích**:
  - Tiết kiệm bộ nhớ và tài nguyên cho database do không phải khởi tạo kết nối vật lý liên tục.
  - **Giảm thời gian gián đoạn (failover)**: Khi DB chính gặp sự cố, RDS Proxy tự chuyển hướng sang DB dự phòng trong `<5 giây` mà không làm sập kết nối của ứng dụng phía trên.
  - Tích hợp bảo mật chặt chẽ với AWS Secrets Manager.

---

## 4. Bảo mật & Quản lý Thông tin xác thực (Security & Credentials)

* **AWS Secrets Manager**: Mật khẩu quản trị database được khởi tạo ngẫu nhiên bằng code (`random_password`) và đẩy trực tiếp lên Secrets Manager.
* **Quy trình Xác thực**: RDS Proxy đóng vai trò đọc thông tin xác thực từ Secrets Manager qua phân quyền IAM Role để kết nối và xác thực với PostgreSQL DB.
* **Tách biệt mạng & Security Group**:
  - Cả DB và Proxy đều nằm hoàn toàn trong tầng mạng cô lập (Private Data Subnets).
  - Security Group của DB và Proxy tạm thời chấp nhận kết nối inbound cổng `5432` từ mọi hướng (`0.0.0.0/0`) để đội ngũ bảo mật cấu hình lại sau.

---

## 5. Tham số Cấu hình trong `terraform.tfvars`

Các biến cấu hình RDS chính được quản lý tập trung:
```hcl
db_name                = "ecommerce_db"
db_username            = "db_admin"
rds_instance_class     = "db.t4g.micro"
rds_allocated_storage  = 20
enable_read_replica    = true
replica_instance_class = "db.t4g.micro"
enable_rds_proxy       = true
rds_multi_az           = true
```
