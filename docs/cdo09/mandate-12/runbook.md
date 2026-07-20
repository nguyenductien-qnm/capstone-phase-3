# MANDATE-12 — Runbook kiểm chứng

## Điều kiện trước khi chạy

Dùng AWS profile có quyền read CloudTrail, IAM simulator, EventBridge, Lambda, CloudWatch Logs, và S3:

```bash
export AWS_PROFILE=804372444787_Phase3-CDO-PermissionSet
export AWS_REGION=us-east-1
export TRAIL_NAME=ecommerce-dev-audit-trail
export TRAIL_ARN=arn:aws:cloudtrail:us-east-1:804372444787:trail/ecommerce-dev-audit-trail
```

Xác nhận caller:

```bash
aws sts get-caller-identity
```

Account kỳ vọng:

```text
804372444787
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

CDO role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568 \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns "$TRAIL_ARN"
```

Mentor role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33 \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns "$TRAIL_ARN"
```

Kỳ vọng:

```text
EvalDecision = explicitDeny
```

## 3. Kiểm chứng S3 read thật có vết

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

CloudTrail data events có thể mất vài phút mới xuất hiện. Sau khi chờ, query `GetObject`.

Ví dụ:

```bash
aws cloudtrail lookup-events \
  --region "$AWS_REGION" \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetObject \
  --max-results 10
```

Các field event kỳ vọng:

```text
eventSource = s3.amazonaws.com
eventName = GetObject
readOnly = true
eventCategory = Data
```

Nếu `lookup-events` chưa thấy data events kịp thời, query CloudTrail CloudWatch log group hoặc kiểm tra log file đã deliver về S3 trong interval đã review.

## 4. Kiểm chứng coverage đọc SecretsManager

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

## 5. Kiểm chứng integrity

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

## 6. Kiểm chứng alert path

EventBridge target:

```bash
aws events list-targets-by-rule \
  --region "$AWS_REGION" \
  --rule ecommerce-dev-audit-cloudtrail-tampering
```

Lambda SQS mapping:

```bash
aws lambda list-event-source-mappings \
  --region "$AWS_REGION" \
  --function-name ecommerce-dev-audit-slack-alert
```

Lambda error metric:

```bash
aws cloudwatch get-metric-statistics \
  --region "$AWS_REGION" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=ecommerce-dev-audit-slack-alert \
  --start-time 2026-07-20T00:00:00Z \
  --end-time 2026-07-20T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

Kỳ vọng:

- EventBridge target trỏ tới `ecommerce-dev-audit-processing`.
- Lambda event source mapping là `Enabled`.
- Lambda errors bằng 0 trong verification window.

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
03-s3-getobject-event.json
04-secretsmanager-getsecretvalue.json
05-validate-logs.txt
06-alert-pipeline.json
```
