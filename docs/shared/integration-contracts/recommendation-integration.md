# Hợp Đồng Tích Hợp Kỹ Thuật (Integration Contract) — Recommendation Service

* **Đơn vị sở hữu**: AI Team (AIO03) & Platform Team (CDO)
* **Trạng thái**: Implemented
* **Ngày cập nhật**: 2026-07-14

Tài liệu này đặc tả cam kết tích hợp kỹ thuật cho dịch vụ **Recommendation** (Python gRPC Server) để phục vụ tính năng Gợi ý sản phẩm thông minh bằng AI (AI Recommendations).

---

## 1. Thông Số Môi Trường & Kết Nối (Env Variables)

Dịch vụ `recommendation` nhận các biến môi trường cấu hình kết nối sau:

| Tên biến | Kiểu dữ liệu | Giá trị mặc định / Mô tả |
| :--- | :--- | :--- |
| `RECOMMENDATION_PORT` | Integer | `8080` (Cổng chạy gRPC mặc định) |
| `DB_CONNECTION_STRING` | String | Chuỗi kết nối tới PostgreSQL `product-catalog` Database có chứa trường `embedding` và cài đặt extension `pgvector`. (VD: `postgresql://user:pass@host:5432/catalog`) |
| `FLAGD_HOST` | String | `flagd` (Host của OpenFeature Flagd) |
| `FLAGD_PORT` | Integer | `8013` (Cổng kết nối Flagd) |
| `PRODUCT_CATALOG_ADDR` | String | (Tuỳ chọn) Địa chỉ gRPC của product catalog để fallback nếu cần |

---

## 2. Ràng Buộc Hệ Thống (System Requirements)

Để tính năng AI Recommendations hoạt động, hạ tầng CDO cần đảm bảo:

1. **Database PostgreSQL 16+**: Phải hỗ trợ và kích hoạt sẵn extension `pgvector` trên schema `catalog`.
2. **Flagd Configuration**: Cung cấp cờ `aiRecommendationsEnabled` (Boolean) thông qua Flagd. Nếu cờ này là `true`, service sẽ thực hiện query Cosine Similarity qua `pgvector`. Nếu `false`, service sẽ tự động fallback về thuật toán gợi ý ngẫu nhiên như phiên bản cũ.

---

## 3. Ràng Buộc Tài Nguyên K8s (Kubernetes Resource Limits)

Để đảm bảo tối ưu hóa chi phí vận hành cụm EKS của dự án:

* **CPU Request**: `100m`
* **CPU Limit**: `500m`
* **Memory Request**: `128Mi`
* **Memory Limit**: `256Mi`
