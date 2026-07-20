# MANDATE-12 — Kế hoạch triển khai Audit Anti-Defeat

## 1. Mục tiêu

Mandate-12 yêu cầu chứng minh audit trail không thể bị đánh bại theo ba hướng:

1. **Làm mù** — attacker/admin không được tắt hoặc làm yếu đường ghi log mà không bị chặn hoặc không để lại cảnh báo.
2. **Làm hụt** — các hành động đọc dữ liệu nhạy cảm phải có vết, không chỉ các management events.
3. **Làm giả/sửa** — log phải có bằng chứng toàn vẹn mật mã, chứng minh không bị thêm/xóa/sửa lén.

Phạm vi kế hoạch này tập trung vào CloudTrail audit trail của Product-like/Sandbox account `<SANDBOX_ACCOUNT_ID>`, trail:

```text
ecommerce-dev-audit-trail
```

Mandate-12 không yêu cầu refactor app runtime, không tái sử dụng Lambda/Slack pipeline của Mandate-11, và không yêu cầu migration Object Lock trong deadline hiện tại.

## 2. Trạng thái runtime đã verify

Các kiểm tra runtime đã chạy bằng profile:

```text
<SANDBOX_SSO_PROFILE>
```

### 2.1 Đã có

| Hạng mục kiểm soát | Trạng thái runtime | Kết luận |
|---|---|---|
| CloudTrail trail | `ecommerce-dev-audit-trail` tồn tại | Đạt |
| Trạng thái ghi log | `IsLogging = true` | Đạt |
| Multi-region/global events | `IsMultiRegionTrail = true`, `IncludeGlobalServiceEvents = true` | Đạt |
| Mã hóa KMS | CloudTrail có customer-managed KMS key | Đạt |
| Tích hợp CloudWatch | Trail stream về `/aws/cloudtrail/ecommerce-dev-audit-trail` | Đạt |
| Log file validation | `LogFileValidationEnabled = true` | Đạt |
| Kiểm chứng toàn vẹn | `1/1 digest files valid`, `38/38 log files valid` | Đạt |
| Bảo vệ S3 log bucket | Versioning, encryption, public access block đã bật | Đạt |
| Coverage đọc SecretsManager | `GetSecretValue` xuất hiện trong CloudTrail management events | Đạt |

### 2.2 Còn thiếu

| Khoảng trống | Evidence runtime | Tác động tới Mandate-12 |
|---|---|---|
| Chưa ghi S3 object read data events | `DataResources = []` | Chưa chứng minh được ai đọc object S3 |
| IAM deny chưa có hiệu lực | CDO SSO role vẫn `allowed` với `StopLogging`, `DeleteTrail`, `PutEventSelectors` | Mentor có thể làm mù audit nếu dùng role hiện tại |
| Mandate-12 email alert path chưa có | Chưa có EventBridge/SNS riêng cho Mandate-12 | Chưa có detective backup độc lập ngoài IAM deny |

## 3. Quyết định thiết kế

### 3.1 Dùng CloudTrail advanced event selectors

Hiện CloudTrail module dùng `event_selector` chỉ để ghi management events.

Mandate-12 cần thêm S3 object read data events. Khi thêm advanced selectors, không được dùng lẫn `event_selector` và `advanced_event_selector` trên cùng trail.

Vì vậy module sẽ chuyển hẳn sang `advanced_event_selector`:

- selector management events luôn bật;
- selector S3 read data events bật khi environment truyền bucket ARN prefixes.

Mục tiêu là tăng coverage mà không làm mất management events hiện có.

### 3.2 Chỉ bật S3 read events cho bucket nhạy cảm

Không bật toàn bộ S3 data events vì có thể tạo nhiều event và tăng chi phí.

Sandbox sẽ bật read-only S3 data events cho hai bucket:

```text
arn:aws:s3:::ecommerce-dev-cloudtrail-logs/
arn:aws:s3:::terraform-state-phase-3/
```

Lý do:

- `ecommerce-dev-cloudtrail-logs/` chứa audit evidence.
- `terraform-state-phase-3/` chứa Terraform state, có thể chứa metadata nhạy cảm về hạ tầng.
- Phạm vi nhỏ giúp kiểm soát chi phí.

