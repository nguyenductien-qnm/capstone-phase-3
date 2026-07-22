# MANDATE-18 evidence runbook

## Environment

PowerShell:

```powershell
$env:AWS_PROFILE = "phase3-cdo"
$env:AWS_REGION = "us-east-1"
$env:AWS_DEFAULT_REGION = "us-east-1"
```

## Read-only preflight

```powershell
aws sts get-caller-identity --profile phase3-cdo --region us-east-1
aws eks describe-cluster --name ecommerce-dev-eks --profile phase3-cdo --region us-east-1
kubectl get namespaces
kubectl auth can-i get pods --all-namespaces
```

## Evidence capture rules

- Redirect only real command output into `../logs/`.
- Capture stderr and exit code for failed commands.
- Redact account ID, email and sensitive ARN segments before commit.
- Do not store tokens, kubeconfig, tfvars, credentials or signed URLs.
- Record UTC timestamp and exact query/filter with every before/after result.

## Before/after discipline

For Cost Explorer, repeat exactly:

- metric `UsageQuantity`;
- same service and Usage Type string;
- same account/tag scope;
- same finalized-duration window;
- same unit.

Do not add `GB`, `GB-Month`, `Hrs`, requests or events. For NAT CloudWatch,
do not add mirrored in/out counter pairs. For telemetry/SLO, keep the same UTC
window, PromQL, load-generator request mix and declared volume tolerance.

Delta formula for comparable values:

```text
absolute_delta = after - before
percent_delta = (after - before) / before * 100
```

If after, scope or unit differs, record `BLOCKED`, not zero or an estimated
saving.

## Validation commands before PR

```powershell
terraform -chdir=terraform/environments/sandbox fmt -check -recursive
terraform -chdir=terraform/environments/sandbox validate -no-color
terraform -chdir=terraform/modules/vpc-endpoints test -no-color
terraform -chdir=terraform/environments/sandbox plan -input=false -lock=false -no-color
helm lint platform/charts/application `
  -f platform/gitops/environments/sandbox/values-flagd-sync.yaml `
  -f platform/gitops/environments/sandbox/values-ops-observability.yaml `
  -f platform/gitops/environments/sandbox/values-external-secrets.yaml `
  -f platform/gitops/environments/sandbox/values-aio-llm.yaml `
  -f platform/gitops/environments/sandbox/values-image-tags.yaml
git diff --check
```

The full plan must run in the approved protected environment with backend read
access and real protected variables. Never use invented tfvars. Record exact
add/change/destroy/replace counts and stop on unexpected delete/replace.

## Specialized rollout runbooks

- Network: `data-transfer-rollout-runbook.md`.
- Telemetry: `telemetry-rollout-runbook.md`.
- Storage decisions: `storage-rightsize-plan.md` and
  `storage-console-checklist.md`.
- Orphan safety: `cleanup-manifest.md`.

## Runtime acceptance sequence

1. Confirm Argo app destination is `techx-tf1`, Synced and Healthy.
2. Confirm all Deployment/StatefulSet/DaemonSet desired replicas are Ready.
3. Confirm no image pull, AWS API credential or rollout errors.
4. Run the same workload/window and verify checkout >=99%, browse/cart >=99.5%
   and storefront p95 <1s.
5. Investigate one trace ID through dashboard/service/time, Jaeger and
   OpenSearch. A missing exemplar must be shown as PARTIAL/BLOCKED.
6. Capture after usage only after the metric window is complete/finalized.
7. Update index status only from raw evidence, then capture screenshots using
   the exact captions in `../screenshots/README.md`.

## Destructive gate

This runbook intentionally contains no delete/apply command. Cleanup requires an approved manifest of exact resource IDs.

## Current blockers

- Remote Terraform backend `HeadObject` returns 403 for the current SSO role.
- Three target groups lack owner confirmation.
- ISM retention lacks owner approval and recoverable backup.
- Storefront p95 is 15 seconds.
- No after Usage Quantity files, screenshots, PR, CI or reviewer evidence exist.
