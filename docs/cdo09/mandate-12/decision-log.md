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

> Đính chính sau independent review: nhận định trên đã lỗi thời. AWS hỗ trợ bật Object Lock trên bucket hiện hữu từ tháng 11/2023; xem Entry 022.

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

## Entry 012 — Step 2: thêm CloudTrail module variables

**User concern**

User muốn implementation đi từng bước và muốn ghi lại log sau mỗi bước để không mất audit trail của quá trình làm việc.

**Phản hồi kỹ thuật**

Step 2 chỉ nên sửa phần input contract của shared CloudTrail module, chưa tạo resource mới. Việc này làm diff nhỏ, dễ review, và chưa ảnh hưởng runtime.

**Quyết định**

Thêm ba biến vào `terraform/modules/cloudtrail/variables.tf`:

```hcl
cloudtrail_s3_data_event_bucket_arns
enable_mandate_12_alert
mandate_12_alert_email
```

Không thêm cross-variable validation ở variable block. Validation email khi alert enabled sẽ được làm bằng resource precondition ở step tạo EventBridge/SNS.

**Outcome**

CloudTrail module giờ có input contract cần thiết cho:

- S3 read data event selector;
- Mandate-12 alert enable flag;
- email receiver truyền từ GitHub secret/env.

## Entry 013 — Step 3: thêm CloudTrail advanced selectors và Mandate-12 alert resources

**User concern**

User confirm tiếp tục Step 3 nhưng vẫn muốn mỗi bước được ghi log và không đụng các phần ngoài scope như Mandate-11 Lambda/SQS/Slack.

**Phản hồi kỹ thuật**

Step 3 là thay đổi chính trong shared CloudTrail module:

- chuyển CloudTrail từ `event_selector` sang `advanced_event_selector`;
- giữ management events;
- thêm optional S3 read data events;
- thêm EventBridge/SNS email alert riêng cho Mandate-12;
- thêm precondition để alert enabled thì email receiver không được rỗng.

**Quyết định**

Sửa `terraform/modules/cloudtrail/main.tf`:

- thêm local `m12_alert_name`;
- thay `event_selector` bằng `advanced_event_selector`;
- tạo SNS topic, SNS topic policy, SNS email subscription, EventBridge rule và EventBridge target khi `enable_mandate_12_alert = true`;
- EventBridge rule bắt CloudTrail tamper actions và IAM guardrail tamper actions.

**Outcome**

Module CloudTrail giờ có logic hạ tầng chính cho Mandate-12, nhưng vẫn không tạo CloudTrail/S3 mới và không sửa Mandate-11 audit-detection resources.

## Entry 014 — Step 4: thêm CloudTrail module outputs

**User concern**

Other AI góp ý rằng module outputs không tự expose ở environment root. Trước hết cần module-level outputs để sau đó root sandbox/develop có thể forward lại.

**Phản hồi kỹ thuật**

Outputs giúp runbook và verification không phải đoán tên resource. Khi alert disabled, output nên trả `null` để develop/default-off không bị lỗi.

**Quyết định**

Thêm hai outputs vào `terraform/modules/cloudtrail/outputs.tf`:

```hcl
mandate_12_alert_rule_name
mandate_12_alert_topic_arn
```

**Outcome**

CloudTrail module giờ expose được EventBridge rule name và SNS topic ARN của Mandate-12 alert path. Environment roots sẽ forward các outputs này ở step sau.

## Entry 015 — Step 5: wire sandbox root

**User concern**

User muốn hiểu mục đích của step này trước khi sửa. Step 5 không bật resource thật mà chỉ nối sandbox root tới các input/output mới của CloudTrail module.

**Phản hồi kỹ thuật**

Terraform có nhiều tầng:

```text
sandbox root → cloudtrail module → AWS resources
```

Sau Step 2–4, shared module đã có input/output mới nhưng sandbox root chưa truyền các giá trị đó vào module.