### 3.3 Không thêm SecretsManager data selector

`secretsmanager:GetSecretValue` đã được CloudTrail ghi dưới dạng management event.

Runtime đã thấy các event `GetSecretValue`, ví dụ từ RDS Proxy role đọc secret:

```text
eventSource = secretsmanager.amazonaws.com
eventName   = GetSecretValue
readOnly    = true
eventCategory = Management
```

Vì vậy không cần thêm SecretsManager data event selector riêng. Mandate-12 chỉ cần evidence/query chứng minh đọc secret có vết.

### 3.4 Tạo EventBridge + SNS email riêng cho Mandate-12

Mandate-12 sẽ tạo alert path riêng:

```text
CloudTrail tamper hoặc IAM guardrail tamper API event
  → EventBridge rule riêng Mandate-12
  → SNS topic riêng Mandate-12
  → email người nhận
```

Rule sẽ bắt CloudTrail tamper actions:

```text
StopLogging
DeleteTrail
UpdateTrail
PutEventSelectors
PutInsightSelectors
```

Rule cũng bắt IAM guardrail tamper actions liên quan tới việc gỡ hoặc làm yếu deny policy:

```text
DetachRolePolicy
DeletePolicy
DeletePolicyVersion
CreatePolicyVersion
SetDefaultPolicyVersion
PutRolePolicy
DeleteRolePolicy
```

Lý do tạo riêng thay vì reuse Mandate-11:

- Mandate-11 pipeline thuộc CDO-05 và đang dùng Lambda/Slack.
- Mandate-12 không phụ thuộc Slack hoặc Lambda.
- Tách rule/topic giúp ownership, rollback và evidence rõ hơn.
- Chi phí của một EventBridge rule và một SNS topic gần như không đáng kể so với lợi ích tách biệt ownership.

Email người nhận không hardcode trong repo. Terraform nhận qua GitHub secret/env:

```text
MANDATE_12_ALERT_EMAIL → TF_VAR_mandate_12_alert_email
```

Sau apply, người nhận phải confirm SNS email subscription trước khi dùng alert path làm evidence.

IAM guardrail tamper detection là defense-in-depth bổ sung. IAM explicitDeny vẫn là preventive control chính của Mandate-12.

### 3.5 AdminHolder quản lý IAM deny ở cấp Permission Set

Repo không quản lý IAM Identity Center Permission Sets. AdminHolder attach customer-managed policy `ecommerce-dev-audit-log-tamper-deny` (path `/`) vào:

- `Phase3-CDO-PermissionSet`;
- `Phase3-Mentor-PermissionSet`.

Sau đó adminHolder provision/update hai Permission Sets vào Sandbox account. Terraform giữ `operator_role_names = []` để không cùng quản lý generated `AWSReservedSSO_*` roles.

Runtime ngày 20/07/2026 đã xác nhận policy có hai attachments và cả CDO/Mentor role đều trả `explicitDeny` cho `StopLogging`, `DeleteTrail` và `PutEventSelectors`. Vì CDO role không có quyền đọc IAM Identity Center configuration, adminHolder/console cung cấp bằng chứng ownership ở cấp Permission Set.

Không attach vào node role, EKS cluster role, hoặc role mới không ai dùng.

## 4. Thay đổi file

### 4.1 `terraform/modules/cloudtrail/variables.tf`

Thêm biến cho S3 data events:

```hcl
variable "cloudtrail_s3_data_event_bucket_arns" {
  type        = list(string)
  default     = []
  description = "S3 bucket ARN prefixes for CloudTrail S3 read data events; e.g. arn:aws:s3:::bucket-name/"
}
```

Thêm biến cho Mandate-12 email alert:

```hcl
variable "enable_mandate_12_alert" {
  type        = bool
  default     = false
  description = "Enable Mandate-12 dedicated EventBridge/SNS CloudTrail tamper alerts."
}

variable "mandate_12_alert_email" {
  type        = string
  default     = ""
  description = "Email receiver for Mandate-12 CloudTrail tamper alerts."
  sensitive   = true
}
```

Vì sao đổi:

- Module CloudTrail là shared module.
- Không hardcode bucket name trong module.
- Environment root quyết định bucket nào là sensitive và cần data event logging.
- Email người nhận là privacy-sensitive nên truyền qua GitHub secret/env, không đưa vào `access.auto.tfvars`.
- Alert mặc định tắt để shared module và các environment chưa cấu hình không vô tình tạo notification resource.
- Điều kiện "alert bật thì email không được rỗng" được enforce bằng `lifecycle.precondition` trong resource SNS topic, không dùng cross-variable validation trong variable block.

### 4.2 `terraform/modules/cloudtrail/main.tf`

Thay block `event_selector` hiện tại bằng `advanced_event_selector`.

Management selector luôn bật:

```hcl
advanced_event_selector {
  name = "Management-events"

  field_selector {
    field  = "eventCategory"
    equals = ["Management"]
  }
}
```

S3 read data selector bật khi có bucket ARN prefixes:

```hcl
dynamic "advanced_event_selector" {
  for_each = length(var.cloudtrail_s3_data_event_bucket_arns) > 0 ? [1] : []

  content {
    name = "S3-Read-Data-Events"

    field_selector {
      field  = "eventCategory"
      equals = ["Data"]
    }

    field_selector {
      field  = "resources.type"
      equals = ["AWS::S3::Object"]
    }

    field_selector {
      field       = "resources.ARN"
      starts_with = var.cloudtrail_s3_data_event_bucket_arns
    }

    field_selector {
      field  = "readOnly"
      equals = ["true"]
    }
  }
}
```

Vì sao đổi:

- `event_selector` hiện tại không ghi object-level S3 reads.
- `advanced_event_selector` cho phép filter read-only S3 object events theo bucket prefix.
- Management events vẫn được giữ.

Thêm EventBridge/SNS riêng cho Mandate-12 khi `enable_mandate_12_alert = true`:

- SNS topic riêng cho Mandate-12 tamper alerts.
- SNS topic policy cho phép EventBridge publish.
- SNS email subscription tới `mandate_12_alert_email`.
- EventBridge rule riêng bắt CloudTrail tamper actions và IAM guardrail tamper actions.
- EventBridge target trỏ tới SNS topic riêng.
- Naming dùng prefix ngắn `m12`, ví dụ `ecommerce-dev-m12-audit-tamper`, để dễ nhận biết và rollback.

Vì sao đổi:

- IAM deny là preventive control chính.
- SNS email là detective backup độc lập.
- Không sửa hoặc phụ thuộc Lambda/Slack pipeline của Mandate-11/CDO-05.
- Bắt IAM guardrail tamper giúp phát hiện nỗ lực gỡ deny policy trước khi attacker thử tắt CloudTrail.

### 4.3 `terraform/environments/sandbox/variables.tf`

Thêm biến cho S3 data events:

```hcl
variable "cloudtrail_s3_data_event_bucket_arns" {
  type        = list(string)
  default     = []
  description = "S3 bucket ARN prefixes for CloudTrail S3 read data events"
}
```

Thêm biến cho email alert:

```hcl
variable "enable_mandate_12_alert" {
  type        = bool
  default     = false
  description = "Enable Mandate-12 dedicated EventBridge/SNS CloudTrail tamper alerts"
}

variable "mandate_12_alert_email" {
  type        = string
  default     = ""
  description = "Email receiver for Mandate-12 CloudTrail tamper alerts"
  sensitive   = true
}
```

Điều kiện email không rỗng khi bật alert được enforce ở CloudTrail module bằng `lifecycle.precondition`, không lặp lại bằng validation ở environment variables.

Vì sao đổi:

- Sandbox là Product-like environment đang cần pass Mandate-12.
- Input không nhạy cảm, có thể review qua Git.
- Email không hardcode trong repo; GitHub Actions truyền bằng `TF_VAR_mandate_12_alert_email`.

### 4.4 `terraform/environments/sandbox/main.tf`

Wire biến vào module CloudTrail:

```hcl
cloudtrail_s3_data_event_bucket_arns = var.cloudtrail_s3_data_event_bucket_arns
enable_mandate_12_alert              = var.enable_mandate_12_alert
mandate_12_alert_email               = var.mandate_12_alert_email
```

Vì sao đổi:

- Root module phải truyền policy environment-specific xuống shared module.

### 4.5 `terraform/environments/develop/variables.tf`

Thêm cùng biến:

- `cloudtrail_s3_data_event_bucket_arns` với default `[]`;
- `enable_mandate_12_alert` với default `false`;
- `mandate_12_alert_email` với default `""`; khi alert được bật, resource `lifecycle.precondition` yêu cầu email không rỗng.

Vì sao đổi:

- CloudTrail module là shared.
- Develop root nên giữ input contract tương thích với sandbox.
- Develop dùng để test resource behavior trước, nhưng không copy sandbox role names/bucket ARNs nếu account/resource khác.

### 4.6 `terraform/environments/develop/main.tf`

Wire biến vào module CloudTrail:

```hcl
cloudtrail_s3_data_event_bucket_arns = var.cloudtrail_s3_data_event_bucket_arns
enable_mandate_12_alert              = var.enable_mandate_12_alert
mandate_12_alert_email               = var.mandate_12_alert_email
```

Vì sao đổi:

- Giữ hai environment roots nhất quán khi shared module thay đổi.

### 4.7 `terraform/environments/sandbox/access.auto.tfvars`

Tạo file mới:

```hcl
cloudtrail_s3_data_event_bucket_arns = [
  "arn:aws:s3:::ecommerce-dev-cloudtrail-logs/",
  "arn:aws:s3:::terraform-state-phase-3/"
]

enable_mandate_12_alert = true
```

Vì sao dùng `access.auto.tfvars`:

- `terraform.tfvars` bị ignore, không review được, và GitHub Actions không có file này từ repo.
- `.gitignore` cho phép commit `terraform/environments/*/access.auto.tfvars`.
- Terraform tự động load `*.auto.tfvars`.
- Nội dung chỉ chứa bucket ARN prefixes và enable flag, không chứa secret.
- Đây là access-control/guardrail config cần reviewer thấy rõ trong PR.
- `audit_operator_role_names` không được set; IAM Identity Center/adminHolder sở hữu deny attachment.
- Dùng GitHub secret cho các giá trị privacy-sensitive như email receiver, không dùng secret cho role/bucket names vì chúng không cấp quyền và cần audit trail rõ.

### 4.8 GitHub Actions workflow

Thêm mapping biến email cho Terraform plan/apply:

```yaml
TF_VAR_mandate_12_alert_email: ${{ secrets.MANDATE_12_ALERT_EMAIL }}
```

Vì sao đổi:

- Email người nhận không hardcode trong repo.
- GitHub Actions cần truyền biến này vào Terraform khi chạy environment tương ứng.
- Pattern này khớp cách workflow hiện truyền các secret Terraform khác.

## 5. Kế hoạch plan/apply

### 5.1 Develop static validation; sandbox runtime verification

Thứ tự rollout đúng cho Mandate-12 hiện tại:

1. Chạy static validation cho cả `develop` và `sandbox`.
2. Không chạy runtime test ở `develop` khi develop vẫn giữ default off.
3. Chạy sandbox plan qua GitHub Actions để review chính xác thay đổi hạ tầng thật.
4. Chỉ manual apply sandbox sau khi plan đúng và reviewer approve.
5. Verify Mandate-12 trên sandbox vì sandbox có đúng resource thật cho mentor test.

Lưu ý:

- Develop đang default off: `operator_role_names = []`, `cloudtrail_s3_data_event_bucket_arns = []`, `enable_mandate_12_alert = false`.
- Apply develop trong trạng thái này không chứng minh được IAM Deny, S3 data events, hoặc EventBridge/SNS alert của Mandate-12.
- Chỉ runtime test develop nếu sau này có bucket/role/email config riêng cho develop.
- Sandbox là môi trường quyết định cho mentor verification.

### 5.2 Đường ưu tiên: GitHub Actions protected apply

Vì Product-like/Sandbox đang được deploy và vận hành qua GitHub CI/CD, đường chuẩn để apply sandbox là workflow:

```text
.github/workflows/infra-cd.yaml
```

Workflow này chạy trong Terraform root:

```text
terraform/environments/sandbox
```

và đã có các guard quan trọng:

- dùng GitHub OIDC role qua `TF_AWS_ROLE_ARN`;
- giới hạn account bằng `allowed-account-ids` trỏ đúng Sandbox account;
- dùng remote backend S3 của sandbox;
- upload plan artifact;
- apply chỉ chạy khi `workflow_dispatch` có:
  - `apply = true`;
  - `confirm = apply-sandbox`;
  - GitHub Environment `sandbox` cho approval/protection.

Vì `access.auto.tfvars` nằm trong `terraform/environments/sandbox`, Terraform sẽ auto-load file này trong cả plan và apply của workflow. Không cần thêm mapping `TF_VAR_cloudtrail_s3_data_event_bucket_arns` vào workflow. IAM deny attachment không đi qua workflow vì adminHolder quản lý tại Permission Set.

Riêng email người nhận cần GitHub secret/env `MANDATE_12_ALERT_EMAIL`, được workflow map thành `TF_VAR_mandate_12_alert_email`. Develop chỉ cần mapping tương đương nếu sau này có workflow/config riêng bật Mandate-12 alert ở develop.

### 5.3 Local apply: chỉ dùng khi có chủ ý vận hành

Local `terraform plan/apply` có thể chạy được nếu operator có đủ điều kiện:

- AWS SSO profile đang login đúng `<SANDBOX_ACCOUNT_ID>`;
- có quyền đọc/lock remote S3 backend;
- có file local `terraform.tfvars` thật;
- chạy từ đúng root `terraform/environments/sandbox`;
- plan được review trước khi apply.

Tuy nhiên local apply không phải đường ưu tiên vì:

- dễ lệch với GitHub protected environment;
- khó để reviewer/auditor thấy plan/apply artifact;
- phụ thuộc local `terraform.tfvars` bị `.gitignore`;
- dễ tạo execution mismatch nếu dùng sai profile/account/root.

Nếu dùng local apply cho deadline, phải lưu lại evidence:

- `aws sts get-caller-identity`;
- `terraform plan` output;
- confirmation người vận hành;
- post-apply verification commands.

### 5.4 Static validation

Chạy static checks trước:

```bash
terraform fmt -recursive terraform/modules/cloudtrail terraform/environments/sandbox terraform/environments/develop
terraform -chdir=terraform/environments/sandbox init -backend=false -input=false
terraform -chdir=terraform/environments/sandbox validate
terraform -chdir=terraform/environments/develop init -backend=false -input=false
terraform -chdir=terraform/environments/develop validate
```

### 5.5 Review Terraform plan cho sandbox

Nếu chạy qua GitHub Actions:

1. Mở PR chứa các file thay đổi.
2. Đọc Terraform plan comment/artifact do workflow tạo.
3. Chỉ approve nếu plan đúng phạm vi.

Nếu chạy local:

```bash
cd terraform/environments/sandbox
terraform plan -var-file=terraform.tfvars -var-file=primary-capacity.tfvars
```

Checklist review plan:

- Không replace CloudTrail trail.
- Không replace S3 audit bucket.
- Không replace KMS key.
- Không delete CloudWatch log group.
- Chỉ thay CloudTrail event selectors.
- Chỉ attach tamper-deny policy vào CDO/Mentor SSO roles.
- Chỉ tạo EventBridge rule/SNS topic/subscription riêng cho Mandate-12.
- Không sửa Mandate-11 audit-detection Lambda/SQS/Slack resources.

### 5.6 Rollback/destroy plan

Rollback chuẩn đi qua revert PR và Terraform plan đảo ngược.

Vì Mandate-12 tạo alert path riêng, gỡ sau này khá thẳng:

- remove EventBridge rule riêng Mandate-12;
- remove SNS topic/subscription riêng Mandate-12;
- remove workflow mapping `TF_VAR_mandate_12_alert_email` nếu không còn dùng;
- adminHolder review và gỡ policy khỏi Permission Sets nếu rollback IAM deny được phê duyệt;
- remove `cloudtrail_s3_data_event_bucket_arns` nếu muốn tắt S3 read data events.

Plan rollback phải được review để đảm bảo:

- không destroy CloudTrail trail;
- không destroy CloudTrail S3 bucket;
- không destroy KMS key;
- không chạm Mandate-11 audit-detection resources;
- chỉ gỡ đúng resources/config thuộc Mandate-12.

### 5.7 Apply

Đường ưu tiên: chạy `workflow_dispatch` của `infra-cd.yaml`:

