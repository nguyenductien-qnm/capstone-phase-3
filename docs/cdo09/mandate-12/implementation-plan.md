# MANDATE-12 — Kế hoạch triển khai Audit Anti-Defeat

## 1. Mục tiêu

Mandate-12 yêu cầu chứng minh audit trail không thể bị đánh bại theo ba hướng:

1. **Làm mù** — attacker/admin không được tắt hoặc làm yếu đường ghi log mà không bị chặn hoặc không để lại cảnh báo.
2. **Làm hụt** — các hành động đọc dữ liệu nhạy cảm phải có vết, không chỉ các management events.
3. **Làm giả/sửa** — log phải có bằng chứng toàn vẹn mật mã, chứng minh không bị thêm/xóa/sửa lén.

Phạm vi kế hoạch này tập trung vào CloudTrail audit trail của Product-like/Sandbox account `804372444787`, trail:

```text
ecommerce-dev-audit-trail
```

Mandate-12 không yêu cầu refactor app runtime, không yêu cầu tạo alert pipeline mới, và không yêu cầu migration Object Lock trong deadline hiện tại.

## 2. Trạng thái runtime đã verify

Các kiểm tra runtime đã chạy bằng profile:

```text
804372444787_Phase3-CDO-PermissionSet
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
| Đường cảnh báo | EventBridge → SQS → Lambda → Slack đã tồn tại | Đạt |
| Coverage đọc SecretsManager | `GetSecretValue` xuất hiện trong CloudTrail management events | Đạt |

### 2.2 Còn thiếu

| Khoảng trống | Evidence runtime | Tác động tới Mandate-12 |
|---|---|---|
| Chưa ghi S3 object read data events | `DataResources = []` | Chưa chứng minh được ai đọc object S3 |
| IAM deny chưa có hiệu lực | CDO SSO role vẫn `allowed` với `StopLogging`, `DeleteTrail`, `PutEventSelectors` | Mentor có thể làm mù audit nếu dùng role hiện tại |

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

### 3.4 Tái sử dụng alert pipeline hiện có

Không tạo SNS/EventBridge mới cho Mandate-12.

Runtime đã verify:

```text
EventBridge rule: ecommerce-dev-audit-cloudtrail-tampering
Target:          ecommerce-dev-audit-processing SQS queue
Processor:       ecommerce-dev-audit-slack-alert Lambda
Receiver:        Slack webhook stored in SSM Parameter Store
```

Rule đã bắt:

```text
StopLogging
DeleteTrail
UpdateTrail
PutEventSelectors
PutInsightSelectors
```

Vì vậy phần alert cho “làm mù” đã có sẵn từ Mandate-11 và được reuse.

### 3.5 Attach IAM deny vào CDO/Mentor SSO role là workaround

Control bền vững nhất là attach deny policy vào IAM Identity Center Permission Set.

Tuy nhiên repo hiện không quản lý IAM Identity Center Permission Set. Nếu không có admin action kịp deadline, mentor dùng CDO/Mentor SSO role vẫn có thể gọi `StopLogging`.

Vì vậy kế hoạch này dùng workaround tạm thời:

- attach managed policy `ecommerce-dev-audit-log-tamper-deny` trực tiếp vào CDO SSO role;
- attach cùng policy vào Mentor SSO role;
- ghi rõ đây là temporary enforcement workaround;
- follow-up là migrate attachment lên Identity Center Permission Set.

Không attach vào node role, EKS cluster role, hoặc role mới không ai dùng.

## 4. Thay đổi file

### 4.1 `terraform/modules/cloudtrail/variables.tf`

Thêm biến:

```hcl
variable "cloudtrail_s3_data_event_bucket_arns" {
  type        = list(string)
  default     = []
  description = "S3 bucket ARN prefixes for CloudTrail S3 read data events; e.g. arn:aws:s3:::bucket-name/"
}
```

Vì sao đổi:

- Module CloudTrail là shared module.
- Không hardcode bucket name trong module.
- Environment root quyết định bucket nào là sensitive và cần data event logging.

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

### 4.3 `terraform/environments/sandbox/variables.tf`

Thêm biến:

```hcl
variable "cloudtrail_s3_data_event_bucket_arns" {
  type        = list(string)
  default     = []
  description = "S3 bucket ARN prefixes for CloudTrail S3 read data events"
}
```

Vì sao đổi:

- Sandbox là Product-like environment đang cần pass Mandate-12.
- Input không nhạy cảm, có thể review qua Git.

### 4.4 `terraform/environments/sandbox/main.tf`

Wire biến vào module CloudTrail:

```hcl
cloudtrail_s3_data_event_bucket_arns = var.cloudtrail_s3_data_event_bucket_arns
```

Vì sao đổi:

- Root module phải truyền policy environment-specific xuống shared module.

### 4.5 `terraform/environments/develop/variables.tf`

Thêm cùng biến với default `[]`.

Vì sao đổi:

- CloudTrail module là shared.
- Develop root nên giữ input contract tương thích với sandbox.
- Develop chưa cần bật S3 data event logging nếu chưa xác định bucket list.

### 4.6 `terraform/environments/develop/main.tf`

Wire biến vào module CloudTrail:

```hcl
cloudtrail_s3_data_event_bucket_arns = var.cloudtrail_s3_data_event_bucket_arns
```

Vì sao đổi:

- Giữ hai environment roots nhất quán khi shared module thay đổi.

### 4.7 `terraform/environments/sandbox/access.auto.tfvars`

Tạo file mới:

```hcl
audit_operator_role_names = [
  "AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568",
  "AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33"
]