**Quyết định**

Sửa sandbox root:

- thêm root variables cho S3 data event bucket ARNs, enable flag, và email receiver;
- truyền các variables đó vào `module "cloudtrail"`;
- expose root outputs cho Mandate-12 EventBridge rule name và SNS topic ARN.

**Outcome**

Sandbox root đã có dây nối tới CloudTrail module để dùng Mandate-12 controls. Step này chưa set giá trị thật; giá trị sandbox sẽ được set ở `access.auto.tfvars` trong step sau.

## Entry 016 — Step 6: wire develop root với defaults off

**User concern**

User muốn test develop trước sandbox nhưng không muốn copy nhầm role names hoặc bucket ARNs của sandbox sang develop.

**Phản hồi kỹ thuật**

Develop root cần được wire với input/output mới để shared CloudTrail module contract nhất quán giữa environments. Tuy nhiên develop phải giữ defaults an toàn để không tạo alert/S3 data event resources nếu chưa có config develop-specific.

**Quyết định**

Sửa develop root:

- thêm variables `cloudtrail_s3_data_event_bucket_arns`, `enable_mandate_12_alert`, `mandate_12_alert_email`;
- default giữ `[]`, `false`, `""`;
- truyền variables vào `module "cloudtrail"`;
- expose root outputs cho Mandate-12 EventBridge rule name và SNS topic ARN.

**Outcome**

Develop root tương thích với CloudTrail module mới nhưng không bật Mandate-12 controls mặc định. Sandbox vẫn là environment quyết định cho mentor verification.

## Entry 017 — Step 7: thêm sandbox `access.auto.tfvars`

**User concern**

User muốn bật giá trị thật cho sandbox nhưng không muốn đưa email cá nhân vào repo.

**Phản hồi kỹ thuật**

`access.auto.tfvars` phù hợp cho non-secret security-critical config cần review trong PR. Email người nhận là privacy-sensitive nên đi qua GitHub secret/env, không ghi vào file này.

**Quyết định**

Tạo `terraform/environments/sandbox/access.auto.tfvars` với:

```hcl
audit_operator_role_names = [
  "AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568",
  "AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33"
]

cloudtrail_s3_data_event_bucket_arns = [
  "arn:aws:s3:::ecommerce-dev-cloudtrail-logs/",
  "arn:aws:s3:::terraform-state-phase-3/"
]

enable_mandate_12_alert = true
```

**Outcome**

Sandbox sẽ bật:

- IAM deny attachment cho CDO/Mentor SSO roles;
- S3 read data events cho CloudTrail logs bucket và Terraform state bucket;
- EventBridge/SNS alert path riêng của Mandate-12.

Email vẫn phải được truyền bằng `MANDATE_12_ALERT_EMAIL` qua GitHub Actions hoặc local `TF_VAR_mandate_12_alert_email`.

## Entry 018 — Step 8: map GitHub secret cho Mandate-12 email alert

**User concern**

CI/CD workflow thuộc ownership của teammate, user không muốn tự ý sửa hoặc lấn scope.

**Phản hồi kỹ thuật**

Sau khi CI/CD owner approve, có thể thêm mapping tối thiểu trong `infra-cd.yaml`. Email vẫn không hardcode trong repo; repo chỉ chứa tên secret `MANDATE_12_ALERT_EMAIL`.

**Quyết định**

Thêm mapping sau vào cả Terraform plan job và Terraform apply job:

```yaml
TF_VAR_mandate_12_alert_email: ${{ secrets.MANDATE_12_ALERT_EMAIL }}
```

**Outcome**

Sandbox CI/CD có thể truyền email alert vào Terraform để tạo SNS email subscription cho Mandate-12. GitHub Environment `sandbox` vẫn cần có secret `MANDATE_12_ALERT_EMAIL`; nếu thiếu, Terraform sẽ fail khi Mandate-12 alert đang bật thay vì tạo alert path không có người nhận.

