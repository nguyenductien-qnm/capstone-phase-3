# Change management runbook — CDO-105

## Standard change

```text
Jira → branch → semantic commit → Pull Request → review → CI checks
→ Terraform plan/Helm render → merge → GitHub Actions → Terraform/ArgoCD
→ verification → evidence
```

Không dùng shared account và không push trực tiếp vào nhánh bảo vệ. Jira ID phải có trong branch/PR; PR ghi owner, resource, risk, blast radius, plan/diff, test, rollback, SLO và audit evidence. Reviewer phê duyệt trên GitHub. GitHub Environment bảo vệ apply; ArgoCD triển khai revision đã merge. Hoàn tất record theo [change-log-template.md](change-log-template.md).

## Emergency change

1. Mở Jira/change record loại `emergency`, ghi lý do, incident ID, người phê duyệt và thời hạn.
2. Ưu tiên PR nhanh có review. Chỉ dùng break-glass danh tính cá nhân khi GitOps không đáp ứng thời gian khôi phục.
3. Trước `kubectl`, ghi UTC/ICT, caller identity, command đã redact, target và expected result. Dùng terminal transcript bảo mật; không lưu token.
4. Chạy lệnh nhỏ nhất, xác minh SLO, rồi đưa thay đổi tương đương vào Git/PR ngay sau phục hồi để loại drift.
5. Thu hồi phiên break-glass, đính CloudTrail/Kubernetes audit ID và làm retrospective.

Ví dụ ghi `kubectl` khẩn cấp: `aws sts get-caller-identity`; `date -u`; lưu command, namespace/resource và Jira vào change record. Không dùng application/flagd làm forensic demo.

## Correlation

1. Query EKS audit theo time/resource; lưu `auditID`, `user.username`, `verb`, `objectRef`, `sourceIPs`, `userAgent`.
2. Với ArgoCD, lấy `kubectl -n argocd get application <app> -o jsonpath='{.status.sync.revision}'`. K8s actor thường là ArgoCD service account.
3. `git show <revision>` xác định file/commit; liên kết commit tới PR; PR bắt buộc có Jira và review.
4. Với AWS, CloudTrail assumed-role session `gha-<actor>-<run_id>` xác định người và run. Run metadata cho repository, workflow, SHA và PR. GitHub login tối đa 39 ký tự nên chuỗi này nằm trong giới hạn session 64 ký tự với run ID hiện hành.

## Rollback

- GitOps: revert commit qua PR, chờ ArgoCD sync và xác minh health/SLO.
- Terraform: tạo revert PR, review plan đảo ngược rồi người có thẩm quyền chạy apply; không sửa state thủ công.
- Emergency Kubernetes: dùng command rollback đã duyệt, rồi reconcile Git ngay.

Break-glass chỉ dùng role riêng, MFA/approval theo quy định tổ chức, session ngắn và alert; không dùng shared user. Audit admin kiểm tra log sau sự kiện. Policy tamper-deny không được gỡ trong lúc xử lý; nếu chính pipeline audit hỏng, admin ghi dual approval và toàn bộ CloudTrail evidence.