cloudtrail_s3_data_event_bucket_arns = [
  "arn:aws:s3:::ecommerce-dev-cloudtrail-logs/",
  "arn:aws:s3:::terraform-state-phase-3/"
]
```

Vì sao dùng `access.auto.tfvars`:

- `terraform.tfvars` bị ignore, không review được.
- `.gitignore` cho phép commit `terraform/environments/*/access.auto.tfvars`.
- Terraform tự động load `*.auto.tfvars`.
- Nội dung chỉ chứa role names và bucket ARN prefixes, không chứa secret.

## 5. Kế hoạch plan/apply

### 5.1 Đường ưu tiên: GitHub Actions protected apply

Vì Product-like/Sandbox đang được deploy và vận hành qua GitHub CI/CD, đường chuẩn để apply Mandate-12 là workflow:

```text
.github/workflows/infra-cd.yaml
```

Workflow này chạy trong Terraform root:

```text
terraform/environments/sandbox
```

và đã có các guard quan trọng:

- dùng GitHub OIDC role qua `TF_AWS_ROLE_ARN`;
- giới hạn account bằng `allowed-account-ids: "804372444787"`;
- dùng remote backend S3 của sandbox;
- upload plan artifact;
- apply chỉ chạy khi `workflow_dispatch` có:
  - `apply = true`;
  - `confirm = apply-sandbox`;
  - GitHub Environment `sandbox` cho approval/protection.

Vì `access.auto.tfvars` nằm trong `terraform/environments/sandbox`, Terraform sẽ auto-load file này trong cả plan và apply của workflow. Không cần thêm mapping `TF_VAR_audit_operator_role_names` hoặc `TF_VAR_cloudtrail_s3_data_event_bucket_arns` vào workflow.

### 5.2 Local apply: chỉ dùng khi có chủ ý vận hành

Local `terraform plan/apply` có thể chạy được nếu operator có đủ điều kiện:

- AWS SSO profile đang login đúng account `804372444787`;
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

### 5.3 Static validation

Chạy static checks trước:

```bash
terraform fmt -recursive terraform/modules/cloudtrail terraform/environments/sandbox terraform/environments/develop
terraform -chdir=terraform/environments/sandbox init -backend=false -input=false
terraform -chdir=terraform/environments/sandbox validate
terraform -chdir=terraform/environments/develop init -backend=false -input=false
terraform -chdir=terraform/environments/develop validate
```

### 5.4 Review Terraform plan cho sandbox

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

### 5.5 Apply

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
  --profile 804372444787_Phase3-CDO-PermissionSet
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
  --policy-source-arn arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568 \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns arn:aws:cloudtrail:us-east-1:804372444787:trail/ecommerce-dev-audit-trail \
  --profile 804372444787_Phase3-CDO-PermissionSet
```

Mentor role:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33 \
  --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors \
  --resource-arns arn:aws:cloudtrail:us-east-1:804372444787:trail/ecommerce-dev-audit-trail \
  --profile 804372444787_Phase3-CDO-PermissionSet
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
  --profile 804372444787_Phase3-CDO-PermissionSet)

aws s3api get-object \
  --bucket ecommerce-dev-cloudtrail-logs \
  --key "$KEY" \
  /tmp/m12-test-object \
  --profile 804372444787_Phase3-CDO-PermissionSet
```

Sau delay delivery của CloudTrail, tìm event `GetObject`.

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
  --trail-arn arn:aws:cloudtrail:us-east-1:804372444787:trail/ecommerce-dev-audit-trail \
  --start-time 2026-07-20T02:00:00Z \
  --end-time 2026-07-20T03:00:00Z \
  --profile 804372444787_Phase3-CDO-PermissionSet
```

Kỳ vọng:

```text
digest files valid
log files valid
```

### 6.5 Verify alert path

Evidence read-only:

```bash
aws events list-targets-by-rule \
  --region us-east-1 \
  --rule ecommerce-dev-audit-cloudtrail-tampering \
  --profile 804372444787_Phase3-CDO-PermissionSet

aws lambda list-event-source-mappings \
  --region us-east-1 \
  --function-name ecommerce-dev-audit-slack-alert \
  --profile 804372444787_Phase3-CDO-PermissionSet
```

Kỳ vọng:

- EventBridge target là `ecommerce-dev-audit-processing`.
- Lambda event source mapping là `Enabled`.
- Lambda Errors metric vẫn bằng 0 trong test window.

## 7. Rủi ro và cách giảm thiểu

### 7.1 Attach trực tiếp vào SSO role là tạm thời

Direct attachment vào `AWSReservedSSO_*` roles là workaround.

Cách giảm thiểu:

- document rõ workaround;
- verify sau apply;
- tạo follow-up action để attach policy ở IAM Identity Center Permission Set level.

### 7.2 Break-glass phải tách riêng

Không thêm routine roles CDO/Mentor vào:

```hcl
audit_administrator_principals
audit_break_glass_principals
```

Các biến này exempt principals khỏi deny policy.

Nếu cần quản trị audit khẩn cấp, dùng một break-glass principal riêng, có approval và evidence.

### 7.3 Chi phí S3 data events

Kế hoạch chỉ ghi read-only S3 data events cho hai bucket. Cách này giữ volume thấp và tránh chi phí data events cho toàn bộ S3 account.

Không bật toàn bộ S3 buckets nếu chưa có cost review riêng.

### 7.4 Retention của EKS audit

Runtime EKS Kubernetes audit log retention hiện là 7 ngày.

Đây là known auditability gap, nhưng không phải blocker của Mandate-12 vì kế hoạch này tập trung vào CloudTrail anti-defeat controls:

- CloudTrail S3 archive: 2555 ngày.
- CloudTrail CloudWatch: 90 ngày.
- EKS Kubernetes audit CloudWatch: 7 ngày.

### 7.5 Object Lock

S3 Object Lock chưa bật trên CloudTrail bucket hiện tại và không thể bật retroactively trên bucket đó nếu không migration.

Kế hoạch này dựa vào:

- CloudTrail log file validation;
- S3 versioning;
- KMS encryption;
- public access block;
- IAM deny cho tamper attempts;
- long retention.

Nếu bắt buộc phải có Object Lock, cần track thành follow-up migration riêng.

### 7.6 Direct SSO attachment vẫn có thể bị admin gỡ

Vì CDO/Mentor roles hiện có quyền admin rộng, direct role attachment không mạnh bằng SCP hoặc Permission Set-level control được quản lý ngoài routine operator access.

Cách giảm thiểu cho deadline này:

- attach deny policy vào CDO/Mentor roles để chặn direct CloudTrail tampering;
- giữ EventBridge rules cho IAM guardrail-removal actions ở trạng thái enabled;
- document đây là workaround tạm thời;
- follow up với adminHolder/Identity Center owner để enforcement bền vững ở Permission Set.

## 8. Tiêu chí hoàn tất

Mandate-12 được coi là sẵn sàng cho mentor verify khi:

- CloudTrail dùng advanced selectors với management events và S3 read data events.
- Simulation của CDO và Mentor SSO role trả về `explicitDeny` cho audit-tamper actions.
- Một lần đọc thật `s3:GetObject` tạo CloudTrail data event.
- `validate-logs` thành công cho một khoảng thời gian đã review.
- Existing EventBridge/SQS/Lambda alert pipeline được document kèm runtime evidence.
- Retention và known gaps được document.
