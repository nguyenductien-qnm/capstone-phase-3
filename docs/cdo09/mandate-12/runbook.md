# MANDATE-12 — Runbook kiểm chứng

## Điều kiện trước khi chạy

Dùng AWS profile có quyền read CloudTrail, IAM simulator, EventBridge, SNS, CloudWatch Logs, và S3:

```bash
export AWS_PROFILE="<SANDBOX_SSO_PROFILE>"
export SANDBOX_ACCOUNT_ID="<SANDBOX_ACCOUNT_ID>"
export AWS_REGION=us-east-1
export TRAIL_NAME=ecommerce-dev-audit-trail
export TRAIL_ARN="arn:aws:cloudtrail:${AWS_REGION}:${SANDBOX_ACCOUNT_ID}:trail/${TRAIL_NAME}"
export CLOUDTRAIL_LOG_GROUP="/aws/cloudtrail/${TRAIL_NAME}"
```

Xác nhận caller:

```bash
aws sts get-caller-identity
```

Account kỳ vọng:

```text
<SANDBOX_ACCOUNT_ID>
```

## 1. Kiểm chứng CloudTrail selectors

```bash
aws cloudtrail get-event-selectors \
  --region "$AWS_REGION" \
  --trail-name "$TRAIL_NAME"
```

Kỳ vọng:

- Có `AdvancedEventSelectors`.
- Một selector cover management events.
- Một selector cover read-only S3 object data events.
- S3 data event prefixes gồm:
  - `arn:aws:s3:::ecommerce-dev-cloudtrail-logs/`
  - `arn:aws:s3:::terraform-state-phase-3/`

## 2. Kiểm chứng IAM deny cho audit tampering

Kiểm tra policy xuất hiện trên hai generated roles:

```bash
aws iam list-attached-role-policies \
  --role-name AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568

aws iam list-attached-role-policies \
  --role-name AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33
```

Kỳ vọng cả hai output có `ecommerce-dev-audit-log-tamper-deny`. Kết quả này chứng minh enforcement trên generated roles; bằng chứng policy được quản lý tại Permission Set cần screenshot/config từ adminHolder vì CDO role không có quyền đọc IAM Identity Center.

CDO role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::${SANDBOX_ACCOUNT_ID}:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568" \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns "$TRAIL_ARN"
```

Mentor role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::${SANDBOX_ACCOUNT_ID}:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33" \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns "$TRAIL_ARN"
```

Kỳ vọng:

```text
EvalDecision = explicitDeny
```

## 3. Kiểm chứng Mandate-12 email alert path

Kiểm tra EventBridge rule riêng:

```bash
aws events list-rules \
  --region "$AWS_REGION" \
  --name-prefix ecommerce-dev-m12
```

Kỳ vọng:

- Rule tồn tại.
- Rule ở trạng thái `ENABLED`.
- Event pattern bắt các CloudTrail tamper actions:
  - `StopLogging`
  - `DeleteTrail`
  - `UpdateTrail`
  - `PutEventSelectors`
  - `PutInsightSelectors`
- Event pattern bắt thêm IAM guardrail tamper actions, chỉ khi `requestParameters.policyArn` trỏ đúng policy Mandate-12:
  - `DetachRolePolicy`
  - `DeletePolicy`
  - `DeletePolicyVersion`
  - `CreatePolicyVersion`
  - `SetDefaultPolicyVersion`
- Event pattern bắt thao tác gỡ customer-managed policy khỏi IAM Identity Center Permission Set, chỉ khi reference có tên `ecommerce-dev-audit-log-tamper-deny` và path `/`:
  - `DetachCustomerManagedPolicyReferenceFromPermissionSet`

Ba nhóm source/action được tách bằng `$or` để tránh ghép chéo `eventSource` và `eventName`, đồng thời không gửi email cho mọi thay đổi IAM trong account.

Kiểm tra target của rule:

```bash
aws events list-targets-by-rule \
  --region "$AWS_REGION" \
  --rule "<m12-eventbridge-rule-name>"
```

