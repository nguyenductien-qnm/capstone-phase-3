# Hướng Dẫn Di Chuyển Valkey Sang AWS Managed ElastiCache

Tài liệu này hướng dẫn chi tiết các bước cần thực hiện để chuyển đổi cơ sở dữ liệu Valkey chạy trong cluster (Kubernetes Pod) sang dịch vụ AWS ElastiCache Valkey (Replication Group có bật Transit Encryption/SSL) cho hệ thống **techx-corp-platform**.

---

## 1. Phân Tích Hiện Trạng Sử Dụng Valkey

Hệ thống có 2 service kết nối tới Valkey để lưu trữ dữ liệu cache và giỏ hàng:

| Service | Ngôn Ngữ | Nhiệm Vụ | File Cấu Hình Kết Nối |
| :--- | :--- | :--- | :--- |
| **[cart](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/cart)** | C# (.NET) | Lưu trữ giỏ hàng tạm thời | [ValkeyCartStore.cs](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/cart/src/cartstore/ValkeyCartStore.cs) |
| **[product-reviews](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/product-reviews)** | Python | Cache dữ liệu đánh giá sản phẩm | [product_reviews_server.py](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/product-reviews/product_reviews_server.py) |

---

## 2. Các Thay Đổi Cần Thiết Trong Code (Yêu Cầu Cho SSL/TLS)

Do AWS ElastiCache Valkey bật mã hóa đường truyền (`transit_encryption_enabled = true`), client bắt buộc phải kết nối qua SSL/TLS.

### A. Cập nhật Cart Service (C#)
Trong tệp [ValkeyCartStore.cs](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/cart/src/cartstore/ValkeyCartStore.cs#L52), đổi thuộc tính `ssl=false` thành `ssl=true`:

```diff
- _connectionString = $"{valkeyAddress},ssl=false,allowAdmin=true,abortConnect=false";
+ _connectionString = $"{valkeyAddress},ssl=true,allowAdmin=true,abortConnect=false";
```
*(Nếu muốn chạy song song local và cloud, bạn có thể truyền `ssl` từ biến môi trường).*

### B. Cập nhật Product Reviews Service (Python)
Trong tệp [product_reviews_server.py](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-platform/src/product-reviews/product_reviews_server.py#L652), sửa phần khởi tạo client Redis để hỗ trợ TLS:

```diff
- valkey_client = redis.Redis(host=valkey_host, port=valkey_port, decode_responses=True)
+ valkey_client = redis.Redis(host=valkey_host, port=valkey_port, ssl=True, decode_responses=True)
```

---

## 3. Cập Nhật Cấu Hình Helm (`values.yaml`)

Cập nhật tệp [values.yaml](file:///Users/ductiennguyen/Documents/Project/xbrain/capstone-phase-3/techx-corp-chart/values.yaml) để trỏ sang endpoint mới của ElastiCache Valkey.

### A. Cập nhật cho `cart`
Thay thế `valkey-cart:6379` bằng ElastiCache Primary Endpoint:
```yaml
cart:
  env:
    - name: VALKEY_ADDR
      value: "<elasticache_primary_endpoint>:6379"
```

### B. Cập nhật cho `product-reviews`
Đồng bộ hóa cách truyền cấu hình. Code python chỉ đọc `VALKEY_ADDR` nên ta cần định nghĩa biến này trong Helm (thay vì `VALKEY_HOST`/`VALKEY_PORT` cũ):
```yaml
product-reviews:
  env:
    # Xóa bỏ VALKEY_HOST và VALKEY_PORT cũ, thay bằng:
    - name: VALKEY_ADDR
      value: "<elasticache_primary_endpoint>:6379"
```

---

## 4. Kế Hoạch Di Chuyển Dữ Liệu (Data Migration)

Vì dữ liệu trong Valkey của hệ thống này là **dữ liệu tạm (Cache / Giỏ hàng tạm thời)**:
* **Khuyên dùng**: Thực hiện chuyển đổi lạnh (**Cold Cutover**). Khi cấu hình mới được deploy, người dùng cũ có thể bị mất giỏ hàng hiện tại (phải thêm lại vào giỏ), nhưng hệ thống hoạt động bình thường trên cụm mới ngay lập tức. Đây là giải pháp an toàn và nhanh nhất đối với môi trường staging/dev.
* **Nếu bắt buộc giữ dữ liệu**: Sử dụng các công cụ đồng bộ như **`riot-redis`** hoặc cấu hình đồng bộ một chiều từ Valkey cũ sang ElastiCache trước khi chuyển traffic.

---

## 5. Tắt database Valkey cũ trong Cluster
Sau khi hoàn tất di chuyển, tắt dịch vụ Valkey tự vận hành trong cluster:
```yaml
# values.yaml
valkey:
  enabled: false
```
Hoặc tắt qua Kubernetes:
```bash
kubectl scale statefulset valkey-cart --replicas=0 -n <namespace>
```

---

## 6. Quy Trình Xác Thực Sau Triển Khai (Post-Deployment Verification)

Theo dõi log để đảm bảo kết nối thành công:
```bash
# 1. Xem log của Cart service (C#)
kubectl logs -f deployment/cart -n <namespace>
# Log thành công: "Successfully connected to Redis"

# 2. Xem log của Product Reviews (Python)
kubectl logs -f deployment/product-reviews -n <namespace>
# Thực hiện gọi API đánh giá trên UI và xem có lỗi kết nối Redis xuất hiện không.
```
