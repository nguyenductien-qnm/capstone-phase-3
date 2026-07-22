# ADR — Mandate 18 cost beyond compute

- Status: Proposed; code validated, no optimization rolled out.
- Date: 2026-07-22.
- Owner: CDO-09.
- Scope: `us-east-1`, `ecommerce-dev-eks`, `techx-tf1`.

## Context

Mandate 18 requires lower non-compute usage without losing SLO or the ability
to investigate. Cost columns are near zero because of credits, so decisions
use Usage Quantity and never add unlike units.

Measured top account-wide GB rows are regional transfer `357.6795 GB`, NAT
processing `61.9773 GB`, and CloudWatch vended logs `18.5108 GB`. TF-specific
Cost Explorer attribution is unavailable, so this ranking remains PARTIAL.

## Decisions

1. **Orphans:** do not delete the three empty target groups. They remain
   UNKNOWN/HOLD until owner confirmation; `testt` is in another VPC.
2. **Storage:** keep all current EBS volumes; 9/9 are gp3. Do not shrink EBS
   in-place. Prometheus and large root disks are only conditional migration
   candidates after full-window measurement and protected plan.
3. **Snapshot/S3:** keep the verified CloudTrail lifecycle. Do not create DLM
   snapshots without backup scope. Do not adopt the shared Terraform state
   bucket without backend-owner agreement.
4. **Network:** implement only the S3 Gateway Endpoint module for the private
   app/MQ egress route table. Keep NAT. Do not add ECR interface endpoints at
   the measured scale; their fixed HA footprint exceeds the processing-only
   break-even estimate.
5. **Telemetry:** remove only duplicate debug exporter output. Keep Jaeger,
   OpenSearch, Prometheus and spanmetrics. Prepare a 3-day `otel-logs-*` ISM
   policy, but keep it disabled until owner approval and backup.
6. **Sampling:** do not add probabilistic sampling because it cannot guarantee
   all errors. Do not tail-sample on the current seven-agent DaemonSet without
   trace-ID-aware gateway routing.

Detailed rationale is in `ADR-data-transfer-endpoints.md` and
`ADR-telemetry-volume-controls.md`.

## Rejected options

- Delete empty target groups based only on target count.
- Shrink EBS volumes in place.
- Remove NAT while Internet registry/general egress dependencies remain.
- Add ECR/API interface endpoints without attributable traffic above the
  quantitative break-even.
- Drop audit/security logs or use sampling that can discard error traces.
- Enable auto-delete retention in the auto-sync path without backup.

## SLO impact and current evidence

Success SLI values are 100%, but storefront p95 is `15,000 ms` and therefore
fails the `<1s` target. Trace/log correlation works for one 51-span request;
Prometheus exemplars are absent. No rollout can be called safe until these
results are remediated or accepted by the mentor.

## Rollback

- S3 endpoint: remove the module only after a plan shows only the expected
  endpoint deletion; NAT default route stays available.
- Debug exporter: revert sandbox exporter lists and allow Argo to resync.
- ISM: detach/disable policy before deleting it. Git rollback cannot restore
  deleted indices; restore requires the pre-rollout backup.
- Storage migration: retain old PVC/node group until data and workload checks
  pass; rollback by switching workload back, not by shrinking a volume.

## Approval gates

Protected Terraform plan, owner/destructive approvals, backup verification,
same-workload SLO and same-Usage-Type after evidence are mandatory. Current
status remains Proposed.