## Entry 019 — Step 9: chạy local checks an toàn, không apply local

**User concern**

User nhắc rằng project deploy qua AWS/GitHub Actions nên không muốn chạy Terraform local theo kiểu can thiệp hạ tầng thật.

**Phản hồi kỹ thuật**

Local checks được giới hạn ở format/syntax validation:

- `terraform fmt -recursive terraform`;
- `git diff --check`;
- `terraform init -backend=false`;
- `terraform validate`.

Không chạy `terraform plan`, `terraform apply`, hoặc `terraform destroy` local.

**Quyết định**

Chạy validate cho:

- `terraform/modules/cloudtrail`;
- `terraform/environments/sandbox`;
- `terraform/environments/develop`.

**Commands đã chạy**

```bash
terraform fmt -recursive terraform
git diff --check
terraform -chdir=terraform/modules/cloudtrail init -backend=false -input=false
terraform -chdir=terraform/modules/cloudtrail validate
terraform -chdir=terraform/environments/sandbox init -backend=false -input=false
terraform -chdir=terraform/environments/sandbox init -backend=false -input=false
terraform -chdir=terraform/environments/sandbox validate
terraform -chdir=terraform/environments/develop init -backend=false -input=false
terraform -chdir=terraform/environments/develop init -backend=false -input=false
terraform -chdir=terraform/environments/develop validate
terraform -chdir=terraform/environments/develop validate
git status --short --branch
```

Ghi chú:

- Sandbox/develop init lần đầu fail do DNS/network sandbox, rerun ngoài sandbox với cùng `-backend=false`.
- Develop validate lần đầu fail do plugin execution restriction, rerun ngoài sandbox pass.
- Không chạy `terraform plan`, `terraform apply`, hoặc `terraform destroy`.

**Outcome**

Kết quả:

- `terraform fmt -recursive terraform`: pass, không tạo format diff mới;
- `git diff --check`: pass;
- CloudTrail module validate: pass, có warning cũ `data.aws_region.current.name` deprecated;
- Sandbox root validate: pass, có warning local `terraform.tfvars` chứa `nlb_dns_name` chưa declare, không liên quan Mandate-12 và file này gitignored;
- Develop root validate: pass khi chạy ngoài sandbox execution restriction.

Terraform init tạo side-effect lockfile trong module và làm thay đổi sandbox lockfile; các side-effect này đã được dọn, không còn nằm trong diff.

## Entry 020 — Step 10A: sửa docs khớp implementation trước commit

**User concern**

Other AI và pre-commit review phát hiện docs còn hai điểm dễ gây hiểu nhầm: docs ghi cross-variable `validation` trong variable block dù code thật dùng `lifecycle.precondition`, và wording "rollout develop trước" khiến teammate nghĩ phải runtime test Mandate-12 trên develop.

**Phản hồi kỹ thuật**

Code hiện tại đúng theo quyết định kỹ thuật:

- không dùng cross-variable validation trong variable block;
- enforce email required bằng `lifecycle.precondition` khi `enable_mandate_12_alert = true`;
- develop root chỉ wire interface và giữ default off;
- sandbox mới bật Mandate-12 controls thật qua `access.auto.tfvars`.

**Quyết định**

Sửa docs:

- `implementation-plan.md`: bỏ ví dụ validation sai, ghi rõ precondition là nơi enforce email requirement;
- `implementation-plan.md`: đổi rollout wording thành "Develop static validation; sandbox runtime verification";
- `external-actions.md`: ghi rõ develop chỉ cần email secret nếu sau này bật Mandate-12 runtime ở develop;
- `README.md`: clarify rollout hiện tại là static validation cho develop, sandbox plan/apply/verify cho runtime.

**Outcome**

Docs khớp implementation hiện tại và giảm rủi ro reviewer/teammate hiểu nhầm rằng phải apply/test runtime trên develop trước khi sandbox.

