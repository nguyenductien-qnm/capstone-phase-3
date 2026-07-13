# Hướng Dẫn Di Chuyển PostgreSQL Sang AWS Managed RDS

Tài liệu này hướng dẫn chi tiết các bước cần thực hiện để chuyển đổi cơ sở dữ liệu PostgreSQL chạy trong cluster (Kubernetes Pod) sang dịch vụ AWS RDS (gồm Primary DB, Read Replica và RDS Proxy) cho hệ thống **techx-corp-platform**.

---

## 1. Phân Tích Phân Luồng Dữ Liệu (Read/Write Splitting)

Hệ thống của bạn bao gồm 3 service tương tác với Postgres, tất cả đều được cấu hình độc lập qua biến môi trường `DB_CONNECTION_STRING`:

| Service | Ngôn Ngữ | Phân Loại | Endpoint Khuyên Dùng |
| :--- | :--- | :--- | :--- |
| **[accounting](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/accounting)** | C# (.NET) | **Chỉ Ghi (Write-Only)** | **RDS Proxy Endpoint** (Tận dụng connection pooling và bảo vệ failover) |
| **[product-catalog](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/product-catalog)** | Go | **Chỉ Đọc (Read-Only)** | **Read Replica Endpoint** (Giảm tải truy vấn đọc cho Primary DB) |
| **[product-reviews](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/product-reviews)** | Python | **Chỉ Đọc (Read-Only)** | **Read Replica Endpoint** (Giảm tải truy vấn đọc cho Primary DB) |

---

## 2. Kế Hoạch Di Chuyển Dữ Liệu (Data Migration)

Thực hiện sao lưu dữ liệu từ database cũ trong cluster và khôi phục vào RDS PostgreSQL Primary.

### Bước 1: Trích xuất dữ liệu (pg_dump) từ Pod cũ
Kết nối vào Postgres pod hiện tại trong EKS để thực hiện backup:
```bash
# 1. Tìm tên pod postgresql
kubectl get pods -n <namespace> | grep postgresql

# 2. Chạy pg_dump và lưu trực tiếp về máy local
kubectl exec -it <postgresql-pod-name> -n <namespace> -- pg_dump -U otelu -d otel > backup.sql
```

### Bước 2: Khôi phục dữ liệu (psql) vào RDS PostgreSQL Primary
Khôi phục dữ liệu vào cơ sở dữ liệu RDS mới (phải kết nối từ máy có quyền truy cập VPC hoặc máy Bastion):
```bash
# Thực thi file sql backup vào RDS Primary (Không khôi phục vào RDS Proxy hoặc Read Replica)
psql -h <rds_primary_endpoint> -U db_admin -d ecommerce_db -f backup.sql
```

---

## 3. Cấu Hình Cập Nhật Helm (`values.yaml`)

Cập nhật tệp cấu hình [values.yaml](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-chart/values.yaml).

### A. Cập nhật cho `accounting` (Sử dụng RDS Proxy)
Định dạng connection string của C# Npgsql yêu cầu cấu hình SSL và tắt tính năng EF Core autotracing nếu cần:
```yaml
accounting:
  env:
    - name: DB_CONNECTION_STRING
      value: "Host=<rds_proxy_endpoint>;Port=5432;Username=db_admin;Password=<db_password>;Database=ecommerce_db;SSL Mode=Require;Trust Server Certificate=true;"
```

### B. Cập nhật cho `product-catalog` (Sử dụng Read Replica)
Định dạng connection string của Go driver (`lib/pq`) với chế độ `sslmode=require`:
```yaml
product-catalog:
  env:
    - name: DB_CONNECTION_STRING
      value: "postgres://db_admin:<db_password>@<rds_replica_endpoint>:5432/ecommerce_db?sslmode=require"
```

### C. Cập nhật cho `product-reviews` (Sử dụng Read Replica)
Định dạng connection string của Python `psycopg2` với `sslmode=require`:
```yaml
product-reviews:
  env:
    - name: DB_CONNECTION_STRING
      value: "host=<rds_replica_endpoint> port=5432 user=db_admin password=<db_password> dbname=ecommerce_db sslmode=require"
```

---

## 4. Tắt database PostgreSQL cũ trong Cluster
Sau khi đã di chuyển dữ liệu thành công và cập nhật Helm, tắt/giảm số lượng pod postgresql in-cluster về `0` để tránh nhầm lẫn và tiết kiệm tài nguyên:
```yaml
# values.yaml
postgresql:
  enabled: false
```
Hoặc scale down statefulset/deployment:
```bash
kubectl scale statefulset postgresql --replicas=0 -n <namespace>
```

---

## 5. Quy Trình Xác Thực Sau Triển Khai (Post-Deployment Verification)

Sau khi deploy (`helm upgrade`), chạy các lệnh sau để kiểm tra lỗi kết nối:

```bash
# 1. Kiểm tra log ghi đơn hàng của accounting
kubectl logs -f deployment/accounting -n <namespace>

# 2. Kiểm tra log đọc sản phẩm của catalog
kubectl logs -f deployment/product-catalog -n <namespace>

# 3. Kiểm tra log đọc review của product-reviews
kubectl logs -f deployment/product-reviews -n <namespace>
```

Nếu xuất hiện lỗi liên quan đến SSL/TLS hoặc thông tin đăng nhập, hãy kiểm tra lại cấu hình Security Group của RDS/RDS Proxy đã cho phép IP từ subnets của EKS chưa.
