# MANDATE-12 — Việc cần người ngoài/adminHolder hỗ trợ

## Mục đích

File này liệt kê các việc có thể cần người ngoài code-change owner thực hiện hoặc xác nhận. Nội dung được chia thành việc cần trước khi mentor verify và việc follow-up bền vững sau deadline.

## Cần trước khi mentor verify

### 1. Approve/run Terraform apply qua GitHub protected workflow

**Người phụ trách:** người approve GitHub Environment `sandbox` / infrastructure operator.

**Hành động:** approve và chạy workflow `infra-cd.yaml` sau khi PR đã được review.

Workflow inputs dự kiến:

```text
apply = true
confirm = apply-sandbox
```

Vì sao cần:

- Mandate-12 thay đổi AWS CloudTrail selectors và IAM role policy attachments.
- Product-like/Sandbox infra đang được quản lý qua GitHub Actions.
- Workflow có account guard `allowed-account-ids: "804372444787"` và tạo plan artifact để review.

Phương án dự phòng:

- Local apply có thể chạy nếu operator có sandbox tfvars thật, SSO profile đúng, và quyền backend.
- Nếu dùng local apply, phải capture `aws sts get-caller-identity`, plan output, và post-apply verification evidence.

### 2. Approve workaround attach deny policy trực tiếp vào SSO roles

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

### 3. Xác nhận alert receiver nếu team muốn dùng alert làm evidence chính

**Người phụ trách:** channel owner hoặc on-call receiver, nếu có.

**Hành động:** xác nhận kênh audit alert từ Mandate-11 vẫn có người theo dõi và nhận được message, nếu team quyết định dùng đường alert này trong mentor demo.

Đường runtime hiện tại:

```text
EventBridge rule: ecommerce-dev-audit-cloudtrail-tampering
SQS queue:        ecommerce-dev-audit-processing
Lambda:           ecommerce-dev-audit-slack-alert
Webhook secret:   /ecommerce/dev/audit/slack-webhook
```

Vì sao cần:

- Mandate-12 không bắt buộc phải dùng Slack.
- Với kế hoạch hiện tại, điều kiện pass chính cho “làm mù” là IAM deny trả `explicitDeny`.
- Alert path là evidence bổ sung. Nếu không có thông tin receiver/webhook, không dùng Slack message làm điều kiện pass.

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

- Tạo alert pipeline mới.
- Tạo operator role mới mà không ai dùng.
- Attach deny policy vào EKS node roles hoặc cluster roles.
- Migration CloudTrail bucket để bật S3 Object Lock.
- Tăng retention cho EKS Kubernetes audit log.
- Các thay đổi runtime hardening như `runAsNonRoot`.