## Entry 021 — Đồng bộ develop và hoàn tất validation trước khi cập nhật PR

**User concern**

User xác nhận phạm vi hiện tại chỉ là hoàn thiện PR để teammate review, approve và merge vào `develop`; không deploy hoặc chạy Terraform apply local. User cũng yêu cầu kiểm tra lại sau khi `origin/develop` có thay đổi mới trong workflow CI/CD.

**Phản hồi kỹ thuật**

`origin/develop` bổ sung chế độ Terraform `refresh_only` trong `.github/workflows/infra-cd.yaml`, trong khi Mandate-12 bổ sung mapping `TF_VAR_mandate_12_alert_email` vào cùng workflow. Hai thay đổi có thể cùng tồn tại:

- `refresh_only` điều khiển plan mode và bỏ qua ArgoCD bootstrap khi chỉ refresh state;
- `TF_VAR_mandate_12_alert_email` truyền GitHub Environment secret vào Terraform plan/apply;
- không thay đổi kiến trúc hoặc scope Mandate-12.

Local validation cần provider cache, nên chạy `terraform init -backend=false` trước `terraform validate`. Thao tác này không kết nối Terraform backend, không chạy plan/apply và không thay đổi AWS.

**Quyết định**

- Tạo checkpoint commit `94868bc` cho implementation Mandate-12.
- Merge `origin/develop` bằng merge commit `b455251`; merge thành công, không có conflict.
- Giữ cả thay đổi `refresh_only` từ develop và secret mapping Mandate-12 trong workflow.
- Chạy format, whitespace check và validate module/root configuration.
- Không commit thay đổi lockfile phát sinh ngoài scope.

**Commands đã chạy**

```bash
git merge origin/develop
terraform fmt -check -recursive terraform
git diff --check
terraform -chdir=terraform/modules/cloudtrail init -backend=false -input=false
terraform -chdir=terraform/modules/cloudtrail validate
terraform -chdir=terraform/environments/sandbox init -backend=false -input=false
terraform -chdir=terraform/environments/sandbox validate
terraform -chdir=terraform/environments/develop validate
git restore -- terraform/environments/sandbox/.terraform.lock.hcl
git status --short --branch
git diff --check
```

Lockfile mới trong `terraform/modules/cloudtrail` do local init tạo ra đã được xóa sau validation. Sandbox lockfile được khôi phục về đúng phiên bản trong Git.

**Outcome**

- Merge develop: pass, không conflict.
- `terraform fmt -check -recursive terraform`: pass.
- `git diff --check`: pass.
- CloudTrail module validate: pass; chỉ có warning cũ `data.aws_region.current.name` deprecated.
- Sandbox root validate: pass; chỉ có warning local `terraform.tfvars` chứa `nlb_dns_name` chưa declare.
- Develop root validate: pass.
- Không chạy Terraform plan/apply/destroy và không thay đổi AWS.
- Sau cleanup, working tree sạch trước khi cập nhật decision log.

## Entry 022 — Independent review: sửa runbook, Object Lock và mô tả SSO workaround

**User concern**

User yêu cầu đọc lại project và xác nhận Mandate-12 có được triển khai đúng hay không trước khi tạo PR implementation mới.

**Phản hồi kỹ thuật**

Review phát hiện:

- `aws cloudtrail lookup-events` chỉ trả management events, nên không thể dùng để chứng minh S3 `GetObject` data event;
- AWS đã hỗ trợ bật S3 Object Lock trên bucket hiện hữu có versioning từ tháng 11/2023; việc bật là không thể đảo ngược và object cũ không tự nhận default retention;
- attach policy trực tiếp vào `AWSReservedSSO_*` roles chỉ là workaround vì role do IAM Identity Center quản lý;
- workaround chặn direct CloudTrail tamper nhưng không loại bỏ mọi chuỗi bypass, ví dụ routine admin tắt alert path trước khi gỡ policy;
- break-glass exemption trong code hiện chỉ áp dụng cho CloudTrail tamper statement, không áp dụng cho S3, CloudWatch Logs và KMS deny statements.

