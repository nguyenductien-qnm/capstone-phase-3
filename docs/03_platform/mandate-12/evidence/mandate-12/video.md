# MANDATE-12

## 1. Mục tiêu video


| Case | Attacker muốn làm gì? | Giải pháp của project | Evidence demo |
|---|---|---|---|
| Làm mù | Tắt hoặc làm yếu CloudTrail | IAM explicit deny; EventBridge và SNS email dự phòng | IAM Simulator trả `explicitDeny`; rule enabled; email test được nhận |
| Làm hụt | Đọc S3 object nhưng không để lại dấu vết | CloudTrail Advanced Event Selectors cho read-only S3 data events | Một `GetObject` xuất hiện với `eventCategory=Data` |
| Làm giả | Sửa, xóa hoặc chèn log/digest | CloudTrail Log File Validation và digest chain | `validate-logs` báo toàn bộ digest/log files valid |


### Giới thiệu ba case

Hiển thị bảng ở đầu file này hoặc slide có nội dung:

```text
Làm mù  → IAM Deny + EventBridge/SNS
Làm hụt → S3 Read Data Events
Làm giả → CloudTrail Log File Validation
```

Các giá trị định danh đã được redact trong tài liệu nộp mentor:

```text
<SANDBOX_SSO_PROFILE>       AWS CLI profile của người demo
<CDO_SSO_ROLE_ARN>          ARN của CDO generated SSO role
<MENTOR_SSO_ROLE_ARN>       ARN của Mentor generated SSO role
<CLOUDTRAIL_TRAIL_ARN>      ARN của ecommerce-dev-audit-trail
<MANDATE_12_SNS_TOPIC_ARN>  ARN của SNS topic Mandate-12
```

### Đăng nhập AWS trước khi demo

```bash
aws sso login \
  --profile "<SANDBOX_SSO_PROFILE>"

aws sts get-caller-identity \
  --profile "<SANDBOX_SSO_PROFILE>"
```

##  Case 1 — Làm mù audit

### Chứng minh CloudTrail vẫn logging


```bash
aws cloudtrail get-trail-status \
  --name "ecommerce-dev-audit-trail" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query '{
    IsLogging:IsLogging,
    LatestLogDelivery:LatestDeliveryTime,
    LatestDigestDelivery:LatestDigestDeliveryTime
  }'
```

>  CloudTrail vẫn đang logging. Log delivery và digest delivery đều có timestamp gần đây.

### Chứng minh IAM explicit deny
```bash
aws iam simulate-principal-policy \
  --policy-source-arn "<CDO_SSO_ROLE_ARN>" \
  --action-names \
    cloudtrail:StopLogging \
    cloudtrail:DeleteTrail \
    cloudtrail:PutEventSelectors \
  --resource-arns "<CLOUDTRAIL_TRAIL_ARN>" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'EvaluationResults[].{Action:EvalActionName,Decision:EvalDecision}'
```

Output:

```text
StopLogging       explicitDeny
DeleteTrail       explicitDeny
PutEventSelectors explicitDeny
```


> CDO routine operator bị explicit deny với các thao tác có thể làm mù hoặc làm hụt audit. Mentor role cũng đã được kiểm tra và có cùng kết quả. Dùng IAM Simulator thay vì gọi StopLogging thật để không tạo rủi ro gián đoạn audit.

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "<MENTOR_SSO_ROLE_ARN>" \
  --action-names \
    cloudtrail:StopLogging \
    cloudtrail:DeleteTrail \
    cloudtrail:PutEventSelectors \
  --resource-arns "<CLOUDTRAIL_TRAIL_ARN>" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'EvaluationResults[].{Action:EvalActionName,Decision:EvalDecision}'
```

### Chứng minh detective alert backup

Kiểm tra EventBridge rule:

```bash
aws events list-rules \
  --name-prefix "ecommerce-dev-m12-audit-tamper" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'Rules[].{Name:Name,State:State}'
```
Expected:

```text
State = ENABLED
```

Kiểm tra target:

```bash
aws events list-targets-by-rule \
  --rule "ecommerce-dev-m12-audit-tamper" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'Targets[].{Id:Id,Arn:Arn}'
```

Kiểm tra email subscription:

```bash
aws sns get-topic-attributes \
  --topic-arn "<MANDATE_12_SNS_TOPIC_ARN>" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'Attributes.{
    Confirmed:SubscriptionsConfirmed,
    Pending:SubscriptionsPending
  }'
```

Expected output:

```text
Confirmed = 1
Pending   = 0
```


> IAM deny là preventive control chính. EventBridge và SNS email là detective backup riêng của Mandate-12.

### Gửi safe email test

Chạy:

```bash
aws sns publish \
  --topic-arn "<MANDATE_12_SNS_TOPIC_ARN>" \
  --subject "MANDATE-12 safe demo" \
  --message "Safe delivery test. No audit resource was modified." \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kết quả trong video:

