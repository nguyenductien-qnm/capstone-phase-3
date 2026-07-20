# MANDATE-12 — Việc cần người ngoài/adminHolder hỗ trợ

## Mục đích

File này liệt kê các việc có thể cần người ngoài code-change owner thực hiện hoặc xác nhận. Nội dung được chia thành việc cần trước khi mentor verify và việc follow-up bền vững sau deadline.

## Cần trước khi mentor verify

### 1. Cấu hình email người nhận cho Mandate-12 SNS alert

**Người phụ trách:** repo/admin người có quyền cấu hình GitHub Environment/Secrets.

**Hành động:** tạo GitHub secret/env cho environment sẽ chạy Mandate-12 plan/apply:

```text
MANDATE_12_ALERT_EMAIL=<email nhận cảnh báo>
```

Vì sao cần:

- Mandate-12 tạo SNS email alert riêng, không dùng Slack/Lambda của Mandate-11.
- Email cá nhân là thông tin privacy-sensitive, không nên hardcode trong repo nếu không cần.
- Terraform cần giá trị này khi chạy plan/apply qua GitHub Actions.
- Develop chỉ cần secret/env tương ứng nếu sau này có workflow/config riêng bật `enable_mandate_12_alert = true` ở develop. Với thiết kế hiện tại, develop default off và chỉ cần static validation.

### 2. Confirm SNS email subscription sau Terraform apply

**Người phụ trách:** người sở hữu email nhận cảnh báo.

**Hành động:** sau `terraform apply`, mở email từ AWS Notifications và bấm confirm subscription.

Vì sao cần:

- `aws_sns_topic_subscription` với protocol `email` sẽ ở trạng thái pending cho tới khi receiver confirm.
- Nếu chưa confirm, EventBridge có publish vào SNS nhưng email sẽ không được gửi tới người nhận.
- Mentor test alert path chỉ nên chạy sau khi subscription đã `Confirmed`.

Verify:

```bash
aws sns list-subscriptions-by-topic \
  --region us-east-1 \
  --topic-arn <m12-topic-arn>
```

Kỳ vọng:

```text
SubscriptionArn != PendingConfirmation
```

### 3. Approve/run Terraform apply qua GitHub protected workflow

**Người phụ trách:** người approve GitHub Environment `sandbox` / infrastructure operator.

**Hành động:** approve và chạy workflow Terraform sau khi PR đã được review.

Workflow inputs dự kiến:

```text
apply = true
confirm = apply-sandbox
```

Vì sao cần:

- Mandate-12 thay đổi AWS CloudTrail selectors, EventBridge rule và SNS topic/subscription. IAM Permission Set attachment do adminHolder quản lý ngoài Terraform.
- Product-like/Sandbox infra đang được quản lý qua GitHub Actions.
- Workflow có `allowed-account-ids` guard trỏ đúng Sandbox account và tạo plan artifact để review.
- Develop hiện default off cho Mandate-12, nên runtime verification chính là sandbox plan/apply sau khi PR được review.

Phương án dự phòng:

- Local apply có thể chạy nếu operator có sandbox tfvars thật, SSO profile đúng, quyền backend, và biến `TF_VAR_mandate_12_alert_email` được export local.
- Nếu dùng local apply, phải capture `aws sts get-caller-identity`, plan output, và post-apply verification evidence.

### 4. Xác nhận IAM deny ở cấp Permission Set

**Người phụ trách:** adminHolder / IAM Identity Center administrator.

**Hành động:** attach customer-managed policy sau vào hai routine operator Permission Sets và provision/update chúng vào Sandbox account:

```text
Policy name: ecommerce-dev-audit-log-tamper-deny
Policy path: /
Permission Sets:
- Phase3-CDO-PermissionSet
- Phase3-Mentor-PermissionSet
```

**Trạng thái kiểm tra ngày 20/07/2026:**

- Policy có `AttachmentCount = 2`.
- Policy xuất hiện trên đúng hai generated CDO/Mentor SSO roles.
- IAM Simulator trả `explicitDeny` cho `StopLogging`, `DeleteTrail` và `PutEventSelectors` trên cả hai role.
- CDO role bị từ chối `sso:ListInstances`, nên cấu hình Permission Set cần adminHolder/console làm evidence ownership.

Terraform giữ `audit_operator_role_names = []` và không attach trực tiếp vào generated `AWSReservedSSO_*` roles, tránh hai hệ thống cùng quản lý một attachment.

## Follow-up bền vững nên làm

### 1. Lưu và kiểm tra định kỳ bằng chứng Permission Set

**Người phụ trách:** adminHolder / IAM Identity Center administrator.

**Hành động:** lưu screenshot/config đã redact của hai Permission Sets và re-run IAM Simulator sau mỗi lần provision hoặc thay đổi Permission Set.

### 2. Định nghĩa break-glass audit administration

**Người phụ trách:** adminHolder / security owner.

**Hành động:** định nghĩa principal break-glass hoặc audit-admin riêng, quy trình approval, và yêu cầu evidence.

Vì sao:

- CDO/Mentor routine roles không nên được exempt khỏi deny policy.
- Emergency audit changes vẫn cần một đường có kiểm soát.

Không thêm CDO/Mentor routine roles vào:

```hcl
audit_administrator_principals
audit_break_glass_principals
```

Trong code hiện tại, exemption chỉ áp dụng cho CloudTrail tamper statement; S3, CloudWatch Logs và KMS deny statements vẫn áp dụng. Thiết kế break-glass đầy đủ cần một follow-up riêng.

### 3. Cân nhắc guardrail cấp AWS Organizations

**Người phụ trách:** AWS Organizations administrator, nếu account thuộc Organization.

**Hành động:** đánh giá SCP để bảo vệ các hành động CloudTrail stop/delete/update.

Vì sao:

- SCP nằm ngoài quyền operator trong account.
- SCP cho bảo đảm anti-defeat mạnh hơn role policy attachment.

Việc này không bắt buộc cho project hiện tại nếu account không được quản lý qua AWS Organizations.

## Không cần cho deadline Mandate-12

- Tái sử dụng Lambda/Slack pipeline của Mandate-11/CDO-05.
- Tạo Lambda mới.
- Tạo operator role mới mà không ai dùng.
- Attach deny policy vào EKS node roles hoặc cluster roles.
- Bật Object Lock và áp retention cho object hiện hữu; đây là thay đổi không thể đảo ngược cần risk review riêng.
- Tăng retention cho EKS Kubernetes audit log.
- Các thay đổi runtime hardening như `runAsNonRoot`.
