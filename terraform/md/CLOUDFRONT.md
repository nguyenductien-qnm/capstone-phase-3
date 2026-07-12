# Cấu hình CloudFront CDN - E-commerce Infrastructure

Tài liệu này mô tả chi tiết cấu hình CDN CloudFront được triển khai tự động qua Terraform để phục vụ phân phối lưu lượng và tăng tốc kết nối cho ứng dụng E-commerce.

---

## 1. Cấu hình Origin (Trỏ về EKS NLB)

* **Origin Domain**: Liên kết trực tiếp tới địa chỉ DNS công cộng của Network Load Balancer (NLB) do EKS tự động sinh ra.
* **Giao thức kết nối (Custom Origin Config)**:
  - Cổng hỗ trợ: HTTP cổng `80` và HTTPS cổng `443`.
  - Chính sách giao thức (`origin_protocol_policy`): Cấu hình `match-viewer` (Tự động khớp giao thức HTTP/HTTPS của Client khi gửi yêu cầu tới EKS).

---

## 2. Tối ưu hóa API & Dynamic Traffic (No Caching)

Vì hệ thống microservices chủ yếu xử lý các API động (như giỏ hàng, thanh toán, thông tin tài khoản), CloudFront được cấu hình tối ưu:
* **Tắt Cache**: Đặt `min_ttl = 0`, `default_ttl = 0`, `max_ttl = 0`. Đảm bảo mọi request luôn được chuyển thẳng về EKS xử lý, không bị lưu cache cũ.
* **Chuyển tiếp Headers & Cookies**:
  - Chuyển tiếp toàn bộ Headers (`headers = ["*"]`), đặc biệt là header `Host` và `Authorization` (chứa JWT Token xác thực).
  - Chuyển tiếp toàn bộ Cookies (`forward = "all"`).

---

## 3. Tích hợp Custom Domain & SSL (HTTPS)

* **Custom Domain (Aliases)**: Phân phối lưu lượng qua tên miền phụ chính thức của bạn (ví dụ: `api.yourdomain.com`).
* **Chứng chỉ SSL (ACM)**: Liên kết với chứng chỉ SSL Wildcard (`*.yourdomain.com`) được tự động cấp và xác thực bởi AWS ACM ở region `us-east-1`.
* **Ép HTTPS**: Bật viewer protocol policy `redirect-to-https`. Mọi truy cập không bảo mật qua HTTP sẽ tự động chuyển hướng sang HTTPS.

---

## 4. Tự động hóa bản ghi DNS (Route 53 Record)

* **Bản ghi Alias**: Hệ thống tự động tạo bản ghi loại `A` (Alias) trên Route 53 trỏ tên miền phụ `api.yourdomain.com` về DNS mặc định của CloudFront (`*.cloudfront.net`).
* **Lợi ích**: Tốc độ phân giải DNS cực nhanh, miễn phí truy vấn bản ghi Alias nội bộ AWS, không cần cập nhật IP thủ công khi CloudFront đổi địa chỉ.

---

## 5. Tham số Cấu hình trong `terraform.tfvars`

Các biến cấu hình CloudFront và Domain chính được quản lý tập trung:
```hcl
# Tên miền NLB của EKS (Thay thế sau khi EKS khởi chạy và tạo NLB thành công)
nlb_dns_name = "mock-eks-nlb-dns-placeholder.amazonaws.com"

# Cấu hình Custom Domain
domain_name = "yourdomain.com"
subdomain   = "api.yourdomain.com"
```
