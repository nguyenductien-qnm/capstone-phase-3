# Disaster Recovery Restore Runbook (MANDATE-20)

Tài liệu này hướng dẫn chi tiết các bước khôi phục Point-In-Time (PITR) cho cơ sở dữ liệu RDS PostgreSQL về môi trường khôi phục tách biệt (`drill-temp`) nhằm xác minh cam kết RPO và RTO.

---

## 1. Nguyên tắc An toàn & Tối ưu chi phí

* **Không đè lên Production/Develop**: Tuyệt đối không phục hồi đè lên các DB instance đang chạy. Luôn khôi phục ra một DB Instance mới hoàn toàn.
* **Quy tắc đặt tên (Safety Guard)**: Tên DB Instance mới bắt buộc phải kết thúc bằng hậu tố `-drill-temp` (ví dụ: `ecommerce-develop-dev-postgres-drill-temp`). Điều này giúp script cleanup tự động nhận diện và tránh xóa nhầm DB thật.
* **Security Group cách ly**: Sử dụng Security Group `db_drill` (không cho phép kết nối từ EKS Node Group, chỉ cho phép kết nối từ IP của Admin/Runner để verify dữ liệu).
* **Tối ưu chi phí**: Tắt Multi-AZ (`--no-multi-az`) khi restore để giảm 50% chi phí chạy instance tạm.

---

## 2. Quy trình Thực hiện Drill Khôi phục (Point-In-Time Restore)

### Bước 1: Thu thập thông tin từ Terraform Outputs
Chạy lệnh sau tại thư mục `terraform/environments/develop` để lấy các thông tin cần thiết:
```bash
# Lấy DB subnet group name
SUBNET_GROUP=$(terraform output -raw db_subnet_group_name 2>/dev/null || echo "ecommerce-develop-dev-rds-subnet-group")

# Lấy Security Group cách ly dành riêng cho Drill (do Khang thiết lập)
DRILL_SG_ID=$(terraform output -raw db_drill_security_group_id)

# Lấy ID của RDS Source (Production/Develop cần drill)
SOURCE_DB_ID="ecommerce-develop-dev-postgres" # Thay đổi tương ứng nếu chạy trên sandbox/develop
```

### Bước 2: Xác định mốc thời gian phục hồi (T0)
Mốc thời gian khôi phục $T_0$ phải là thời điểm dữ liệu còn nguyên vẹn (trước khi xảy ra sự cố mất mát dữ liệu).
* Định dạng thời gian: **UTC ISO-8601** (ví dụ: `2026-07-24T03:05:00Z`).

### Bước 3: Chạy lệnh Restore PITR ra DB Instance mới
Thực thi lệnh AWS CLI sau để tiến hành khôi phục:

```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier "$SOURCE_DB_ID" \
  --target-db-instance-identifier "${SOURCE_DB_ID}-drill-temp" \
  --restore-time "2026-07-24T03:05:00Z" \
  --db-subnet-group-name "$SUBNET_GROUP" \
  --vpc-security-group-ids "$DRILL_SG_ID" \
  --no-multi-az \
  --no-publicly-accessible \
  --storage-type gp3
```

**Giải thích các tham số tối ưu chi phí & an toàn:**
* `--target-db-instance-identifier`: Tên bắt buộc kết thúc bằng `-drill-temp`.
* `--no-multi-az`: Tắt Multi-AZ giúp tối ưu hóa chi phí (giảm 50% chi phí chạy instance tạm).
* `--vpc-security-group-ids`: Trỏ về SG cô lập `$DRILL_SG_ID` để ngăn các ứng dụng kết nối nhầm.
* `--no-publicly-accessible`: Đảm bảo cơ sở dữ liệu không bị phơi bày ra internet.
* `--storage-type gp3`: Sử dụng gp3 để tối ưu chi phí và hiệu năng storage.

### Bước 4: Chờ Instance chuyển sang trạng thái sẵn sàng
Bạn có thể theo dõi tiến độ khôi phục qua lệnh:
```bash
aws rds wait db-instance-available --db-instance-identifier "${SOURCE_DB_ID}-drill-temp"
```

### Bước 5: Kết nối & Xác minh toàn vẹn dữ liệu (Verify)
1. Lấy Connection Endpoint của DB Drill mới:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier "${SOURCE_DB_ID}-drill-temp" \
     --query "DBInstances[0].Endpoint.Address" \
     --output text
   ```
2. Thực hiện truy vấn (Query) từ máy Admin/Runner được phép truy cập (đã khai báo IP trong Security Group):
   * Đối chiếu số lượng dòng (Row count) và checksum (MD5) của bảng dữ liệu tại mốc khôi phục $T_0$.
   * Kiểm tra xem các dữ liệu ghi sau mốc $T_1$ (sự cố) có xuất hiện hay không (để chứng minh khôi phục đúng Point-In-Time chứ không phải restore bản mới nhất).

---

## 3. Dọn dẹp tài nguyên (Cleanup)

Sau khi hoàn tất kiểm tra và lấy đầy đủ bằng chứng (Evidence), chạy ngay script dọn dẹp để hủy instance tạm, tránh phát sinh chi phí:
```bash
bash scripts/dr/destroy-drill-env.sh
```
*(Script này sẽ tự động gỡ Deletion Protection và xóa sạch DB Instance tạm thời).*
