# Hợp Đồng Tích Hợp Kỹ Thuật (Integration Contracts) - TF1 (AI & CDO)

Tài liệu tích hợp kỹ thuật giữa AI Team (AIO03) và Platform/Storefront Teams (CDO05, CDO09) được mô-đun hóa theo từng dịch vụ chạy độc lập để tránh xung đột cấu hình và tối ưu hóa việc ghép nối:

---

## 📁 1. Hợp đồng tích hợp dịch vụ Product Reviews
Chốt giao diện kết nối bộ đệm cache Valkey, giới hạn tài nguyên và cấu hình metrics giám sát cho dịch vụ Reviews tóm tắt:
👉 **[product-reviews-integration.md](product-reviews-integration.md)**

---

## 📁 2. Hợp đồng tích hợp dịch vụ Shopping Copilot Agent
Chốt cổng giao tiếp gRPC `:50051`, định nghĩa file Protobuf, cơ chế định tuyến Envoy Proxy và cổng bảo mật confirmation gate:
👉 **[shopping-copilot-integration.md](shopping-copilot-integration.md)**

---

## 📁 3. Hợp đồng tích hợp dịch vụ Recommendation
Chốt giao diện kết nối PostgreSQL (pgvector) để thực hiện tính năng Gợi ý sản phẩm thông minh (AI Recommendations) và fallback flagd:
👉 **[recommendation-integration.md](recommendation-integration.md)**

---

## ✍️ Quy ước phê duyệt
Mỗi tài liệu mô-đun trên bắt buộc phải được review và ký tên xác nhận bởi AI Lead và CDO Lead tương ứng phụ trách phần tích hợp đó trước khi đưa vào vận hành thực tế ở Tuần 2.
