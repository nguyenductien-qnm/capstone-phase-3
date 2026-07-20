# MANDATE-12 — Audit Anti-Defeat

## Tóm tắt

Mandate-12 yêu cầu team chứng minh audit trail trên AWS không thể bị đánh bại bởi ba đòn:

1. **Làm mù** — tắt hoặc làm yếu đường ghi log.
2. **Làm hụt** — đọc dữ liệu nhạy cảm ở nơi không có audit event.
3. **Làm giả/sửa** — sửa, xóa, hoặc chèn bằng chứng audit mà không bị phát hiện.

Thư mục này chứa kế hoạch triển khai và runbook kiểm chứng cho Product-like/Sandbox account.

## Phạm vi hiện tại

```text
AWS account: <SANDBOX_ACCOUNT_ID>
Region: us-east-1
CloudTrail: ecommerce-dev-audit-trail
CloudTrail bucket: ecommerce-dev-cloudtrail-logs
Terraform state bucket: terraform-state-phase-3
```

## Architecture Mandate-12

```text
CloudTrail tamper hoặc IAM guardrail tamper attempt
        |
        +--> IAM explicitDeny chặn request
        |
        +--> CloudTrail ghi API event / AccessDenied
                 |
                 v
             EventBridge rule riêng Mandate-12
                 |
                 v
             SNS topic riêng Mandate-12
                 |
                 v
             Email người nhận từ GitHub secret/env
```

## Runtime facts đã verify

| Hạng mục | Trạng thái |
|---|---|
| CloudTrail logging | Đang bật |
| Multi-region/global events | Đang bật |
| KMS encryption | Đang bật |
| CloudWatch integration | Đang bật |
| Log file validation | Đang bật |
| Integrity validation | Đã pass trên interval đã kiểm tra |
| SecretsManager `GetSecretValue` | Được ghi là CloudTrail management event |
| S3 object read data events | Thiếu trước thay đổi này |
| IAM deny cho CDO/Mentor audit tamper | Đã verify live: policy có 2 attachments; cả hai role trả `explicitDeny` |
| Mandate-12 email alert path | Thiếu trước thay đổi này |
| S3 Object Lock | Chưa bật; có thể bật trên bucket hiện hữu nhưng là thay đổi không thể đảo ngược và cần review riêng |

## Thay đổi dự kiến

1. Chuyển CloudTrail selector từ `event_selector` cơ bản sang `advanced_event_selector`.
2. Giữ nguyên coverage cho management events.
3. Thêm read-only S3 object data events cho:
   - `arn:aws:s3:::ecommerce-dev-cloudtrail-logs/`
   - `arn:aws:s3:::terraform-state-phase-3/`
4. AdminHolder attach audit tamper-deny policy ở cấp CDO và Mentor IAM Identity Center Permission Sets; Terraform không quản lý trực tiếp generated SSO roles.
5. Tạo EventBridge rule và SNS email topic riêng cho Mandate-12, bắt CloudTrail tamper và IAM guardrail tamper.
6. Tài liệu hóa retention, lệnh verify, và các giới hạn đã biết.

## Rollout

1. Validate static cho cả `develop` và `sandbox`.
2. Giữ `develop` default off; không runtime test Mandate-12 ở develop nếu chưa có role/bucket/email config riêng.
3. Chạy sandbox plan/apply qua GitHub Actions protected workflow.
4. Verify Mandate-12 trên sandbox với đúng CDO/Mentor roles và bucket thật.

Không copy role names hoặc bucket ARNs của sandbox sang develop nếu develop dùng account/resource khác.

## Tài liệu

- [Kế hoạch triển khai](implementation-plan.md)
- [Runbook kiểm chứng](runbook.md)
- [Việc cần người ngoài/adminHolder hỗ trợ](external-actions.md)

## Giới hạn quan trọng

- IAM deny được adminHolder quản lý ở cấp IAM Identity Center Permission Set. Runtime đã xác nhận policy xuất hiện trên đúng hai generated roles và IAM Simulator trả `explicitDeny`; CDO role không có quyền tự đọc cấu hình Permission Set nên bằng chứng ownership cần xác nhận từ adminHolder/console.
- Permission Set control vẫn không phải anti-defeat tuyệt đối trước Identity Center/Organizations administrator. SCP hoặc guardrail nằm ngoài quyền routine operator là follow-up mạnh hơn nếu threat model yêu cầu.
- Object Lock có thể bật trên bucket hiện hữu có versioning. Tuy nhiên, việc bật không thể đảo ngược; default retention chỉ áp dụng cho object mới, còn object cũ cần retention riêng. Vì vậy thay đổi này được defer sang review/risk approval riêng, không phải vì AWS không hỗ trợ.
- Mandate-12 không tái sử dụng Lambda/Slack pipeline của Mandate-11/CDO-05.
- Email người nhận cho SNS không hardcode trong repo; giá trị nằm trong GitHub secret/env `MANDATE_12_ALERT_EMAIL` và workflow map sang `TF_VAR_mandate_12_alert_email`.
- Rollback/destroy của alert path độc lập: gỡ EventBridge rule, SNS topic/subscription riêng của Mandate-12 mà không chạm Mandate-11.
