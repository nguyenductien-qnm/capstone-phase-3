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
- Nếu test `develop` trước, develop cũng cần secret/env tương ứng hoặc plan sẽ fail khi `enable_mandate_12_alert = true`.

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

- Mandate-12 thay đổi AWS CloudTrail selectors, IAM role policy attachments, EventBridge rule và SNS topic/subscription.
- Product-like/Sandbox infra đang được quản lý qua GitHub Actions.
- Workflow có account guard `allowed-account-ids: "804372444787"` và tạo plan artifact để review.
- Rollout nên test `develop` trước nếu develop có config riêng, rồi mới apply `sandbox` để pass mentor verification.

Phương án dự phòng:

- Local apply có thể chạy nếu operator có sandbox tfvars thật, SSO profile đúng, quyền backend, và biến `TF_VAR_mandate_12_alert_email` được export local.
- Nếu dùng local apply, phải capture `aws sts get-caller-identity`, plan output, và post-apply verification evidence.

### 4. Approve workaround attach deny policy trực tiếp vào SSO roles

**Người phụ trách:** CDO lead / mentor / adminHolder, tùy quy trình team.

**Hành động:** approve việc Terraform attach tạm policy `ecommerce-dev-audit-log-tamper-deny` vào:

```text
AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568
AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33
```

Vì sao cần:

- Runtime IAM simulation hiện cho thấy CDO SSO role vẫn gọi được CloudTrail tamper actions.
- Mentor có thể dùng CDO hoặc Mentor SSO role để kiểm chứng.
- Nếu deny chưa effective, bài test “làm mù” có thể fail.

Giới hạn quan trọng:

- Đây là workaround cho deadline.
- `AWSReservedSSO_*` roles do IAM Identity Center quản lý.
- Nếu Permission Set được reprovision sau này, role attachment có thể bị overwrite hoặc role có thể bị recreate.

## Follow-up bền vững nên làm

### 1. Chuyển deny attachment lên IAM Identity Center Permission Set

**Người phụ trách:** adminHolder / IAM Identity Center administrator.

**Hành động:** attach managed policy vào routine operator Permission Set thay vì attach trực tiếp vào generated `AWSReservedSSO_*` roles.

Policy:

```text
arn:aws:iam::804372444787:policy/ecommerce-dev-audit-log-tamper-deny
```

Vì sao:

- Enforcement ở Permission Set bền hơn.
- Tránh quản lý trực tiếp generated SSO roles.
- Khớp identity control boundary tốt hơn.

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

Hai biến này exempt principals khỏi deny policy.

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
- Migration CloudTrail bucket để bật S3 Object Lock.
- Tăng retention cho EKS Kubernetes audit log.
- Các thay đổi runtime hardening như `runAsNonRoot`.