```text
apply  = true
confirm = apply-sandbox
```

Phương án dự phòng local:

```bash
terraform apply
```

Phương án dự phòng local chỉ dùng khi team chấp nhận ghi evidence thủ công và đã xác nhận đúng AWS caller/root/state.

## 6. Kế hoạch kiểm chứng

### 6.1 Verify event selectors

```bash
aws cloudtrail get-event-selectors \
  --region us-east-1 \
  --trail-name ecommerce-dev-audit-trail \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kỳ vọng:

- Có `AdvancedEventSelectors`.
- Có management selector.
- Có S3 read data selector.
- `resources.ARN` starts with:
  - `arn:aws:s3:::ecommerce-dev-cloudtrail-logs/`
  - `arn:aws:s3:::terraform-state-phase-3/`

### 6.2 Verify IAM deny

CDO role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::<SANDBOX_ACCOUNT_ID>:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568" \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns "arn:aws:cloudtrail:us-east-1:<SANDBOX_ACCOUNT_ID>:trail/ecommerce-dev-audit-trail" \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Mentor role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::<SANDBOX_ACCOUNT_ID>:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33" \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns "arn:aws:cloudtrail:us-east-1:<SANDBOX_ACCOUNT_ID>:trail/ecommerce-dev-audit-trail" \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kỳ vọng:

```text
EvalDecision = explicitDeny
```

### 6.3 Verify actual S3 read trace

Đọc thử một object có sẵn từ CloudTrail log bucket:

```bash
KEY=$(aws s3api list-objects-v2 \
  --bucket ecommerce-dev-cloudtrail-logs \
  --max-items 1 \
  --query 'Contents[0].Key' \
  --output text \
  --profile "<SANDBOX_SSO_PROFILE>")

aws s3api get-object \
  --bucket ecommerce-dev-cloudtrail-logs \
  --key "$KEY" \
  /tmp/m12-test-object \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Sau delay delivery của CloudTrail, tìm event `GetObject` trong CloudTrail CloudWatch log group. Không dùng `aws cloudtrail lookup-events`, vì command đó chỉ trả management events.

```bash
aws logs filter-log-events \
  --region us-east-1 \
  --log-group-name /aws/cloudtrail/ecommerce-dev-audit-trail \
  --filter-pattern '{ ($.eventSource = "s3.amazonaws.com") && ($.eventName = "GetObject") && ($.eventCategory = "Data") }' \
  --max-items 20 \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kỳ vọng:

```text
eventSource = s3.amazonaws.com
eventName   = GetObject
readOnly    = true
eventCategory = Data
```

### 6.4 Verify integrity

```bash
aws cloudtrail validate-logs \
  --trail-arn "arn:aws:cloudtrail:us-east-1:<SANDBOX_ACCOUNT_ID>:trail/ecommerce-dev-audit-trail" \
  --start-time 2026-07-20T02:00:00Z \
  --end-time 2026-07-20T03:00:00Z \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kỳ vọng:

```text
digest files valid
log files valid
```

### 6.5 Verify Mandate-12 alert path

Kiểm tra EventBridge rule riêng:

```bash
aws events list-rules \
  --region us-east-1 \
  --name-prefix ecommerce-dev-m12 \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kiểm tra target SNS:

```bash
aws events list-targets-by-rule \
  --region us-east-1 \
  --rule "<m12-eventbridge-rule-name>" \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kiểm tra SNS subscription:

```bash
aws sns list-subscriptions-by-topic \
  --region us-east-1 \
  --topic-arn "<m12-sns-topic-arn>" \
  --profile "<SANDBOX_SSO_PROFILE>"
```

Kỳ vọng:

- EventBridge rule riêng Mandate-12 là `ENABLED`.
- Rule target trỏ tới SNS topic riêng Mandate-12.
- Event pattern có cả `cloudtrail.amazonaws.com` và `iam.amazonaws.com`.
- SNS subscription không còn `PendingConfirmation`.
- Email người nhận đã click confirm subscription.
- Không có dependency vào Lambda/Slack/Mandate-11.

## 7. Rủi ro và cách giảm thiểu

### 7.1 Permission Set attachment là external control

Terraform không quản lý IAM Identity Center Permission Sets và không attach trực tiếp vào generated `AWSReservedSSO_*` roles.

