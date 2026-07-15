# GitHub Secrets & Variables — sandbox CI/CD

Tài liệu map các giá trị cấu hình lên GitHub cho 4 workflow:
`platform-ci.yaml`, `app-build.yaml`, `infra-cd.yaml`, `infra-destroy.yaml`.

> **Nguyên tắc bảo mật:** `terraform.tfvars` bị `.gitignore` chặn (dòng `*.tfvars`) —
> **không commit**. File sandbox hiện chỉ chứa cấu hình không nhạy cảm, nên CI nạp
> qua **Repository Variable `TFVARS_SANDBOX`**
> (bước "Materialize sandbox variables" ghi ra `$RUNNER_TEMP/sandbox.tfvars`).
> File `terraform.tfvars` trong repo chỉ để tham chiếu local; **nguồn thật khi
> chạy CI là repository variable này**. Đổi tfvars → phải cập nhật lại
> `TFVARS_SANDBOX`.

## 1. Repository Variables (Settings → Secrets and variables → Actions → Variables)

Không nhạy cảm. Các giá trị có ghi "bắt buộc" phải được cấu hình trước khi chạy workflow:

| Variable | Giá trị (khớp tfvars/hạ tầng hiện tại) | Dùng ở |
|---|---|---|
| `AWS_REGION` | `us-east-1` | tất cả |
| `EKS_CLUSTER_NAME` | `ecommerce-dev-eks` | infra-cd, infra-destroy |
| `ECR_REGISTRY` | `804372444787.dkr.ecr.us-east-1.amazonaws.com` | app-build |
| `ECR_REPOSITORY` | `ecommerce-dev-techx-corp` | app-build |
| `IMAGE_VERSION` | `1.0` | app-build |
| `TFVARS_SANDBOX` | Toàn bộ nội dung `terraform/environments/sandbox/terraform.tfvars` | infra-cd, infra-destroy; bắt buộc |
| `TF_AWS_ROLE_ARN` | ARN IAM role OIDC của GitHub Actions | app-build, infra-cd, infra-destroy; bắt buộc |
| `GITOPS_APP_ID` | App ID của GitHub App bot bump tag | app-build job `bump`; bắt buộc |

Trong giai đoạn chuyển đổi, workflow tạm fallback về Repository Secret
`GITOPS_APP_ID` nếu Repository Variable cùng tên chưa được tạo. Sau khi set variable,
xóa secret cũ để hoàn tất migration.

## 2. Repository Secrets (Settings → Secrets and variables → Actions → Secrets)

Chỉ giữ dữ liệu bí mật thực sự:

| Secret | Nội dung | Ghi chú |
|---|---|---|
| `GITOPS_APP_PRIVATE_KEY` | Private key (.pem) của GitHub App đó | dán nguyên khối PEM |

> `GITHUB_TOKEN` (dùng ở `secret-scan`/gitleaks) là token tự động của Actions —
> **không cần tạo**.

## 3. Giá trị `TFVARS_SANDBOX`

Copy **nguyên văn** nội dung file `terraform/environments/sandbox/terraform.tfvars`
vào Repository Variable. ARN, domain, CIDR, instance type và username không phải secret.
Không đưa password, token, access key hoặc private key vào biến này.

Environment `sandbox` vẫn được workflow sử dụng cho deployment protection và OIDC
subject, nhưng không lưu variable/secret ở scope Environment.

## 4. Set nhanh bằng `gh` CLI (chạy trên máy có gh + đã `gh auth login`)

```bash
REPO="nguyenductien-qnm/capstone-phase-3"
TFVARS="terraform/environments/sandbox/terraform.tfvars"

# --- Variables (không nhạy cảm) ---
gh variable set AWS_REGION       --repo "$REPO" --body "us-east-1"
gh variable set EKS_CLUSTER_NAME --repo "$REPO" --body "ecommerce-dev-eks"
gh variable set ECR_REGISTRY     --repo "$REPO" --body "804372444787.dkr.ecr.us-east-1.amazonaws.com"
gh variable set ECR_REPOSITORY   --repo "$REPO" --body "ecommerce-dev-techx-corp"
gh variable set IMAGE_VERSION    --repo "$REPO" --body "1.0"
gh variable set TF_AWS_ROLE_ARN  --repo "$REPO" --body "arn:aws:iam::804372444787:role/GitHubTerraformSandboxRole"
gh variable set GITOPS_APP_ID    --repo "$REPO" --body "<app-id>"
gh variable set TFVARS_SANDBOX   --repo "$REPO" < "$TFVARS"

# --- Repository secret (nhạy cảm) ---
gh secret set GITOPS_APP_PRIVATE_KEY --repo "$REPO" < path/to/gitops-app.private-key.pem
```

## 5. Kiểm tra sau khi set

```bash
gh variable list --repo "$REPO"
gh secret list   --repo "$REPO"
```
