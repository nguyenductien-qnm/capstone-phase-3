# Auditability assessment and action plan — CDO-46, CDO-105, CDO-106

## Scope and assignment note

- **CDO-46:** EKS control-plane audit logging and change-management evidence.
- **CDO-106:** query, inspect and demonstrate Kubernetes audit events.
- **CDO-105:** CloudTrail integrity/tamper protection and end-to-end change trail.

`mandates/MANDATE-04-auditability-tf4.md` says the directive applies only to TF4, while this repository and `docs/cdo09` identify TF1/CDO09. Current Jira assigns these three tickets to Tấn Huy Nguyễn. The mandate source is preserved unchanged; implementation follows the current Jira assignment and records this governance inconsistency for mentor/product-owner confirmation.

## Architecture

```text
Human SSO / GitHub OIDC / ArgoCD identity
  → EKS API → EKS api/audit/authenticator → /aws/eks/<cluster>/cluster (KMS, retention)
  → AWS API → multi-region CloudTrail → encrypted/versioned S3 + validation digests
                                      ↘ CloudWatch Logs query group
Git/Jira → PR/review/plan → GitHub run session → Terraform or ArgoCD revision → resource event
```

EKS managed control plane only exposes selectable control-plane log types. It does **not** allow Terraform/users to install a custom kube-apiserver audit-policy file as self-managed Kubernetes would.

## Current-state matrix

| Requirement | Existing implementation | Gap found | Action | Evidence |
|---|---|---|---|---|
| K8s actions recorded | EKS module defaulted to api/audit/authenticator and existing log group | Root relied on implicit default; 7-day example; no KMS/protection/retention validation | Explicit sandbox input; 30d; rotating optional KMS; prevent_destroy; outputs | plan, `describe-cluster`, log group/stream |
| AWS API activity | Multi-region/global CloudTrail with validation and prevent_destroy | Bucket lacked explicit hardening and query stream | versioning, public block, SSE-KMS/AES fallback, lifecycle, management selector, CloudWatch | trail/status/selectors and S3 APIs |
| Who/what/when/resource | SSO access entries and GitHub OIDC roles | CI session attribution absent | bounded `gha-<actor>-<run_id>` session name in every AWS credential step | CloudTrail userIdentity + GitHub run |
| Git/PR/Jira correlation | PR plan artifact and ArgoCD Git revision | record fields/runbook absent | expanded PR template, change record and runbook | PR approval, SHA, revision, Jira |
| Tamper resistance | S3/trail prevent_destroy and log validation | operator deny absent; Object Lock unsafe on existing bucket | managed explicit-deny policy/output/manual SSO attachment; Object Lock opt-in GOVERNANCE | policy simulator/AccessDenied |
| On-site forensic | Logs existed | no repeatable query/drill | Bash queries, PowerShell verification, four-scenario drill | saved command/output/audit IDs |

## Risk, blast radius, cost

No application workload, Helm release, replicas, probes, PDB, HPA, database schema or flagd configuration changes. Terraform affects only EKS/CloudTrail audit resources and related IAM/KMS/CloudWatch/S3 settings. `prevent_destroy` deliberately makes teardown require a separately reviewed lifecycle decision. Enabling KMS on an existing log group/trail changes encryption for new records; validate key policy before apply. CloudTrail remains management-events only, avoiding broad S3/Lambda data-event cost.

Cost categories increase through CloudWatch ingestion/storage and queries, KMS key/API requests, retained/versioned S3 objects and lifecycle transitions/retrieval. Exact spend depends on API volume, region, retention and query frequency; use AWS Pricing Calculator/Cost Explorer rather than an invented amount. Scheduler/controllerManager remain off unless a forensic need justifies their ingestion cost.

## Rollback and break-glass

Rollback through a revert PR and reviewed Terraform plan. Disabling optional CloudWatch/KMS must account for retained encrypted data and must never schedule key deletion before retention/legal review. `prevent_destroy` is not removed casually. Object Lock stays false for the existing sandbox bucket; migration is: create a new Object-Lock-enabled bucket, test GOVERNANCE, update trail in a maintenance window, retain old bucket/history, then document custody.

Break-glass uses an individual, MFA-protected, short session with dual approval/incident-Jira, never shared credentials. Record caller ARN, UTC/ICT, command, reason, resource and result. Notify audit owner, export evidence, reconcile through Git and revoke session. Audit admins/break-glass ARN patterns are inputs; routine operators receive the explicit-deny policy through Identity Center.

## Evidence checklist

### CDO-46

- [ ] Terraform plan showing EKS log configuration; `describe-cluster` logging JSON.
- [ ] EKS log group, retention/KMS and `kube-apiserver-audit-*` stream.
- [ ] IAM Identity Center → EKS Access Entry design; change-management flow/PR.

### CDO-106

- [ ] Logs Insights query and result with username, verb, resource, timestamp and audit ID.
- [ ] Demo create/patch/delete events; verification script PASS.

### CDO-105

- [ ] CloudTrail status/selectors; S3 versioning/encryption/public block; validation enabled/result.
- [ ] CloudTrail session `gha-<actor>-<run_id>` and matching run/commit/PR.
- [ ] PR/change record, ArgoCD revision correlation.
- [ ] Operator IAM simulation or safe `AccessDenied` evidence for prohibited action.

Capture actual console/CLI evidence at the listed points; this repository contains no fabricated screenshots.

## Changed files and manual administration

Implementation changes are limited to:

- EKS: `terraform/modules/eks/{main.tf,variables.tf,outputs.tf}`.
- CloudTrail: `terraform/modules/cloudtrail/{main.tf,variables.tf,outputs.tf}`.
- Sandbox: `terraform/environments/sandbox/{main.tf,variables.tf,outputs.tf,terraform.tfvars.example,.terraform.lock.hcl}`.
- GitHub: `.github/workflows/{infra-cd.yaml,infra-destroy.yaml,app-build.yaml}` and `.github/pull_request_template.md`.
- Scripts: `scripts/validate/{verify-auditability.sh,verify-auditability.ps1,forensic-k8s-audit.sh,forensic-cloudtrail.sh,forensic-change-trail.sh}`.
- Documents: this report, `change-management-runbook.md`, `change-log-template.md`, and `mandate-04-forensic-drill.md`.

AWS/GitHub administrators must: review Terraform plan and KMS policies; apply themselves through protected environment; attach `audit_tamper_protection_policy_arn` to the routine Operator IAM Identity Center Permission Set (do not attach directly to ephemeral `AWSReservedSSO` roles); keep audit-admin/break-glass separate; use IAM policy simulator before denial drill; protect branches/environments and require approval; preserve GitHub run/log retention. Confirm the TF4-versus-TF1 assignment discrepancy with governance owners.

## Useful commands

```bash
terraform -chdir=terraform/environments/sandbox output eks_control_plane_log_group_name
aws eks describe-cluster --region <region> --name <cluster> --query cluster.logging
aws cloudtrail get-trail-status --region <region> --name <trail>
aws cloudtrail get-event-selectors --region <region> --trail-name <trail>
scripts/validate/verify-auditability.sh --region <region> --cluster-name <cluster> --trail-name <trail>
```