Cách kiểm soát:

- adminHolder quản lý policy reference và provision Permission Sets;
- lưu screenshot/config đã redact làm ownership evidence;
- re-run attachment check và IAM Simulator sau mỗi lần provision;
- không để Terraform và Identity Center cùng sở hữu attachment.

### 7.2 Break-glass phải tách riêng

Không thêm routine roles CDO/Mentor vào:

```hcl
audit_administrator_principals
audit_break_glass_principals
```

Hiện tại condition exemption chỉ áp dụng cho statement chặn CloudTrail tampering. Các deny statement cho CloudWatch Logs, S3 và KMS không có exemption tương ứng. Vì chưa cấu hình break-glass principal trong rollout này, đây là limitation cần được xử lý trong thiết kế break-glass follow-up.

Nếu cần quản trị audit khẩn cấp, dùng một break-glass principal riêng, có approval và evidence.

### 7.3 Chi phí S3 data events

Kế hoạch chỉ ghi read-only S3 data events cho hai bucket. Cách này giữ volume thấp và tránh chi phí data events cho toàn bộ S3 account.

Không bật toàn bộ S3 buckets nếu chưa có cost review riêng.

### 7.4 SNS email subscription cần confirm

SNS email subscription không hoạt động cho tới khi receiver bấm confirm trong email AWS gửi.

Cách giảm thiểu:

- dùng email người nhận do team kiểm soát;
- confirm ngay sau Terraform apply;
- verify bằng `aws sns list-subscriptions-by-topic`;
- không demo alert path trước khi subscription confirmed.

### 7.5 Retention của EKS audit

Runtime EKS Kubernetes audit log retention hiện là 7 ngày.

Đây là known auditability gap, nhưng không phải blocker của Mandate-12 vì kế hoạch này tập trung vào CloudTrail anti-defeat controls:

- CloudTrail S3 archive: 2555 ngày.
- CloudTrail CloudWatch: 90 ngày.
- EKS Kubernetes audit CloudWatch: 7 ngày.

### 7.6 Object Lock

S3 Object Lock chưa bật trên CloudTrail bucket hiện tại. AWS hỗ trợ bật Object Lock trên bucket hiện hữu đã bật versioning, nhưng đây là thay đổi không thể đảo ngược.

Default retention sau khi bật chỉ tự áp dụng cho object mới. Object cũ cần được gán retention riêng, ví dụ bằng S3 Batch Operations.

Kế hoạch này dựa vào:

- CloudTrail log file validation;
- S3 versioning;
- KMS encryption;
- public access block;
- IAM deny cho tamper attempts;
- long retention.

Nếu bắt buộc phải có Object Lock, cần track thành follow-up riêng để review Terraform plan, retention mode/period, quyền break-glass và cách xử lý object hiện hữu. Không defer với lý do AWS không hỗ trợ bucket hiện hữu.

### 7.7 Identity Center administrator vẫn có thể thay đổi control

Permission Set attachment chặn routine CDO/Mentor operators nhưng không chặn Identity Center/Organizations administrator thay đổi chính Permission Set. EventBridge rule hiện bắt CloudTrail/IAM tamper events, không tuyên bố bao phủ mọi `sso-admin` control-plane change.

Cách giảm thiểu:

- giới hạn adminHolder và yêu cầu change record/reviewer;
- lưu Permission Set ownership evidence;
- re-run simulator sau mỗi lần provision;
- cân nhắc SCP hoặc detective control cho Identity Center changes nếu threat model yêu cầu.

## 8. Tiêu chí hoàn tất

Mandate-12 được coi là sẵn sàng cho mentor verify khi:

- CloudTrail dùng advanced selectors với management events và S3 read data events.
- Simulation của CDO và Mentor SSO role trả về `explicitDeny` cho audit-tamper actions.
- Một lần đọc thật `s3:GetObject` tạo CloudTrail data event.
- EventBridge/SNS email alert path riêng của Mandate-12 tồn tại, enabled, và subscription đã confirmed.
- `validate-logs` thành công cho một khoảng thời gian đã review.
- Không phụ thuộc Lambda/Slack/Mandate-11 pipeline.
- Retention và known gaps được document.
