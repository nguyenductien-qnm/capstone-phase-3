# Cấu hình ElastiCache Valkey - E-commerce Infrastructure

Tài liệu này mô tả chi tiết cấu hình bộ nhớ đệm (Cache) chạy mã nguồn mở Valkey được triển khai tự động qua Terraform.

---

## 1. Thông số Kỹ thuật Cache (Cache Specs)

* **Cache Engine**: Valkey phiên bản `7.2` (Engine mã nguồn mở hiệu năng cao thế hệ mới thay thế Redis).
* **Node Type**: `cache.t4g.micro` (Sử dụng chip Graviton tiết kiệm điện năng và tối ưu chi phí).
* **Mô hình triển khai (Replication Group)**: 
  - Khởi tạo **2 nodes** (`num_cache_clusters = 2`).
  - Bao gồm: 1 node **Primary** (nhận ghi/đọc) và 1 node **Replica** (nhận đọc / đóng vai trò hot standby).

---

## 2. Cơ chế Sẵn sàng cao (High Availability)

* **Tự động Failover**: Bật (`automatic_failover_enabled = true`). Các node được AWS phân bổ tự động trên các Availability Zones (AZs) khác nhau.
* **Cơ chế hoạt động**:
  - Khi node Primary gặp sự cố, AWS tự động phát hiện và thăng chức (promote) node Replica lên làm Primary mới.
  - Tên miền endpoint chính (`valkey_primary_endpoint`) tự động cập nhật hướng kết nối về node mới trong vòng vài giây, đảm bảo ứng dụng không bị gián đoạn.

---

## 3. Bảo mật & Mã hóa dữ liệu (Security & Encryption)

* **Mã hóa dữ liệu khi truyền tải (In-transit Encryption)**: Bật (`transit_encryption_enabled = true`). Bắt buộc mã hóa SSL/TLS cho mọi kết nối đọc/ghi giữa EKS pods và Valkey cluster.
* **Mã hóa dữ liệu tĩnh (At-rest Encryption)**: Bật (`at_rest_encryption_enabled = true`). Dữ liệu cache lưu trên ổ đĩa được mã hóa hoàn toàn.
* **Tách biệt mạng & Security Group**:
  - Valkey được đặt hoàn toàn trong tầng mạng cô lập (Private Data Subnets).
  - Security Group của Valkey tạm thời chấp nhận kết nối inbound cổng `6379` từ mọi hướng (`0.0.0.0/0`) để đội ngũ bảo mật cấu hình lại sau.

---

## 4. Tham số Cấu hình trong `terraform.tfvars`

Các biến cấu hình cache được quản lý tập trung:
```hcl
valkey_node_type          = "cache.t4g.micro"
valkey_num_cache_clusters = 2
```
