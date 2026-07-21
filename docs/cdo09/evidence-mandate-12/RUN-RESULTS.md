# MANDATE-12 runtime evidence results

- **Ngày kiểm tra gần nhất:** 21/07/2026
- **Region:** `us-east-1`
- **Trail:** `ecommerce-dev-audit-trail`

## Đã verify live

- Trail tồn tại, multi-region, ghi global service events, dùng KMS và CloudWatch Logs.
- `LogFileValidationEnabled = true`.
- Tamper-deny policy tồn tại và có `AttachmentCount = 2`.
- Policy xuất hiện trên đúng CDO và Mentor generated SSO roles.
- IAM Simulator trả `explicitDeny` cho `StopLogging`, `DeleteTrail` và `PutEventSelectors` trên cả hai role.
- Protected GitHub Actions plan/apply thành công: `5 added, 1 changed, 0 destroyed`.
- Trail đang logging; multi-region, KMS, CloudWatch Logs và log-file validation đều được cấu hình.
- Advanced Event Selectors giữ management events và bổ sung read-only S3 data events cho đúng hai bucket.
- Một lần đọc thật đã tạo event `GetObject`, `eventCategory=Data`, `managementEvent=false`, `readOnly=true`.
- EventBridge rule Mandate-12 đang `ENABLED` và target là SNS topic riêng.
- SNS có một subscription confirmed, không có pending subscription; safe email delivery đã PASS.
- `validate-logs` thành công với 2/2 digest files và 85/85 log files hợp lệ.

Raw evidence:

- `logs/03-iam-policy-attachments.json`
- `logs/04-iam-explicit-deny.json`
- `logs/01-terraform-ci-plan.txt`
- `logs/02-cloudtrail-baseline.json`
- `logs/05-cloudtrail-advanced-selectors.json`
- `logs/06-s3-getobject-event.json`
- `logs/07-m12-eventbridge-sns.json`
- `logs/08-sns-subscription.txt`
- `logs/09-cloudtrail-validation.txt`
- `logs/10-pr-jira-ci.txt`

## Change attribution

- Jira chính: `CDO-202`; subtasks: `CDO-214`, `CDO-215`, `CDO-216`.
- PR #236 được `nguyenductien-qnm` review `APPROVED` và merge vào `develop`.
- Protected workflow run `29818863006` hoàn tất thành công.

Object Lock chưa bật; đây là residual immutability gap/follow-up riêng, không được trình bày là `PASS` của control đó.

Không chạy Terraform apply local hoặc destructive CloudTrail/S3 test để tạo evidence.
