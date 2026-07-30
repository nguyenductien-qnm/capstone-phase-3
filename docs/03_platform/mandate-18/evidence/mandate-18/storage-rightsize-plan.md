# Mandate 18 — storage right-size and lifecycle plan

## Decision

Runtime already uses `gp3` for all nine scoped EBS volumes. No in-place shrink, snapshot creation, DLM policy or shared-state lifecycle change is authorized in Prompt 4.

No environment lock-file edit is retained. The Mandate 18 Terraform resource change is the reviewed S3 Gateway Endpoint wiring in the develop root; storage right-sizing remains plan-only until utilization and migration approval are complete.

## Right-size proposals

| Storage | Current | Current usage/headroom | Proposed target | Gate |
|---|---:|---:|---:|---|
| OpenSearch PVC | 10 GiB | 76.80% used / 23.04% headroom | Keep 10 GiB | Add ISM retention first; consider expansion if sustained usage exceeds 80% |
| Prometheus PVC | 20 GiB | 25.89% used / 74.03% headroom | New 12 GiB PVC | Full 7-day max used must be <=8.4 GiB, then offline TSDB copy and SLO validation |
| Main managed-node roots | 50 GiB | 9.30-9.93 GiB used | 30 GiB for newly rolled nodes | Complete plan must show only expected launch-template/node rollout; PodDisruptionBudget and capacity verified |
| Ops/Karpenter roots | 30 GiB | approximately 6.66-10.08 GiB used | Keep 30 GiB | No smaller size without a full-window measurement |

The percentage for a proposed target is not derived by shrinking the current device. A new volume/node is created at the target size and data/workload is migrated.

## Prometheus migration — not executed

1. Measure `max_over_time(kubelet_volume_stats_used_bytes{namespace="techx-tf1",persistentvolumeclaim="prometheus"}[7d])`.
2. Continue only if maximum used is at most `8.4 GiB`, leaving at least 30% headroom on 12 GiB.
3. Create a separate 12 GiB `gp3-observability` PVC; do not edit the bound 20 GiB claim expecting shrink.
4. Stop Prometheus cleanly and copy the TSDB offline to the new PVC, preserving ownership and permissions.
5. Point a reviewed workload revision to the new claim and verify readiness, ingestion, retention, queries and SLO dashboard.
6. Keep the original 20 GiB PVC/PV unchanged as rollback until the agreed observation window ends.
7. Delete the old volume only after explicit owner approval and after-evidence.

Rollback: revert the workload claim reference to the retained 20 GiB PVC, restart Prometheus and verify active series plus SLO panels.

## Managed-node root migration — not executed

1. Change the launch-template input from 50 GiB to 30 GiB only after a complete plan is available.
2. Require plan review showing no cluster/VPC/database replacement and only the expected launch-template/node-group rollout.
3. Verify spare capacity, PodDisruptionBudgets and one-node-at-a-time drain.
4. Roll one canary node, validate disk headroom, pods, ingress and SLO, then continue.

Rollback: restore the 50 GiB launch-template input and roll back to the previous launch-template version. Existing 50 GiB EBS volumes are never shrunk.

## Snapshot/DLM decision

There are no self-owned snapshots, so there is no current snapshot-retention leak. DLM remains a preventive GAP. A future DLM change must be opt-in by an explicit backup tag, specify retention/count and estimate snapshot GB-month before apply; it must not snapshot every cluster volume implicitly.

Rollback: disable the DLM policy first. Do not delete already-created snapshots until owner/retention approval.

## S3 decisions

- CloudTrail bucket: keep the verified 90-day Glacier Instant Retrieval transition and 2555-day audit retention.
- Terraform state bucket: do not transition the current state object. Ownership, tags and versioning policy must be established first. A later reviewed control may enable versioning and expire only sufficiently old noncurrent versions while retaining a defined rollback count.

Rollback for a future lifecycle change: suspend/remove the new rule before its expiration threshold; restore state from a verified noncurrent version only through the backend-owner runbook.

## Terraform plan blocker

The develop root requires protected variables not stored in the repository. Supplying invented values would create a misleading plan. Run the full plan through the protected Develop CI environment or provide the exact non-secret tfvars and secret inputs through the approved mechanism. No apply is allowed until the plan has zero unexpected destroy/replace actions.