```text
PASS — người nhận đã nhận email có subject "MANDATE-12 safe demo".
```

##  Case 2 — Làm hụt audit

### Chứng minh S3 read selector

```bash
aws cloudtrail get-event-selectors \
  --trail-name "ecommerce-dev-audit-trail" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'AdvancedEventSelectors'
```

Output includes:

```text
ManagementEvents
S3ReadDataEvents
eventCategory = Data
resources.type = AWS::S3::Object
readOnly = true
```

> Management events vẫn được giữ. Mandate-12 bổ sung read-only S3 object data events cho CloudTrail log bucket và Terraform state bucket. Scope được giới hạn vào hai bucket để kiểm soát chi phí và alert volume.

### Tạo một GetObject an toàn

Chọn object có dữ liệu và chỉ đọc 1 byte:

```bash
export M12_OBJECT_KEY="$(aws s3api list-objects-v2 \
  --bucket ecommerce-dev-cloudtrail-logs \
  --max-keys 100 \
  --query 'Contents[?Size > `0`].Key | [0]' \
  --output text \
  --profile "<SANDBOX_SSO_PROFILE>")"

aws s3api get-object \
  --bucket ecommerce-dev-cloudtrail-logs \
  --key "$M12_OBJECT_KEY" \
  --range bytes=0-0 \
  /tmp/m12-getobject-byte \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query '{ContentLength:ContentLength,ETag:ETag}'
```

> Thực hiện một GetObject read-only và chỉ tải một byte. CloudTrail data event delivery có thể trễ vài phút, nên em sẽ dùng event thành công đã được ghi nhận trong cùng phiên kiểm chứng.

###  Hiển thị GetObject data event



```bash
aws logs filter-log-events \
  --log-group-name "/aws/cloudtrail/ecommerce-dev-audit-trail" \
  --filter-pattern '{ ($.eventSource = "s3.amazonaws.com") && ($.eventName = "GetObject") && ($.requestParameters.bucketName = "ecommerce-dev-cloudtrail-logs") }' \
  --start-time "$(date -u -d '2026-07-21T12:00:00Z' +%s000)" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --max-items 50 \
  --output json |
jq '[
  .events[].message | fromjson |
  select(.errorCode == null)
] | last | {
  eventTime,
  eventName,
  eventCategory,
  managementEvent,
  readOnly,
  bucket: .requestParameters.bucketName,
  actor: .userIdentity.sessionContext.sessionIssuer.userName
}'
```
Output includes:
```text
eventName       = GetObject
eventCategory   = Data
managementEvent = false
readOnly        = true
```

> Đây là object-level S3 read event thật. Trước Mandate-12, trail chỉ có management events nên hành vi này không có trong audit trail. Bây giờ event ghi được thời gian, actor, bucket và loại thao tác.

## Case 3 — Làm giả audit

### Chứng minh validation đang bật
```bash
aws cloudtrail get-trail \
  --name "ecommerce-dev-audit-trail" \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>" \
  --query 'Trail.{
    MultiRegion:IsMultiRegionTrail,
    LogFileValidation:LogFileValidationEnabled,
    KmsKeyId:KmsKeyId,
    S3Bucket:S3BucketName
  }'
```

Output includes:

```text
MultiRegion          = true
LogFileValidation    = true
```

###  Validate digest và log files

Chạy interval đã kiểm chứng:

```bash
aws cloudtrail validate-logs \
  --trail-arn "<CLOUDTRAIL_TRAIL_ARN>" \
  --start-time 2026-07-21T10:00:00Z \
  --end-time 2026-07-21T11:00:00Z \
  --region "us-east-1" \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Output includes:

```text
2/2 digest files valid
85/85 log files valid
```

> CloudTrail dùng các digest được ký và nối thành hash chain. Nếu log hoặc digest bị sửa, xóa hay chèn, validation sẽ phát hiện.

##  Kết luận


> Mandate-12 đã xử lý đủ ba case. Làm mù bị chặn bằng IAM explicit deny và có EventBridge/SNS email làm detective backup. Làm hụt được xử lý bằng S3 read data events. Làm giả được kiểm chứng bằng CloudTrail digest validation. Giải pháp tái sử dụng audit infrastructure hiện có, được review qua PR và deploy bằng protected GitHub Actions.


```text
Làm mù  → explicitDeny + alert email       → PASS
Làm hụt → GetObject eventCategory=Data     → PASS
Làm giả → 2/2 digest, 85/85 logs valid     → PASS
Deploy  → 5 added, 1 changed, 0 destroyed → PASS
```
