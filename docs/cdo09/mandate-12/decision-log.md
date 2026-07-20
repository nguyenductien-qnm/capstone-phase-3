# MANDATE-12 — Decision Log

File này ghi lại các quyết định thiết kế trong quá trình chốt Mandate-12. Mục tiêu là giữ audit trail cho chính quá trình ra quyết định: user hỏi/concern gì, phản hồi kỹ thuật là gì, và quyết định cuối cùng ra sao.

## Entry 001 — Mandate-12 có áp dụng cho project hiện tại không?

**User concern**

Directive nói rằng ở Directive #4 team đã chứng minh log “không xóa được” bằng Object Lock. User hỏi liệu giả định đó có áp dụng cho project hiện tại không, vì runtime hiện tại có thể không bật Object Lock.

**Phản hồi kỹ thuật**

Mandate-12 vẫn áp dụng, nhưng không được copy nguyên giả định của TF4. Với CDO09/Sandbox hiện tại:

- CloudTrail bucket có versioning, encryption, lifecycle retention và log file validation.
- Object Lock chưa bật trên bucket hiện tại.
- Object Lock không thể bật retroactively nếu bucket không được tạo với Object Lock enabled từ đầu.

**Quyết định**

Mandate-12 được triển khai như một adaptation cho runtime hiện tại, không phải migration Object Lock.

**Outcome**

Object Lock được ghi là known gap/follow-up. Scope hiện tại tập trung vào IAM deny, S3 read data events, EventBridge/SNS email alert riêng, và CloudTrail log validation.

## Entry 002 — Không tạo CloudTrail hoặc S3 bucket riêng cho Mandate-12

**User concern**

User lo rằng việc tạo CloudTrail/S3 riêng cho Mandate-12 sẽ tạo audit island chỉ dùng một lần, không reusable cho các thành viên khác.

**Phản hồi kỹ thuật**

Mandate-12 không cần và không nên tạo CloudTrail hoặc S3 bucket mới. Audit trail nên là shared platform control.

**Quyết định**

Reuse infrastructure hiện có:

```text
CloudTrail: ecommerce-dev-audit-trail
CloudTrail log bucket: ecommerce-dev-cloudtrail-logs
Terraform state bucket: terraform-state-phase-3
```

**Outcome**

Implementation chỉ nâng cấp CloudTrail hiện có:

- chuyển selector sang advanced event selectors;
- thêm S3 read data events cho bucket hiện có;
- thêm guardrail IAM deny;
- thêm alert wrapper riêng bằng EventBridge/SNS.

Không tạo CloudTrail mới, S3 log bucket mới, Terraform state bucket mới, Object Lock bucket mới, hoặc Lambda mới.

## Entry 003 — Không dùng Slack/Lambda Mandate-11 làm điều kiện pass

**User concern**

User không có thông tin Slack/webhook/channel receiver và không muốn phụ thuộc Slack.

**Phản hồi kỹ thuật**

Mandate-12 cần chống “làm mù”. Nếu IAM explicitDeny chặn được `StopLogging`/`DeleteTrail`, thì control chính đã pass theo hướng preventive. Slack/Lambda Mandate-11 có thể tồn tại trong project nhưng không nên là dependency của Mandate-12.

**Quyết định**

Mandate-12 không phụ thuộc Slack, Lambda, hoặc pipeline Mandate-11/CDO-05.

**Outcome**

Docs được chỉnh để:

- không dùng Slack message delivery làm điều kiện pass;
- không sửa Lambda/SQS/Slack Mandate-11;
- không nhận ownership resource của CDO-05.

## Entry 004 — Tạo EventBridge/SNS riêng cho Mandate-12

**User concern**

User muốn có alert email backup sau IAM deny, nhưng vẫn muốn tách khỏi Mandate-11.

**Phản hồi kỹ thuật**

Có hai lựa chọn:

1. Reuse EventBridge rule cũ của Mandate-11 và thêm SNS target.
2. Tạo EventBridge rule + SNS topic riêng cho Mandate-12.

Reuse rule cũ ít resource hơn, nhưng làm ownership và rollback bị mơ hồ. Tạo rule/topic riêng có cost gần như bằng 0 và isolation tốt hơn.

**Quyết định**

Tạo EventBridge rule riêng và SNS topic riêng cho Mandate-12.

**Outcome**

Architecture final:

```text
CloudTrail tamper hoặc IAM guardrail tamper API event
  → EventBridge rule riêng Mandate-12
  → SNS topic riêng Mandate-12
  → email người nhận
```

Naming dùng prefix ngắn:

```text
ecommerce-dev-m12-audit-tamper
```

## Entry 005 — Alert rule bắt thêm IAM guardrail tamper

**User concern**

User hỏi liệu attacker có thể backdoor bằng cách gỡ guardrail trước khi tắt CloudTrail không.

**Phản hồi kỹ thuật**

Đúng. Một attacker thông minh có thể gỡ deny policy trước rồi mới gọi `StopLogging`. Vì vậy chỉ alert CloudTrail tamper là chưa đủ defense-in-depth.

**Quyết định**

Mandate-12 EventBridge rule bắt hai nhóm action:

CloudTrail tamper:

```text
StopLogging
DeleteTrail
UpdateTrail
PutEventSelectors
PutInsightSelectors
```

IAM guardrail tamper:

```text
DetachRolePolicy
DeletePolicy
DeletePolicyVersion
CreatePolicyVersion
SetDefaultPolicyVersion
PutRolePolicy
DeleteRolePolicy
```

