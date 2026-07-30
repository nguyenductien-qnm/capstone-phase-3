# MANDATE-12 evidence index

Evidence phải là output thật đã redact. Trạng thái runtime không tự động thành `PASS` chỉ vì file tồn tại; xem [RUN-RESULTS.md](RUN-RESULTS.md).

| ID | Acceptance | Trạng thái gần nhất | Raw evidence dự kiến |
|---|---|---|---|
| 01 | Terraform/CI plan đúng scope, không destroy audit resources | PASS; plan/apply `5 add, 1 change, 0 destroy` | `logs/01-terraform-ci-plan.txt` |
| 02 | Trail logging, multi-region, KMS, validation enabled | PASS | `logs/02-cloudtrail-baseline.json` |
| 03 | Policy attach vào CDO và Mentor generated roles | PASS enforcement; attachment count 2 | `logs/03-iam-policy-attachments.json` |
| 04 | CDO và Mentor audit tamper actions = `explicitDeny` | PASS | `logs/04-iam-explicit-deny.json` |
| 05 | Management + S3 read Advanced Event Selectors | PASS | `logs/05-cloudtrail-advanced-selectors.json` |
| 06 | Actual S3 `GetObject` data event | PASS | `logs/06-s3-getobject-event.json` |
| 07 | M12 EventBridge rule và SNS target/policy | PASS | `logs/07-m12-eventbridge-sns.json` |
| 08 | SNS subscription confirmed và email delivery | PASS | `logs/08-sns-subscription.txt` |
| 09 | CloudTrail digest/log validation | PASS; 2/2 digest và 85/85 log hợp lệ | `logs/09-cloudtrail-validation.txt` |
| 10 | PR, Jira, reviewer và GitHub workflow attribution | PASS | `logs/10-pr-jira-ci.txt` |

Screenshot checklist: [screenshots/README.md](screenshots/README.md).
