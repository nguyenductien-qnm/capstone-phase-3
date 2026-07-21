# MANDATE-12 — Audit Anti-Defeat

## Tóm tắt

Mandate-12 yêu cầu team chứng minh audit trail trên AWS không thể bị đánh bại bởi ba đòn:

1. **Làm mù** — tắt hoặc làm yếu đường ghi log.
2. **Làm hụt** — đọc dữ liệu nhạy cảm ở nơi không có audit event.
3. **Làm giả/sửa** — sửa, xóa, hoặc chèn bằng chứng audit mà không bị phát hiện.

Thư mục này chứa kế hoạch triển khai và runbook kiểm chứng cho Product-like/Sandbox account.

## Phạm vi hiện tại

```text
AWS account: 804372444787
Region: us-east-1
CloudTrail: ecommerce-dev-audit-trail
CloudTrail bucket: ecommerce-dev-cloudtrail-logs
Terraform state bucket: terraform-state-phase-3
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
| EventBridge/SQS/Lambda alert pipeline | Tồn tại và đang enabled; receiver bên ngoài chưa dùng làm điều kiện pass |
| SecretsManager `GetSecretValue` | Được ghi là CloudTrail management event |
| S3 object read data events | Thiếu trước thay đổi này |
| IAM deny cho CDO/Mentor audit tamper | Thiếu trước thay đổi này |

## Thay đổi dự kiến

1. Chuyển CloudTrail selector từ `event_selector` cơ bản sang `advanced_event_selector`.
2. Giữ nguyên coverage cho management events.
3. Thêm read-only S3 object data events cho:
   - `arn:aws:s3:::ecommerce-dev-cloudtrail-logs/`
   - `arn:aws:s3:::terraform-state-phase-3/`
4. Attach audit tamper-deny policy hiện có vào CDO và Mentor SSO roles bằng Terraform như một workaround tạm thời.
5. Tài liệu hóa retention, lệnh verify, và các giới hạn đã biết.

## Tài liệu

- [Kế hoạch triển khai](implementation-plan.md)
- [Runbook kiểm chứng](runbook.md)
- [Việc cần người ngoài/adminHolder hỗ trợ](external-actions.md)

## Giới hạn quan trọng

Attach trực tiếp policy vào `AWSReservedSSO_*` roles là workaround để kịp deadline. Control bền vững hơn là adminHolder hoặc IAM Identity Center owner attach deny policy ở cấp Permission Set, hoặc áp dụng guardrail tương đương nằm ngoài quyền routine operator.