**Outcome**

IAM deny vẫn là preventive control chính. IAM guardrail tamper detection là defense-in-depth bổ sung.

Alert-path tamper như `events:DeleteRule` hoặc `sns:DeleteTopic` không đưa vào Mandate-12 để tránh mở rộng scope quá mức.

## Entry 006 — Dùng `access.auto.tfvars` cho non-secret guardrail config

**User concern**

User hỏi vì sao không dùng `terraform.tfvars` hoặc GitHub Secrets/Env cho role names và bucket ARNs. User cũng hỏi liệu các giá trị này có sensitive không.

**Phản hồi kỹ thuật**

Các giá trị này không phải secret:

- SSO role names không cấp quyền.
- S3 bucket ARN prefixes không cấp quyền.
- Attacker biết tên resource vẫn cần AWS credentials/quyền để làm gì đó.

Nhưng chúng là security-critical config, vì nếu bị remove thì guardrail yếu đi.

**Quyết định**

Dùng `terraform/environments/sandbox/access.auto.tfvars` cho:

```hcl
audit_operator_role_names
cloudtrail_s3_data_event_bucket_arns
enable_mandate_12_alert
```

Không dùng `terraform.tfvars` vì file đó bị ignore, không vào PR review, và GitHub Actions không có file đó từ repo.

Không dùng GitHub Secrets cho role/bucket names vì reviewer/auditor cần thấy rõ trong PR.

**Outcome**

`access.auto.tfvars` là file commit được theo `.gitignore`, Terraform auto-load, và phù hợp cho non-secret access-control/guardrail config.

## Entry 007 — Email dùng GitHub secret/env

**User concern**

User sẽ dùng email cá nhân để nhận SNS alert và không muốn hardcode nếu không cần.

**Phản hồi kỹ thuật**

Email không phải AWS secret, nhưng là privacy-sensitive. Không cần public trong repo.

**Quyết định**

Dùng GitHub secret/env:

```text
MANDATE_12_ALERT_EMAIL
```

Workflow map sang Terraform variable:

```yaml
TF_VAR_mandate_12_alert_email: ${{ secrets.MANDATE_12_ALERT_EMAIL }}
```

**Outcome**

Email không nằm trong `access.auto.tfvars`. Nếu `enable_mandate_12_alert = true`, Terraform phải nhận email qua workflow/local env.

Sau apply, người nhận phải confirm SNS email subscription trước khi mentor test alert path.

## Entry 008 — Defaults an toàn và develop-first rollout

**User concern**

User muốn test trên develop trước rồi mới proceed sandbox.

**Phản hồi kỹ thuật**

Develop có thể dùng để validate Terraform/resource behavior, nhưng không được copy sandbox-specific role names hoặc bucket ARNs nếu account/resource khác.

**Quyết định**

Defaults an toàn:

```hcl
cloudtrail_s3_data_event_bucket_arns = []
enable_mandate_12_alert              = false
mandate_12_alert_email               = ""
```

Sandbox mới bật config thật:

```hcl
enable_mandate_12_alert = true
```

**Outcome**

Develop root được wire variables để tương thích module, nhưng default off. Sandbox là environment quyết định cho mentor verification.

## Entry 009 — Validation strategy cho email

**User concern**

Nếu `enable_mandate_12_alert = true` nhưng email rỗng thì alert path tạo ra vô nghĩa hoặc plan nên fail.

**Phản hồi kỹ thuật**

Cross-variable validation trong variable block dễ gây compatibility/design risk. Terraform workflow đang dùng version mới, nhưng để giảm risk, precondition trong resource rõ ràng hơn.

**Quyết định**

Không dùng cross-variable validation trong variable block. Dùng resource precondition khi tạo Mandate-12 alert resources.

**Outcome**

Nếu bật `enable_mandate_12_alert` mà không truyền email, Terraform plan/apply sẽ fail với message rõ ràng.

## Entry 010 — ADR để cuối

**User concern**

Architecture thay đổi nhiều lần, user muốn hoãn ADR để tránh phải sửa lại liên tục.

**Phản hồi kỹ thuật**

ADR nên ghi decision đã ổn định: tradeoff, cost, SLO impact, rollback, owner. Viết quá sớm dễ churn.

**Quyết định**

ADR để cuối, sau khi Terraform implementation và validation/plan ổn.

**Outcome**

Trước mắt chỉ duy trì docs plan/runbook/external-actions/decision-log. ADR final sẽ được viết sau implementation.

## Entry 011 — Implementation sẽ đi step-by-step và báo trước khi sửa

**User concern**

User muốn kiểm soát thay đổi vì nhiều file Terraform vừa được pull/merge từ develop, và không muốn bị rối.

**Phản hồi kỹ thuật**

Repo hiện có thay đổi mới liên quan gián tiếp:

- Mandate-11 audit-detection packaging.
- Develop RDS proxy/replica.
- Sandbox logical replication.

Các thay đổi này phải được preserve.

**Quyết định**

Implementation đi từng bước nhỏ:

1. Read-only inspect.
2. Sửa module variables.
3. Sửa module resources.
4. Wire sandbox/develop roots.
5. Thêm sandbox `access.auto.tfvars`.
6. Sửa workflow mapping.
7. Thêm outputs.
8. Run fmt/validate.
9. Review diff.
10. ADR cuối.

**Outcome**

Không sửa file khi chưa báo trước. Mỗi step có diff riêng để reviewer dễ hiểu và dễ rollback.