**Quyết định**

- Đổi runbook S3 evidence sang CloudWatch Logs `filter-log-events`;
- đính chính Object Lock và defer sang follow-up vì tính không thể đảo ngược/risk review, không phải vì AWS không hỗ trợ;
- yêu cầu reviewer/adminHolder chấp nhận residual risk của direct SSO attachment trước deploy;
- không sửa Terraform core trong bước documentation correction này;
- redact account ID đầy đủ khỏi nội dung mới/chỉnh sửa của Mandate-12.

**Outcome**

Tài liệu không còn hướng dẫn command chắc chắn thất bại khi demo S3 data event và mô tả trung thực giới hạn của kiến trúc hiện tại. Implementation vẫn cần PR review, Terraform plan và adminHolder acceptance trước khi deploy.

## Entry 023 — Chuyển IAM deny ownership sang Identity Center Permission Sets

**User concern**

User phối hợp với adminHolder để attach policy ở IAM Identity Center Permission Set và muốn tránh Terraform cùng quản lý generated `AWSReservedSSO_*` roles.

**Phản hồi kỹ thuật**

Live verification ngày 20/07/2026 cho thấy:

- policy `ecommerce-dev-audit-log-tamper-deny` có `AttachmentCount = 2`;
- policy xuất hiện trên đúng generated CDO và Mentor SSO roles;
- IAM Simulator trả `explicitDeny` cho `StopLogging`, `DeleteTrail` và `PutEventSelectors` trên cả hai role;
- CDO role bị explicit deny khi gọi `sso:ListInstances`, nên không thể independently verify cấu hình Permission Set bằng CLI;
- screenshot IAM role chứng minh effective attachment, nhưng không tự chứng minh Permission Set ownership.

**Quyết định**

- AdminHolder/IAM Identity Center sở hữu attachment tại `Phase3-CDO-PermissionSet` và `Phase3-Mentor-PermissionSet`.
- Bỏ `audit_operator_role_names` khỏi sandbox `access.auto.tfvars`; shared module vẫn giữ generic variable với default `[]`.
- Không để Terraform attach trực tiếp policy vào generated `AWSReservedSSO_*` roles.
- Dùng attachment checks và IAM Simulator làm runtime enforcement evidence; dùng adminHolder screenshot/config đã redact làm Permission Set ownership evidence.

**Outcome**

Preventive control “làm mù” đã được xác minh effective cho CDO và Mentor. Repo không tạo dual ownership giữa Terraform và IAM Identity Center; S3 selector và Mandate-12 alert vẫn chờ PR merge, protected apply và runtime verification.

## Entry 024 — Tạo evidence workspace cho Mandate-12

**User concern**

User yêu cầu kiểm tra format evidence của các mandate khác và muốn Mandate-12 theo cùng convention, nhưng không tạo một pack nặng hoặc evidence giả.

**Phản hồi kỹ thuật**

Mandate-04 là evidence pack đầy đủ duy nhất trong `docs/cdo09`. Pattern hữu ích gồm evidence matrix, evidence index, runtime results, raw logs, screenshot checklist, quy tắc redaction và nguyên tắc chỉ đánh dấu `PASS` sau runtime verification.

**Quyết định**

- Tạo `docs/cdo09/evidence-mandate-12/` theo pattern Mandate-04 nhưng rút gọn cho ba đòn làm mù/làm hụt/làm giả.
- Tách 10 acceptance IDs cho CI plan, baseline trail, IAM attachment/deny, S3 selectors/event, EventBridge/SNS, integrity validation và PR/Jira attribution.
- Không lưu output mẫu như raw evidence.
- Các control đã verify nhưng chưa capture vào pack để `PARTIAL`; code chưa deploy để `PENDING`.
- Không commit screenshot hiện tại như Permission Set evidence vì ảnh là generated IAM role page và chứa full account ID.

