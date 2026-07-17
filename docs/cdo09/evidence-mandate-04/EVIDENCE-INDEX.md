# MANDATE-04 evidence index

Evidence dưới đây là output thật đã redact, được thu ngày 15/07/2026. Trạng thái runtime không tự động trở thành PASS chỉ vì file tồn tại; xem [RUN-RESULTS.md](RUN-RESULTS.md) và [AUDIT-REVIEW-2026-07-16.md](AUDIT-REVIEW-2026-07-16.md).

| ID | Acceptance | Status gần nhất | Raw evidence |
|---|---|---|---|
| 01 | Terraform init/validate | PASS (15/07); re-test local PASS (16/07) | `logs/01b-terraform-init.txt`, `logs/01-terraform-validate.txt` |
| 02 | Terraform plan đúng scope | BLOCKED | `logs/02-plan-diagnostic-missing-vars.txt` |
| 03 | EKS `api/audit/authenticator` | PASS lịch sử | `logs/03-eks-audit-enabled.json` |
| 04 | Audit stream, retention ≥30 ngày, KMS | PARTIAL; runtime cũ 7 ngày, chưa KMS | `logs/04a-cloudwatch-log-group.json`, `logs/04b-cloudwatch-audit-stream.json` |
| 05 | Timeline create/patch/delete có actor/audit ID | PASS lịch sử | `logs/05-k8s-forensic-timeline.json`, `queries/05-k8s-forensic-timeline-used.txt` |
| 06 | CloudTrail logging/multi-region/global/selectors | PASS lịch sử | `logs/06a-cloudtrail-status.json`, `logs/06b-cloudtrail-configuration.json`, `logs/06c-cloudtrail-event-selectors.json` |
| 07 | Danh tính cá nhân và GitHub actor/run | PARTIAL | `logs/07-cloudtrail-user-identity.json`, `queries/07-cloudtrail-github-session.txt` |
| 08 | S3 versioning/encryption/public block | FAIL lịch sử: chưa versioning | `logs/08-s3-protection-summary.json`, `logs/08b-s3-public-access-block.json`, `logs/08c-s3-encryption.json`, `logs/08d-s3-object-lock.json` |
| 09 | `cloudtrail validate-logs` | PASS lịch sử | `logs/09-cloudtrail-validation.txt` |
| 10 | PR/Jira/reviewer/CI | PARTIAL: PR #93 có, chưa approval/remote re-run | `logs/10-pr-search.json`; PR #93 |
| 11 | ArgoCD revision → commit → PR → Jira | PASS lịch sử | `logs/11a-argocd-applications.txt`, `logs/11b-git-pr-correlation.json` |
| 12 | Operator tamper actions = `explicitDeny` | FAIL lịch sử | `logs/12a-audit-tamper-policies.json` đến `logs/12e-current-role-s3-simulation.json` |

Không có screenshot thật trong repository tại thời điểm review; owner chụp theo `screenshots/README.md`. Sáu raw log chứa account ID đã được thay bằng `<ACCOUNT_ID_REDACTED>` ngày 16/07/2026; event, quyết định và kết quả validation không bị sửa.
