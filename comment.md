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
| Change owner / implementer | Lê Kim Dũng (03 lê kim dũng) |
| Reviewer độc lập | Nguyễn Hữu Định (AI Lead) |
| Jira / Incident ID | TF1-94, TF1-74 |
| Resource và môi trường bị ảnh hưởng | Service `llm`, `shopping-copilot` |
| Before → After | Pass rate 40% → 96.0% (EKS Live + ML-Guard) |
| Blast radius / SLO impact | Low |
| Terraform plan hoặc Helm diff/render | N/A |
| GitHub workflow run ID | N/A |
| Rollback command / revert commit | git revert HEAD |
| Evidence path (không chứa secret) | docs/ai/04_eval_report.md, docs/ai/TF1-94-EVIDENCE.md |

- [x] Không dùng shared account; thay đổi quy được về danh tính cá nhân.
- [x] Không chứa secret, access key, token, `terraform.tfvars` hoặc account ID đầy đủ.
- [x] Với thay đổi hạ tầng: plan đã được review trước apply.
- [x] Với emergency change: có incident ID, approver, thời hạn break-glass và kế hoạch reconcile về Git.