Kỳ vọng:

- Target trỏ tới SNS topic riêng của Mandate-12.
- Không trỏ tới Lambda/SQS pipeline của Mandate-11.

Kiểm tra SNS subscription:

```bash
aws sns list-subscriptions-by-topic \
  --region "$AWS_REGION" \
  --topic-arn "<m12-sns-topic-arn>"
```

Kỳ vọng:

```text
SubscriptionArn != PendingConfirmation
```

Nếu subscription vẫn pending:

1. Người nhận email mở email từ AWS Notifications.
2. Bấm confirm subscription.
3. Chạy lại `list-subscriptions-by-topic`.

## 4. Kiểm chứng S3 read thật có vết

Đọc một object có sẵn từ CloudTrail bucket:

```bash
KEY=$(aws s3api list-objects-v2 \
  --bucket ecommerce-dev-cloudtrail-logs \
  --max-items 1 \
  --query 'Contents[0].Key' \
  --output text)

aws s3api get-object \
  --bucket ecommerce-dev-cloudtrail-logs \
  --key "$KEY" \
  /tmp/m12-test-object
```

CloudTrail data events có thể mất vài phút mới xuất hiện. `aws cloudtrail lookup-events` không trả data events, nên query CloudTrail CloudWatch log group.

Ví dụ:

```bash
aws logs filter-log-events \
  --region "$AWS_REGION" \
  --log-group-name "$CLOUDTRAIL_LOG_GROUP" \
  --filter-pattern '{ ($.eventSource = "s3.amazonaws.com") && ($.eventName = "GetObject") && ($.eventCategory = "Data") }' \
  --max-items 20
```

Các field event kỳ vọng:

```text
eventSource = s3.amazonaws.com
eventName = GetObject
readOnly = true
eventCategory = Data
```

Nếu CloudWatch Logs chưa thấy event sau delivery delay, kiểm tra CloudTrail log file đã deliver về S3 trong interval đã review. Không dùng `lookup-events` làm evidence cho S3 data events.

## 5. Kiểm chứng coverage đọc SecretsManager

```bash
aws cloudtrail lookup-events \
  --region "$AWS_REGION" \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --max-results 10
```

Kỳ vọng:

```text
eventSource = secretsmanager.amazonaws.com
eventName = GetSecretValue
eventCategory = Management
readOnly = true
```

## 6. Kiểm chứng integrity

Dùng interval nhỏ đã review:

```bash
aws cloudtrail validate-logs \
  --trail-arn "$TRAIL_ARN" \
  --start-time 2026-07-20T02:00:00Z \
  --end-time 2026-07-20T03:00:00Z
```

Kỳ vọng:

```text
digest files valid
log files valid
```

## 7. Evidence cần capture

Với mỗi command, capture:

- timestamp;
- operator identity;
- command;
- output;
- trạng thái đạt/chưa đạt;
- screenshot hoặc raw log path khi cần.

Tên evidence khuyến nghị:

```text
01-event-selectors.json
02a-iam-deny-cdo.json
02b-iam-deny-mentor.json
03a-eventbridge-rule.json
03b-eventbridge-targets.json
03c-sns-subscription.json
04-s3-getobject-event.json
05-secretsmanager-getsecretvalue.json
06-validate-logs.txt
```

## 8. Rollback/destroy verification nếu cần gỡ Mandate-12

Rollback phải đi qua revert PR và Terraform plan đảo ngược.

Kỳ vọng khi review rollback plan:

- Chỉ gỡ EventBridge rule/SNS topic/subscription riêng của Mandate-12.
- Chỉ detach deny policy khỏi CDO/Mentor SSO roles nếu đó là mục tiêu rollback đã được approve.
- Chỉ remove S3 read data event selector nếu đó là mục tiêu rollback đã được approve.
- Không destroy CloudTrail trail, S3 log bucket, KMS key, hoặc Mandate-11 audit-detection resources.
