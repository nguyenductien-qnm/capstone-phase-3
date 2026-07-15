# GitHub Secrets & Variables — sandbox CI/CD

Tài liệu map các giá trị cấu hình lên GitHub cho 4 workflow:
`platform-ci.yaml`, `app-build.yaml`, `infra-cd.yaml`, `infra-destroy.yaml`.

> **Nguyên tắc bảo mật:** `terraform.tfvars` bị `.gitignore` chặn (dòng `*.tfvars`) —
> **không commit**. CI nạp biến qua **Environment Secret `TFVARS_SANDBOX`**
> (bước "Materialize sandbox variables" ghi ra `$RUNNER_TEMP/sandbox.tfvars`).
> File `terraform.tfvars` trong repo chỉ để tham chiếu local; **nguồn thật khi
> chạy CI là secret này**. Đổi tfvars → phải cập nhật lại secret `TFVARS_SANDBOX`.

## 1. Repository Variables (Settings → Secrets and variables → Actions → Variables)

Không nhạy cảm. Đều có default trong workflow (`vars.X || 'default'`) nên **tùy chọn**,
chỉ set khi cần override:

| Variable | Giá trị (khớp tfvars/hạ tầng hiện tại) | Dùng ở |
|---|---|---|
| `AWS_REGION` | `us-east-1` | tất cả |
| `EKS_CLUSTER_NAME` | `ecommerce-dev-eks` | infra-cd, infra-destroy |
| `ECR_REGISTRY` | `804372444787.dkr.ecr.us-east-1.amazonaws.com` | app-build |
| `ECR_REPOSITORY` | `ecommerce-dev-techx-corp` | app-build |
| `IMAGE_VERSION` | `1.0` | app-build |

## 2. Environment Secrets — environment `sandbox` (Settings → Environments → sandbox)

Nhạy cảm. **Bắt buộc** để CD/destroy chạy được:

| Secret | Nội dung | Ghi chú |
|---|---|---|
| `TFVARS_SANDBOX` | **Toàn bộ nội dung** `terraform/environments/sandbox/terraform.tfvars` | Xem mục 3 |
| `TF_AWS_ROLE_ARN` | ARN IAM role cho OIDC (assume từ GitHub Actions) | Ví dụ `arn:aws:iam::804372444787:role/github-actions-terraform` |
| `GITOPS_APP_ID` | App ID của GitHub App bot bump tag | app-build job `bump` |
| `GITOPS_APP_PRIVATE_KEY` | Private key (.pem) của GitHub App đó | dán nguyên khối PEM |

> `GITHUB_TOKEN` (dùng ở `secret-scan`/gitleaks) là token tự động của Actions —
> **không cần tạo**.

## 3. Giá trị `TFVARS_SANDBOX`

Copy **nguyên văn** nội dung file `terraform/environments/sandbox/terraform.tfvars`
(đã bao gồm `kafka_version = "3.9.0"`) vào ô value của secret. Các giá trị đã nhúng
sẵn ARN/domain nên chính secret này cũng nhạy cảm → để ở Environment secret, không phải repo secret.

## 4. Set nhanh bằng `gh` CLI (chạy trên máy có gh + đã `gh auth login`)

```bash
REPO="nguyenductien-qnm/capstone-phase-3"
ENV="sandbox"
TFVARS="terraform/environments/sandbox/terraform.tfvars"

# --- Variables (không nhạy cảm) ---
gh variable set AWS_REGION       --repo "$REPO" --body "us-east-1"
gh variable set EKS_CLUSTER_NAME --repo "$REPO" --body "ecommerce-dev-eks"
gh variable set ECR_REGISTRY     --repo "$REPO" --body "804372444787.dkr.ecr.us-east-1.amazonaws.com"
gh variable set ECR_REPOSITORY   --repo "$REPO" --body "ecommerce-dev-techx-corp"
gh variable set IMAGE_VERSION    --repo "$REPO" --body "1.0"

# --- Environment secrets (nhạy cảm) ---
# TFVARS_SANDBOX = nguyên nội dung file tfvars local
gh secret set TFVARS_SANDBOX --repo "$REPO" --env "$ENV" < "$TFVARS"

# Các secret còn lại (thay giá trị thật):
gh secret set TF_AWS_ROLE_ARN        --repo "$REPO" --env "$ENV" --body "arn:aws:iam::804372444787:role/<github-actions-role>"
gh secret set GITOPS_APP_ID          --repo "$REPO" --env "$ENV" --body "<app-id>"
gh secret set GITOPS_APP_PRIVATE_KEY --repo "$REPO" --env "$ENV" < path/to/gitops-app.private-key.pem
```

## 5. Kiểm tra sau khi set

```bash
gh variable list --repo "$REPO"
gh secret list   --repo "$REPO" --env "$ENV"
```
