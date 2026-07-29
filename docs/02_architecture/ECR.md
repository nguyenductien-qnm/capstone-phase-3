# Cấu hình ECR (Elastic Container Registry) - E-commerce Infrastructure

Tài liệu này mô tả chi tiết cấu hình kho lưu trữ container images (ECR) được triển khai tự động qua Terraform.

---

## 1. Cơ chế Tạo động Repositories (Dynamic Repositories)

* **Tự động hóa**: Module sử dụng vòng lặp `for_each` để khởi tạo hàng loạt kho lưu trữ ECR từ danh sách khai báo tại biến root.
* **Cấu hình động**: Danh sách các tên repositories được khai báo trong `terraform.tfvars` hoặc truyền qua biến môi trường của CI/CD. Điều này giúp tách biệt cấu trúc code infra và tên của các microservice thực tế.

---

## 2. Các lớp bảo mật tích hợp (Security Features)

* **Image Scanning**: Bật tự động quét ảnh (`scan_on_push = true`). Khi CI/CD đẩy image lên, AWS sẽ tự động phân tích và phát hiện các lỗ hổng bảo mật (CVE) trong hệ điều hành hoặc các gói thư viện của container.
* **Mã hóa (Encryption)**: Dữ liệu image lưu trữ được mã hóa tĩnh mặc định sử dụng khóa KMS do AWS quản lý dành riêng cho ECR (`KMS` encryption type).

---

## 3. Ngăn chặn vô tình xóa dữ liệu (Deletion Protection)

* **Cấu hình**: Bật block `lifecycle { prevent_destroy = true }` cho toàn bộ ECR repositories.
* **Lợi ích**: Bảo vệ các Docker image đã build và push từ trước. Khi chạy lệnh `terraform destroy` hạ tầng, Terraform sẽ từ chối xóa ECR để tránh việc bạn phải mất thời gian build/push lại hàng chục GB image.
* **Cách xóa thủ công**: Nếu thực sự muốn xóa ECR, bạn phải chạy lệnh `terraform state rm module.ecr` để đưa ECR ra ngoài quản lý của Terraform trước khi chạy `destroy`, hoặc xóa trực tiếp trên AWS Console.

---

## 4. Tối ưu hóa chi phí lưu trữ (Lifecycle Policy)

* **Vấn đề**: Mỗi lần build code mới sẽ tạo ra một image mới. Nếu lưu tất cả, dung lượng ECR sẽ phình to và tốn rất nhiều tiền lưu trữ ($0.09 / GB / tháng).
* **Cấu hình dọn dẹp tự động**:
  - Đặt giới hạn tối đa **10 images** gần nhất cho mỗi repository (`countNumber = 10`).
  - Khi đẩy bản build thứ 11 lên, AWS sẽ tự động xóa bản build cũ nhất (bản thứ 1) đi.

---

## 5. Tham số Cấu hình trong `terraform.tfvars`

Các biến cấu hình ECR chính được quản lý tập trung (mặc định để trống để CI/CD tự truyền danh sách tên repo khi chạy):
```hcl
ecr_repositories = []
```
