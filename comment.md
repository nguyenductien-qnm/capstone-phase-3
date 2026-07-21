## 📝 Mô tả thay đổi

Sửa lỗi phiên bản `openfeature-sdk==0.5.1` không tồn tại bằng cách cập nhật lên `0.6.0` (trigger CI để pass lỗi pipeline).

## 🔗 Liên kết Task trên Jira

- Link Jira Task: N/A

## 🛠 Những gì đã làm

- [x] Sửa lỗi version `openfeature-sdk` trong `llm/requirements.txt`
- [x] Đã chạy test thử ở máy cá nhân (Local Test)

## 🔎 Change trail và audit attribution

| Trường bắt buộc | Giá trị |
|---|---|
| Change owner / implementer | dinh144 (Gemini AI) |
| Reviewer độc lập | |
| Jira / Incident ID | N/A |
| Resource và môi trường bị ảnh hưởng | Service `llm` |
| Before → After | `openfeature-sdk==0.5.1` → `0.6.0` |
| Blast radius / SLO impact | Low |
| Terraform plan hoặc Helm diff/render | N/A |
| GitHub workflow run ID | N/A |
| Rollback command / revert commit | N/A |
| Evidence path (không chứa secret) | N/A |

- [x] Không dùng shared account; thay đổi quy được về danh tính cá nhân.
- [x] Không chứa secret, access key, token, `terraform.tfvars` hoặc account ID đầy đủ.
- [x] Với thay đổi hạ tầng: plan đã được review trước apply.
- [x] Với emergency change: có incident ID, approver, thời hạn break-glass và kế hoạch reconcile về Git.
