# MANDATE-12 screenshot checklist

| ID | Tên file | Nội dung bắt buộc | Không được nhầm với |
|---|---|---|---|
| 01 | `01-terraform-ci-plan.png` | GitHub plan summary, add/change/destroy, workflow run và commit | Local plan thiếu protected variables |
| 02 | `02-cloudtrail-baseline.png` | Trail logging/multi-region/KMS/validation | Chỉ chụp tên trail |
| 03 | `03-permission-set-policy.png` | Hai IAM Identity Center Permission Sets có customer-managed policy name/path | Trang generated IAM role |
| 04 | `04-iam-explicit-deny.png` | CDO và Mentor simulator đều hiện `explicitDeny` | `implicitDeny` hoặc destructive command |
| 05 | `05-cloudtrail-advanced-selectors.png` | Management selector và S3 read selector đúng hai ARN prefixes | Basic selector có `DataResources = []` |
| 06 | `06-s3-getobject-event.png` | Event `GetObject`, `eventCategory=Data`, actor, bucket/key và timestamp | `lookup-events` management-only |
| 07 | `07-m12-eventbridge-sns.png` | Rule M12 enabled, SNS target và subscription confirmed | Lambda/Slack pipeline Mandate-11 |
| 08 | `08-m12-email-delivery.png` | Safe test email có topic/source và timestamp | Email subscription confirmation đơn thuần |
| 09 | `09-cloudtrail-validation.png` | `validate-logs` không có invalid digest/log | Chỉ chụp validation enabled |
| 10 | `10-pr-jira-ci.png` | PR, Jira, reviewer approval và successful workflow | PR chưa review hoặc run cũ |

## Redaction

- Che account ID đầy đủ nếu không cần cho acceptance.
- Che email receiver và thông tin cá nhân không cần thiết.
- Không che role name, policy name, action, decision, timestamp hoặc event ID dùng để chứng minh.
- Ảnh IAM role user đã cung cấp có full account ID và chỉ chứng minh generated-role attachment; không commit nguyên ảnh đó như Permission Set evidence.
