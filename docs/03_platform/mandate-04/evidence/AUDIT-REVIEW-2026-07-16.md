# MANDATE-04 independent audit review — 2026-07-16

## Kết luận

**Chưa đủ điều kiện kết luận PASS toàn bộ Mandate 04.** IaC và tooling local đã qua validation, nhưng runtime control mới chưa được chứng minh đã apply. Các blocker còn lại là Terraform plan thật, EKS retention/KMS, S3 versioning, GitHub-run attribution và Operator `explicitDeny`.

Mandate gốc ghi chỉ TF4, trong khi `RULES.md` đặt CDO09 trong TF1 và Jira/repository giao CDO-46/CDO-105/CDO-106 cho CDO09. Không sửa mandate gốc; đây là governance inconsistency cần mentor xác nhận, còn review này vẫn áp dụng acceptance kỹ thuật Mandate 04.

## Kết quả lệnh thực tế

| Check / acceptance | Command | Exit code | Output thực tế rút gọn | Evidence |
|---|---|---:|---|---|
| Git remote state | `git fetch origin` | 0 | Fetch thành công | terminal review 16/07; commit merge `1a974ac` |
| Branch đồng bộ develop | `git rev-list --left-right --count origin/develop...HEAD` | 0 | Trước merge `23 2`; sau merge không còn commit nào thiếu từ develop (`left=0`) | Git history local |
| Scope | PowerShell classify `git diff --name-only origin/develop` | 0 | `FORBIDDEN_COUNT=0`, `FLAGD_DIFF_COUNT=0`, `BUSINESS_LOGIC_DIFF_COUNT=0` | terminal review 16/07 |
| Conflict artifacts | `rg -l '^(<<<<<<<|>>>>>>>)' .` | 1 (không có match) | `CONFLICT_MARKER_COUNT=0` | terminal review 16/07 |
| Terraform format | `terraform -chdir=terraform/environments/sandbox fmt -check -recursive ../../` | 0 | Không có format error | terminal review 16/07 |
| Terraform init (không backend) | `terraform -chdir=terraform/environments/sandbox init -backend=false -input=false` | 0 | `Terraform has been successfully initialized!` | terminal review 16/07 |
| Terraform validate | `terraform -chdir=terraform/environments/sandbox validate` | 0 | `Success! The configuration is valid.` | terminal review 16/07 |
| Terraform plan thật | `terraform ... plan -refresh=false -lock=false -input=false -var-file=primary-capacity.tfvars` | 1 | Backend S3 chưa init bằng session hợp lệ; `terraform.tfvars` thật không tồn tại | `logs/02-plan-diagnostic-missing-vars.txt` và review 16/07 |
| Helm lint | `helm lint ... -f values-external-secrets.yaml ...` | 0 | `1 chart(s) linted, 0 chart(s) failed` | terminal review 16/07 |
| Helm render | `helm template techx-corp ...` | 0 | `HELM_RENDER_LINES=20708`, không rỗng | terminal review 16/07 |
| PowerShell verifier syntax | `Parser.ParseFile(verify-auditability.ps1)` | 0 | `POWERSHELL_PARSE_EXIT=0` | terminal review 16/07 |
| Bash script syntax | `bash -n scripts/validate/{verify-auditability,forensic-*}.sh` | 0 | `BASH_SYNTAX_EXIT=0` | terminal review 16/07 |
| Static audit controls | PowerShell assertions trên Terraform/workflows/template | 0 | 14/14 PASS: EKS logs/KMS, CloudTrail coverage, S3 controls, tamper actions, GitHub session, PR fields | terminal review 16/07 |
| AWS runtime re-test | `aws sts get-caller-identity`, `aws eks describe-cluster`, `aws cloudtrail get-trail` | 255 | `Token has expired and refresh failed` | terminal review 16/07 |
| Unit tests baseline | `go test ./...` | NOT RUN | `go` không có trong PATH; không sửa business code | terminal review 16/07 |

