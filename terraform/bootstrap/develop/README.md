# Develop bootstrap

This one-time root creates only the prerequisites required before GitHub Actions can manage the Develop infrastructure:

- a dedicated, versioned and encrypted S3 state bucket in account `458580846647`;
- `GitHubTerraformDevelopRole`;
- an OIDC trust policy restricted to repository `nguyenductien-qnm/capstone-phase-3` and GitHub Environment `develop`.

It reuses the GitHub OIDC provider that already exists in the account. It does not create application infrastructure and it does not reference the Product-like Terraform state.

## One-time execution

Run this only after verifying the active SSO identity is in account `458580846647`. The first run intentionally uses Terraform's local backend because the S3 bucket does not exist yet; local state files are ignored by Git. Initialize normally, review `terraform plan`, and protect the local state until migration is complete.

After the first reviewed apply, record these outputs:

- `terraform_state_bucket` -> GitHub Environment variable `TF_BACKEND_BUCKET`;
- `github_terraform_role_arn` -> GitHub Environment variable `TF_AWS_ROLE_ARN`.

After the reviewed bootstrap apply creates the bucket, copy `backend.s3.tf.example` to `backend.tf` and run `terraform init -migrate-state` with backend bucket, region, encryption, S3 lockfile, and key `bootstrap/develop/terraform.tfstate`. Commit the active `backend.tf` only in a follow-up change after migration succeeds. Do not reuse `develop/terraform.tfstate`, which belongs to the main Develop root. Never force-unlock an unrelated state lock.

`AdministratorAccess` is attached because the current root creates IAM, network, EKS, database, cache, MSK and audit resources. The blast radius is constrained by the dedicated AWS account and the exact GitHub Environment OIDC subject; replace it with a narrower managed policy after the required API set is measured.
