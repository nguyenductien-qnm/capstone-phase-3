# Hợp Đồng Tích Hợp Dịch Vụ: Shopping Copilot Agent

* **Dịch vụ tích hợp:** `shopping-copilot` (Python gRPC Server)
* **Nhóm sở hữu:** AI Team (AIO03) & Platform/Storefront Team (CDO05/CDO09)
* **Người phê duyệt:** [AI Lead Name] & [CDO Lead Name]
* **Trạng thái:** Draft | Accepted
* **Ngày cập nhật:** YYYY-MM-DD

---

## 1. Giao Tiếp API (gRPC) & Định Tuyến (Routing)
- Dịch vụ **Shopping Copilot** (Python gRPC Server) sẽ chạy ở cổng: `50051` (gRPC).
- **CDO Storefront cam kết:** Cấu hình Envoy Proxy (`frontend-proxy`) để định tuyến các cuộc gọi gRPC-Web từ client của storefront đến cổng `50051` của pod `shopping-copilot` trong cluster.
- **Protobuf Contract:** Định nghĩa dịch vụ gRPC được lưu trữ tại `techx-corp-platform/proto/shopping_copilot.proto`. Hai bên cam kết không tự ý sửa đổi file proto này.

---

## 2. Giới Hạn Tài Nguyên (Kubernetes Resource Limits)
Thống nhất giới hạn tài nguyên cho pod `shopping-copilot` trên môi trường EKS:
- **CPU:** Request: `200m` · Limit: `1000m`
- **Memory:** Request: `256Mi` · Limit: `1024Mi`
- **Replicas:** Minimum: `1` · Maximum: `3` (Autoscaling dựa trên CPU usage > 80%).

---

## 3. Cổng Bảo Mật Xác Nhận (Confirmation Gate)
- Hai bên thống nhất cơ chế **Confirmation Gate** ở giao diện người dùng Storefront:
  - Khi trợ lý AI quyết định thực hiện hành động thêm sản phẩm vào giỏ hàng (`add_to_cart`), nó **chỉ** được phép trả về trạng thái yêu cầu xác nhận.
  - Giao diện Storefront sẽ hiển thị nút bấm Xác nhận.
  - Chỉ khi người dùng bấm nút Xác nhận hoặc nhập tin nhắn Đồng ý, hành động `add_to_cart` mới được thực thi thật dưới DB.
