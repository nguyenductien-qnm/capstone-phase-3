# GitHub Secrets & Variables — sandbox CI/CD

Tài liệu map cấu hình cho `app-build.yaml`, `infra-cd.yaml` và
`infra-destroy.yaml`. Tất cả được đặt ở **Repository scope**, không đặt dữ liệu
trong GitHub Environment `sandbox`.

Environment `sandbox` vẫn được job sử dụng cho deployment protection và GitHub
OIDC subject.

## 1. Repository Variables dùng chung

| Variable | Mục đích |
|---|---|
| `AWS_REGION` | AWS region của workflow |
| `EKS_CLUSTER_NAME` | Tên EKS cluster |
| `ECR_REGISTRY` | ECR registry của application |
| `ECR_REPOSITORY` | ECR repository của application |
| `IMAGE_VERSION` | Prefix version của image tag |
| `TF_AWS_ROLE_ARN` | ARN IAM role mà GitHub Actions assume bằng OIDC |
| `GITOPS_APP_ID` | App ID của GitHub App dùng để bump image tag |

ARN, account ID, region, cluster name và GitHub App ID không phải secret.

## 2. Repository Variables cho Terraform

Mỗi Terraform input là một Repository Variable riêng. Quy ước mapping:

```text
Repository Variable TF_VAR_VPC_CIDR
               -> env TF_VAR_vpc_cidr
               -> Terraform variable vpc_cidr
```

String lưu dưới dạng text thuần. Boolean/number lưu dưới dạng literal. List/map
lưu dưới dạng JSON hoặc biểu thức HCL hợp lệ.

### Network

```text
TF_VAR_AWS_REGION
TF_VAR_PROJECT_NAME
TF_VAR_ENVIRONMENT
TF_VAR_VPC_CIDR
TF_VAR_PUBLIC_SUBNETS
TF_VAR_PRIVATE_APP_SUBNETS
TF_VAR_PRIVATE_DATA_SUBNETS
TF_VAR_PRIVATE_MQ_SUBNETS
TF_VAR_ENABLE_NAT_GATEWAY
TF_VAR_SINGLE_NAT_GATEWAY
TF_VAR_PUBLIC_SUBNET_TAGS
TF_VAR_PRIVATE_SUBNET_TAGS
```

### EKS

```text
TF_VAR_EKS_CLUSTER_VERSION
TF_VAR_EKS_NODE_CAPACITY_TYPE
TF_VAR_EKS_ENDPOINT_PUBLIC_ACCESS
TF_VAR_EKS_PUBLIC_ACCESS_CIDRS
TF_VAR_EKS_CONTROL_PLANE_LOG_RETENTION_DAYS
TF_VAR_EKS_ACCESS_ENTRIES
```

`eks_node_instance_types` và `eks_node_scaling` không đặt ở GitHub Variables.
Source of truth của hai biến này là file version-controlled
`terraform/environments/sandbox/primary-capacity.tfvars`.

Các input EKS optional còn lại dùng default trong `variables.tf` nếu không được
override.

### RDS, MSK, Valkey và ECR

```text
TF_VAR_DB_NAME
TF_VAR_DB_USERNAME
TF_VAR_RDS_INSTANCE_CLASS
TF_VAR_RDS_ALLOCATED_STORAGE
TF_VAR_ENABLE_READ_REPLICA
TF_VAR_REPLICA_INSTANCE_CLASS
TF_VAR_ENABLE_RDS_PROXY
TF_VAR_RDS_MULTI_AZ
TF_VAR_KAFKA_VERSION
TF_VAR_VALKEY_NODE_TYPE
TF_VAR_VALKEY_NUM_CACHE_CLUSTERS
TF_VAR_ECR_REPOSITORIES
```

### DNS và CloudFront

```text
TF_VAR_ROUTE53_ZONE_ID
TF_VAR_SUBDOMAIN
TF_VAR_ACM_CERTIFICATE_ARN
TF_VAR_ENABLE_CLOUDFRONT
```

## 3. Repository Secrets

Chỉ giữ dữ liệu bí mật thực sự:

| Secret | Nội dung |
|---|---|
| `GITOPS_APP_PRIVATE_KEY` | Private key PEM của GitHub App |

`GITHUB_TOKEN` do GitHub Actions tự tạo, không cần cấu hình thủ công.

Không đưa password, token, AWS access key hoặc private key vào Repository
Variables. Password RDS/Valkey được Terraform sinh và lưu trong AWS Secrets
Manager, không truyền qua GitHub Actions.

## 4. Source of truth

```text
Terraform configuration  -> individual Repository Variables TF_VAR_*
Primary node capacity    -> primary-capacity.tfvars trong Git
Optional defaults        -> variables.tf
Sensitive credential    -> Repository Secrets / AWS Secrets Manager
```

Workflow không còn đọc `TFVARS_SANDBOX` và không tạo file
`$RUNNER_TEMP/sandbox.tfvars`.

## 5. Hoàn tất migration

Chỉ chạy cleanup sau khi workflow mới đã merge và Terraform plan thành công:

```bash
REPO="nguyenductien-qnm/capstone-phase-3"

# Biến nguyên-file cũ không còn được dùng.
gh variable delete TFVARS_SANDBOX --repo "$REPO"
gh secret delete TFVARS_SANDBOX --repo "$REPO"

# ARN đã chuyển thành Repository Variable TF_AWS_ROLE_ARN.
gh secret delete TF_AWS_ROLE_ARN --repo "$REPO" --env sandbox

# Sau khi tạo Repository Variable GITOPS_APP_ID từ GitHub App Settings:
gh secret delete GITOPS_APP_ID --repo "$REPO"
```

Kiểm tra tên cấu hình mà không in giá trị:

```bash
gh variable list --repo "$REPO" --json name --jq '.[].name'
gh secret list --repo "$REPO"
gh secret list --repo "$REPO" --env sandbox
```
