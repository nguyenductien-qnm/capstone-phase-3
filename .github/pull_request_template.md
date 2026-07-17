## 📝 Mô tả thay đổi

<!-- Viết 1-2 câu tóm tắt những gì bạn đã làm trong PR này -->

## 🔗 Liên kết Task trên Jira

- Link Jira Task: #<ID_Jira_Task>

## 🛠 Những gì đã làm

- [ ] Implement tính năng...
- [ ] Sửa lỗi...
- [ ] Đã chạy test thử ở máy cá nhân (Local Test)

## 📸 Hình ảnh / Minh chứng (nếu có)

<!-- Chèn screenshot hoặc log chạy thử thành công ở local -->

## ⚠️ Lưu ý đặc biệt đối với Reviewer

<!-- Điền những điểm cần reviewer tập trung kiểm tra hoặc lưu ý khi deploy -->

## 🔎 Change trail và audit attribution

| Trường bắt buộc | Giá trị |
|---|---|
| Change owner / implementer | |
| Reviewer độc lập | |
| Jira / Incident ID | |
| Resource và môi trường bị ảnh hưởng | |
| Before → After | |
| Blast radius / SLO impact | |
| Terraform plan hoặc Helm diff/render | |
| GitHub workflow run ID | |
| Rollback command / revert commit | |
| Evidence path (không chứa secret) | |

- [ ] Không dùng shared account; thay đổi quy được về danh tính cá nhân.
- [ ] Không chứa secret, access key, token, `terraform.tfvars` hoặc account ID đầy đủ.
- [ ] Với thay đổi hạ tầng: plan đã được review trước apply.
- [ ] Với emergency change: có incident ID, approver, thời hạn break-glass và kế hoạch reconcile về Git.
