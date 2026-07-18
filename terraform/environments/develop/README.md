# Develop environment

This root reuses the same Terraform modules as the Product-like root but creates resources only in the dedicated Develop AWS account `458580846647`.

## Isolation guarantees

- The AWS provider has `allowed_account_ids = ["458580846647"]`.
- `aws_account_id`, `project_name` and `environment` are validated as `458580846647`, `ecommerce-develop` and `dev`.
- The S3 backend is partial. Bucket, key and region must come from the GitHub Environment `develop`; no Sandbox backend value is present in this root.
- The workflow performs a second STS account check and explicitly rejects Product-like account `804372444787`.
- Apply is manual, only from branch `develop`, and requires the exact confirmation `apply-develop`.
- This root does not instantiate the ECR module. Workloads pull from the existing shared ECR in account `804372444787`.
- The Product-like scheduled Auto Scaling configuration is not copied into Develop.
- CloudFront, Route53 and public ALB ingress are disabled for the initial rollout.

Resource names use prefix `ecommerce-develop-dev`, so globally named resources such as the CloudTrail bucket do not collide with Product-like names.

## Bootstrap and GitHub Environment

First review and execute the one-time root at `terraform/bootstrap/develop` with an administrator SSO identity in account `458580846647`. Do not run the main Develop root locally.

In GitHub, create an Environment named exactly `develop`, restrict deployment branches to `develop`, and preferably require a reviewer. Configure:

| Name | Type | Required value |
|---|---|---|
| `AWS_ACCOUNT_ID` | variable | `458580846647` |
| `AWS_REGION` | variable | `us-east-1` |
| `TF_AWS_ROLE_ARN` | variable | bootstrap output `github_terraform_role_arn` |
| `TF_BACKEND_BUCKET` | variable | bootstrap output `terraform_state_bucket` |
| `TF_BACKEND_KEY` | variable | `develop/terraform.tfstate` |
| `TF_BACKEND_REGION` | variable | `us-east-1` |
| `EKS_CLUSTER_NAME` | variable | `ecommerce-develop-dev-eks` |
| `ARGOCD_REPO_TOKEN` | secret | fine-grained token with read-only Contents access to this private repository |

The workflow also expects the same Terraform input variables used by Product-like, but stored separately in the `develop` GitHub Environment:

- network: `TF_VAR_VPC_CIDR`, `TF_VAR_PUBLIC_SUBNETS`, `TF_VAR_PRIVATE_APP_SUBNETS`, `TF_VAR_PRIVATE_DATA_SUBNETS`, `TF_VAR_PRIVATE_MQ_SUBNETS`, `TF_VAR_ENABLE_NAT_GATEWAY`, `TF_VAR_SINGLE_NAT_GATEWAY`;
- EKS: `TF_VAR_EKS_CLUSTER_VERSION`, `TF_VAR_EKS_NODE_CAPACITY_TYPE`, `TF_VAR_EKS_ENDPOINT_PUBLIC_ACCESS`, `TF_VAR_EKS_PUBLIC_ACCESS_CIDRS`, `TF_VAR_EKS_CONTROL_PLANE_LOG_RETENTION_DAYS`, `TF_VAR_EKS_ACCESS_ENTRIES`;
- RDS: `TF_VAR_DB_NAME`, `TF_VAR_DB_USERNAME`, `TF_VAR_RDS_INSTANCE_CLASS`, `TF_VAR_RDS_ALLOCATED_STORAGE`, `TF_VAR_ENABLE_READ_REPLICA`, `TF_VAR_REPLICA_INSTANCE_CLASS`, `TF_VAR_ENABLE_RDS_PROXY`, `TF_VAR_RDS_MULTI_AZ`;
- Valkey/MSK: `TF_VAR_VALKEY_NODE_TYPE`, `TF_VAR_VALKEY_NUM_CACHE_CLUSTERS`, `TF_VAR_KAFKA_VERSION`.

Subnet variables and access entries are Terraform JSON values. Do not copy the Product-like CIDRs blindly: verify the selected Develop CIDR does not overlap Product-like, VPN, peered VPCs or internal networks. The private application subnet map must contain key `app-2`, which is the default location of the dedicated observability node.

`develop-capacity.tfvars` deliberately fixes the primary node group at desired/min `1`, max `3`, and keeps one dedicated observability node required by the current EKS module.

## Safe execution order

1. Run the one-time bootstrap plan and review that it targets only account `458580846647`.
2. Create the GitHub Environment and variables above.
3. Open a pull request; it runs only offline format and validation checks and does not assume an AWS role.
4. Merge into `develop`, then manually dispatch `Develop Infra` with `apply=false` to produce a Develop-only plan. Review that it contains creates only, no destroy/replace, and no account `804372444787` ARN.
5. Dispatch again with `apply=true` and confirmation `apply-develop`; that run creates a fresh plan and applies exactly its saved artifact.
6. Copy the two node-role outputs into the Sandbox Environment variable `TF_VAR_ECR_PULL_PRINCIPAL_ARNS`, review the Product-like plan, and apply only the ECR repository policy change.
7. Add `ARGOCD_REPO_TOKEN`, then manually dispatch with `bootstrap_argocd=true`. The Develop root application is only registered; all ArgoCD auto-sync/prune/self-heal remains disabled for first review.

No command in this directory should use `terraform destroy`, force replacement, state manipulation or force-unlock without a separate risk review.
