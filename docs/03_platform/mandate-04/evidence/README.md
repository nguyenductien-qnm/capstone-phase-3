# MANDATE-04 evidence workspace

Thư mục này chỉ chứa evidence thực tế cho CDO-46, CDO-105 và CDO-106. Không tạo ảnh giả, không chỉnh sửa output để biến FAIL thành PASS, và không lưu access key, token, secret hay nội dung `terraform.tfvars`.

## Cấu trúc

```text
evidence-mandate-04/
├── mandate-04.md             # Evidence pack nộp mentor
├── screenshots/              # Ảnh 01–12 do owner tự chụp
├── logs/                     # Raw command output đã redact
└── queries/                  # CloudWatch Logs Insights queries đã dùng
```

## AWS environment của owner

```powershell
$env:AWS_PROFILE = "phase3-cdo"
$env:AWS_REGION  = "us-east-1"
$Region          = "us-east-1"

aws sso login --profile $env:AWS_PROFILE
aws sts get-caller-identity --profile $env:AWS_PROFILE --region $Region
```

Có thể chạy `. .\docs\cdo09\evidence-mandate-04\set-evidence-environment.ps1` để nạp các biến dùng chung. Script chỉ đặt profile/region và đọc Terraform outputs; không chứa hoặc in credential.

## Quy tắc đặt tên

Lưu ảnh đúng các tên sau:

1. `screenshots/01-terraform-validate.png`
2. `screenshots/02-terraform-plan.png`
3. `screenshots/03-eks-audit-enabled.png`
4. `screenshots/04-cloudwatch-audit-stream.png`
5. `screenshots/05-k8s-forensic-timeline.png`
6. `screenshots/06-cloudtrail-status.png`
7. `screenshots/07-cloudtrail-user-identity.png`
8. `screenshots/08-s3-log-protection.png`
9. `screenshots/09-cloudtrail-validation.png`
10. `screenshots/10-pr-jira-review.png`
11. `screenshots/11-argocd-git-correlation.png`
12. `screenshots/12-operator-explicit-deny.png`

Nếu một mục cần nhiều ảnh, thêm hậu tố `a`, `b`, `c`, ví dụ `07a-github-run.png` và `07b-cloudtrail-session.png`.

## Điều kiện hoàn thành

- Ảnh có command/màn hình nguồn, resource, timestamp và kết quả thực tế.
- Raw output tương ứng được lưu trong `logs/` khi có thể.
- Mục 05 có đủ `create`, `patch`, `delete`, username, timestamp, resource và audit ID.
- Mục 09 là kết quả `aws cloudtrail validate-logs`, không chỉ là `LogFileValidationEnabled=true`.
- Mục 11 nối được ArgoCD revision → Git commit → Pull Request → Jira.
- Mục 12 phải hiện `explicitDeny`; `implicitDeny` không đủ chứng minh tamper policy.
- Chỉ đổi trạng thái trong `mandate-04.md` sang `PASS` sau khi file evidence thật đã tồn tại.
