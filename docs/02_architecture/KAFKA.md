# Tài liệu Hạ tầng Amazon MSK (Managed Streaming for Apache Kafka)

Tài liệu này mô tả chi tiết kiến trúc hạ tầng và cấu hình của cụm Amazon MSK được thiết lập thông qua Terraform.

---

## 1. Tổng quan thành phần (Architecture Overview)

| Tham số | Giá trị cấu hình | Ghi chú |
| :--- | :--- | :--- |
| **Cluster Name** | `${project_name}-${environment}-msk` | Định danh cụm theo project và môi trường |
| **Kafka Version** | `3.9.0` | Phiên bản Apache Kafka đang chạy |
| **Broker Nodes** | `length(var.mq_subnet_ids)` | Số lượng Broker node (bằng số Subnets được cấu hình) |
| **Broker Instance Type** | `kafka.t3.small` | Dòng EC2 instance nhỏ gọn, tối ưu chi phí cho Dev/Sandbox |
| **Storage (EBS)** | `10 GB` | Dung lượng ổ đĩa gp3 cho mỗi broker node |

---

## 2. Thiết lập Mạng & Security Group (Networking & Access Control)

Cụm MSK được cô lập hoàn toàn trong mạng nội bộ (Private VPC) và chỉ chấp nhận kết nối từ các EKS Nodes được cấu hình.

*   **Subnets sử dụng**: `private_mq_subnet_ids` (Các subnets private dành riêng cho Message Queue).
*   **Security Group**: `${project_name}-${environment}-msk-sg`
    *   **Inbound Rules**:
        *   Cho phép lưu lượng từ Security Group của cụm EKS (`eks_security_group_id`).
        *   Các cổng cho phép: từ `9092` (Plaintext), `9094` (TLS) đến `9096` (SASL/SCRAM).
    *   **Outbound Rules**:
        *   Cho phép kết nối ra ngoài mọi hướng (`0.0.0.0/0`) để tải các gói/liên kết với AWS Secrets Manager, CloudWatch Logs, v.v.

---

## 3. Cấu hình Kafka (Custom Configuration)

Sử dụng cấu hình động thông qua `aws_msk_configuration` giúp tối ưu hóa luồng hoạt động của Broker:

```properties
auto.create.topics.enable=true
default.replication.factor=2
min.insync.replicas=1
num.partitions=1
```

*   `auto.create.topics.enable=true`: Cho phép các microservice tự tạo Topic khi gửi message lần đầu mà không cần tạo trước thủ công.
*   `default.replication.factor=2`: Nhân bản dữ liệu trên 2 broker khác nhau đảm bảo tính sẵn sàng cao (HA).
*   `min.insync.replicas=1`: Số lượng bản sao tối thiểu cần ghi nhận thành công để xác thực transaction.

---

## 4. Bảo mật & Xác thực (Security & Authentication)

Hạ tầng MSK áp dụng chuẩn bảo mật nghiêm ngặt cho dữ liệu truyền tải (In Transit) và xác thực người dùng (Client Authentication).

### 4.1. Mã hóa (Encryption)
*   **Encryption in Transit**:
    *   **Client to Broker**: Bắt buộc sử dụng giao thức bảo mật `TLS` (Port 9094) hoặc `SASL/SCRAM` (Port 9096).
    *   **In-Cluster (Giữa các broker)**: Mã hóa TLS toàn bộ dữ liệu luân chuyển nội bộ cụm.

### 4.2. Cơ chế xác thực (Authentication)
*   Sử dụng **SASL/SCRAM** (Salted Challenge Response Authentication Mechanism) để định danh client.
*   **Quản lý thông tin xác thực**:
    *   Mật khẩu được tạo ngẫu nhiên 16 ký tự không chứa ký tự đặc biệt bằng `random_password`.
    *   Lưu trữ an toàn trên **AWS Secrets Manager** với tên bí mật tuân thủ định dạng `AmazonMSK_${project_name}-${environment}-msk-secret` (Tiền tố `AmazonMSK_` là bắt buộc để MSK liên kết tự động).
    *   Secret được mã hóa bằng khóa riêng biệt **AWS KMS Key** (`aws_kms_key.msk`).
    *   Cụm MSK đọc thông tin này trực tiếp thông qua liên kết `aws_msk_scram_secret_association`.

---

## 5. Giám sát & Logs (Monitoring & Logging)

*   **CloudWatch Logs**: Broker logs được đẩy trực tiếp lên CloudWatch Log Group `/aws/msk/${project_name}-${environment}-msk`.
    *   Thời gian lưu trữ logs (Retention Period): `3 ngày` để tối ưu chi phí cho môi trường Sandbox.
*   **Open Monitoring (Prometheus)**:
    *   JMX Exporter: `Disabled`
    *   Node Exporter: `Disabled`

---

## 6. Danh sách Đầu ra Terraform (Terraform Outputs)

Các thông tin kết nối và quản trị được xuất ra cho các module khác sử dụng:

| Tên Output | Kiểu | Mô tả |
| :--- | :--- | :--- |
| `bootstrap_brokers_plaintext` | `string` | Connection string Plaintext (Cổng 9092). *Lưu ý: Không dùng nếu bật TLS bắt buộc.* |
| `bootstrap_brokers_tls` | `string` | Connection string TLS (Cổng 9094). An toàn cho kết nối nội bộ VPC. |
| `bootstrap_brokers_sasl_scram` | `string` | Connection string SASL/SCRAM (Cổng 9096). Sử dụng khi ứng dụng kết nối xác thực bằng username/password. |
| `msk_security_group_id` | `string` | Security Group ID của cụm MSK, dùng để thiết lập kết nối từ các máy trạm/bastion. |
| `msk_secret_arn` | `string` | ARN của AWS Secrets Manager lưu trữ credentials kết nối. |
