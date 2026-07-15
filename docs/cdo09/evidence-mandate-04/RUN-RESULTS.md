# MANDATE-04 runtime evidence results

**Captured:** 2026-07-15 UTC/ICT  
**AWS profile:** `phase3-cdo`  
**Region:** `us-east-1`  
**Cluster:** `ecommerce-dev-eks`  
**Trail:** `ecommerce-dev-audit-trail`

## Passed

- 01: Terraform format/init/validate passed against the real S3 backend.
- 03: EKS enables `api`, `audit`, and `authenticator`.
- 05: Isolated ConfigMap drill produced attributable create/patch/delete audit events; namespace cleanup completed.
- 06: CloudTrail is logging, multi-region, includes global services, validates log files, and records all management read/write events.
- 09: `3/3` digest files and `126/126` log files validated successfully.
- 11: ArgoCD root revision `77ed0358f53346ab36426fc1797d1b5d521bbda0` correlates to a GitHub commit, PR #87, and Jira CDO-49.

## Partial

- 04: Kubernetes audit streams exist, but runtime retention is still 7 days and the EKS log group has no KMS key.
- 07: IAM Identity Center attribution to the individual session `huynt` is proven. GitHub `gha-<actor>-<run_id>` attribution is not deployed on the remote branch yet.

## Failed or blocked

- 02: Local plan is blocked because the non-committed `terraform.tfvars`/GitHub `TFVARS_SANDBOX` secret is unavailable. The diagnostic lists required variables without exposing values.
- 08: S3 Public Access Block and AES256 encryption pass, but Versioning is not configured. Object Lock remains intentionally disabled pending migration.
- 10: No PR implementing CDO-46/CDO-105/CDO-106 exists on the public repository, so reviewer/Jira evidence cannot be claimed.
- 12: No audit tamper managed policy exists in AWS. The current SSO role has `AdministratorAccess`; IAM simulation returns `allowed` for CloudTrail stop/delete/update and S3 delete/bypass actions.

## Required path to full pass

1. Supply the real sandbox tfvars only through the protected local file or GitHub `TFVARS_SANDBOX` secret.
2. Commit and open a PR for the auditability Terraform/workflow/docs/scripts changes with Jira CDO-46/CDO-105/CDO-106.
3. Review the Terraform plan and merge the PR.
4. An authorized human runs the protected apply; do not apply an unreviewed local reconstruction of tfvars.
5. Attach the generated tamper-deny managed policy to a dedicated routine Operator IAM Identity Center Permission Set, not directly to the ephemeral `AWSReservedSSO_*` role and not to the break-glass/audit-admin Permission Set.
6. Re-run runtime verification and IAM simulation; evidence 12 must show `explicitDeny`.
7. Run a post-merge GitHub workflow and correlate its `gha-<actor>-<run_id>` session in CloudTrail.