**Outcome**

Evidence workspace đã sẵn sàng để capture kết quả thật theo từng bước sau PR merge/protected apply mà không tuyên bố sớm Mandate-12 đã `PASS`.

## Entry 025 — Capture IAM attachment và explicit-deny evidence

**User concern**

User confirm Step 3 để lưu evidence thật cho preventive control “làm mù”, không chạy destructive CloudTrail command.

**Commands đã chạy**

- `aws iam list-policies` với query chỉ giữ policy name, attachment count và default version.
- `aws iam list-attached-role-policies` cho CDO và Mentor generated roles.
- `aws iam simulate-principal-policy` cho CDO và Mentor với `StopLogging`, `DeleteTrail` và `PutEventSelectors`.

**Kết quả**

- Policy `ecommerce-dev-audit-log-tamper-deny`: `AttachmentCount = 2`, version `v1`.
- Policy xuất hiện trên đúng CDO và Mentor generated roles.
- Sáu simulation results đều là `explicitDeny`.
- Không gọi thật `StopLogging`, `DeleteTrail` hoặc thay đổi AWS.
- Saved evidence bỏ account-specific ARNs nhưng giữ role name, action và decision.

**Outcome**

Evidence 03 được đánh dấu `PASS enforcement`; Permission Set ownership dựa trên adminHolder confirmation. Evidence 04 được đánh dấu `PASS` với raw output đã lưu.

## Entry 026 — Review toàn bộ diff và static validation trước commit

**User concern**

User confirm Step 4 để rà toàn bộ implementation, workflow, docs và evidence trước khi commit; không chạy Terraform plan/apply.

**Phạm vi review**

- So sánh working tree cuối với `origin/develop`.
- Kiểm tra CloudTrail advanced selectors, EventBridge/SNS resources, variables/outputs và sandbox/develop wiring.
- Kiểm tra GitHub Actions secret mapping ở cả plan/apply jobs.
- Kiểm tra IAM ownership sau khi bỏ direct role names khỏi `access.auto.tfvars`.
- Rà account ID, email, secret và evidence JSON.
- Chạy Terraform format/init-without-backend/validate.

**Kết quả**

- `git diff --check`: pass.
- `terraform fmt -check -recursive terraform`: pass.
- CloudTrail module validate: pass; chỉ có warning cũ về `data.aws_region.current.name`.
- Sandbox validate: pass; chỉ có warning local `terraform.tfvars` chứa `nlb_dns_name` chưa declare.
- Develop validate: pass.
- Advanced selectors giữ management events và thêm read-only S3 object data events đúng biến input.
- Mandate-12 alert resources conditional, yêu cầu email khác rỗng và SNS policy chỉ cho đúng EventBridge rule publish.
- GitHub secret mapping có ở cả plan và apply.
- Sandbox không còn set `audit_operator_role_names`; Identity Center/adminHolder là owner của deny attachment.
- Evidence JSON parse hợp lệ và không chứa account ID/ARN/email/secret.
- Không chạy Terraform plan/apply/destroy và không thay đổi AWS.

`terraform init -backend=false` chỉ được dùng để tải provider schema cho static validation. Lockfile sandbox phát sinh thay đổi đã được restore; lockfile module phát sinh ngoài scope đã được xóa.

**Residual checks sau merge/apply**

- Review protected Terraform plan để chắc không replace/destroy trail hoặc audit bucket và không detach IAM deny.
- Confirm SNS email subscription.
- Capture Advanced Event Selectors, actual S3 `GetObject` event, EventBridge/SNS configuration và interval `validate-logs`.

**Outcome**

Không phát hiện blocker code/static ở Step 4. Branch sẵn sàng cho final diff review của user trước commit; runtime controls chưa deploy vẫn giữ `PENDING`.