Lưu ý: lần đầu chạy Git Bash trong sandbox trả lỗi Win32 `CreateFileMapping ... error 5`; chạy lại ngoài sandbox cho bốn script `--help` và `bash -n` đều exit 0. Đây là lỗi môi trường local, không phải script.

## Acceptance matrix

| Mentor acceptance | Code/static | Runtime evidence | Verdict |
|---|---|---|---|
| Kubernetes/EKS audit logs | `api/audit/authenticator`, retention input ≥30, KMS, `prevent_destroy` | Log types/stream và forensic timeline có evidence 15/07; runtime retention/KMS cũ chưa đạt | PARTIAL |
| CloudTrail/change trail | Multi-region/global, management read/write, validation, CloudWatch, actor/run session | Trail/validation lịch sử PASS; GitHub session sau deploy chưa có | PARTIAL |
| Forensic ai-làm-gì-khi-nào | Query/scripts + change record + PR template | K8s drill và ArgoCD correlation lịch sử PASS | PASS lịch sử; cần mentor re-run tại chỗ |
| Tamper-evident | S3 versioning/KMS/lifecycle/public block; expanded explicit-deny policy | Runtime 15/07 chưa versioning; simulator trả allowed | FAIL runtime |
| Identity attribution | Individual SSO + `gha-<actor>-<run_id>` ở mọi AWS OIDC step | SSO individual PASS lịch sử; GitHub session chưa deploy | PARTIAL |
| Không phá flagd/storefront/private ops/business logic | Diff classifier không có file flagd/business logic ngoài scope | Helm render PASS | PASS local |
| Cost | Management events only; retention/lifecycle; không bật broad data events | Chưa có Cost Explorer/plan estimate sau apply | PARTIAL |

## Gap đã sửa trong review này

- Bổ sung các tamper action còn thiếu: CloudTrail selectors, CloudWatch retention/KMS, S3 overwrite/policy/encryption/lifecycle/public-block/Object-Lock và KMS disable/policy/grant.
- Mở rộng PR template với owner, reviewer, resource, before/after, blast radius, plan/render, run ID, rollback và evidence.
- Verifier yêu cầu EKS retention ≥30 ngày, EKS/CloudTrail KMS, multi-region/global, management selector và hỗ trợ IAM simulation `explicitDeny`.
- Forensic K8s demo dùng namespace duy nhất và cleanup bằng `trap`.
- Platform CI dùng đúng sandbox External Secrets overlay mà không giữ thay đổi chart ngoài scope.
- Merge `origin/develop`, giữ nguyên Karpenter và các task mới của thành viên khác.
- Redact account ID khỏi sáu raw evidence file; không phát hiện access-key/private-key pattern.

## MANUAL ACTION REQUIRED

Không chạy `terraform apply`, destructive CloudTrail/S3 test hoặc thay IAM thật trong review này.

1. Làm mới SSO:

   ```powershell
   aws sso login --profile phase3-cdo
   $env:AWS_PROFILE = "phase3-cdo"
   $env:AWS_REGION = "us-east-1"
   ```

2. Push các commit mới để PR #93 nhận merge commit và chạy CI; yêu cầu ít nhất một reviewer độc lập approval.
3. Cung cấp `TFVARS_SANDBOX` qua GitHub Environment `sandbox`, review plan artifact, rồi chỉ người có thẩm quyền mới approve/apply.
4. Sau apply, chạy read-only verifier:

   ```powershell
   .\scripts\validate\verify-auditability.ps1 `
     -Region us-east-1 `
     -ClusterName ecommerce-dev-eks `
     -TrailName ecommerce-dev-audit-trail `
     -OperatorPrincipalArn "<DEDICATED_OPERATOR_ROLE_ARN>"
   ```

5. Chỉ đánh dấu PASS khi output có retention ≥30, KMS, versioning và mọi action simulator là `explicitDeny`. Không chạy thật `stop-logging` hoặc delete S3 object.
