# MANDATE-12 runtime evidence results

- **Ngày kiểm tra gần nhất:** 20/07/2026
- **Region:** `us-east-1`
- **Trail:** `ecommerce-dev-audit-trail`

## Đã verify live

- Trail tồn tại, multi-region, ghi global service events, dùng KMS và CloudWatch Logs.
- `LogFileValidationEnabled = true`.
- Tamper-deny policy tồn tại và có `AttachmentCount = 2`.
- Policy xuất hiện trên đúng CDO và Mentor generated SSO roles.
- IAM Simulator trả `explicitDeny` cho `StopLogging`, `DeleteTrail` và `PutEventSelectors` trên cả hai role.
- CDO role không có quyền `sso:ListInstances`; Permission Set ownership cần adminHolder/console evidence.

Raw evidence:

- `logs/03-iam-policy-attachments.json`
- `logs/04-iam-explicit-deny.json`

## Chưa deploy hoặc chưa verify

- AWS runtime hiện vẫn dùng basic management selector với `DataResources = []`.
- M12 EventBridge rule/SNS topic chưa tồn tại trên AWS.
- SNS email subscription chưa được tạo/confirm.
- Chưa capture actual S3 `GetObject` data event sau advanced selector.
- Chưa có protected Terraform plan/apply của implementation.

## Required path to full pass

1. Review và merge PR vào `develop`.
2. Review Terraform plan từ GitHub Actions.
3. Infrastructure owner approve protected Sandbox apply.
4. Người nhận confirm SNS email subscription.
5. Capture advanced selectors và actual S3 `GetObject` event.
6. Verify EventBridge/SNS configuration và safe email delivery.
7. Re-run `validate-logs` với `--start-time` và `--end-time`.
8. Lưu raw outputs đã redact vào `logs/`, bổ sung screenshots cần thiết.
9. Liên kết PR, reviewer, workflow run và Jira.
10. Chỉ sau đó đổi các acceptance tương ứng thành `PASS`.

Không chạy Terraform apply local hoặc destructive CloudTrail/S3 test để tạo evidence.
