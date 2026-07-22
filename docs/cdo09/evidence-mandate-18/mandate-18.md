# MANDATE-18 — Cost beyond compute

## Executive result

Status: **IN PROGRESS / NOT READY FOR MENTOR SIGN-OFF**.

Baseline, design and code validation are substantial, but no top usage driver
has a comparable after value and no optimization has runtime rollout evidence.
Storefront p95 is `15s`, above the `<1s` target. The pack therefore makes no
claim that Mandate 18 has reduced AWS usage.

## Verified scope

| Field | Value |
|---|---|
| AWS profile | `phase3-cdo`; account/caller redacted |
| Region | `us-east-1` |
| Cluster | `ecommerce-dev-eks` |
| Environment | `dev` |
| Namespace | `techx-tf1` |
| Argo application | `techx-corp`, runtime observed Synced/Healthy |
| Git branch | `feat/mandate-18` |

## Directive requirement status

| Requirement | Status | Mentor conclusion |
|---|---|---|
| 1. No orphan resources | BLOCKED | Inventory exists; three target groups remain UNKNOWN/HOLD because owner is unconfirmed; no after inventory |
| 2. Correct storage and lifecycle | PARTIAL | 9/9 scoped EBS are gp3 and CloudTrail lifecycle is active; right-size not implemented; zero DLM; state bucket ownership/lifecycle unresolved |
| 3. Reduce hidden data transfer | PARTIAL | NAT/cross-AZ baseline and S3 gateway module exist; protected plan, rollout and after usage absent |
| 4. Telemetry bounded and operable | PARTIAL | Baseline/cardinality/topology measured; debug removal code rendered; ISM is safety-gated; no after delta; storefront p95 fails |
| 5. Top non-compute driver reduced | BLOCKED | Account-wide top GB row identified, but TF attribution and same-Usage-Type after value are absent |

Strict directive PASS: `0/5 = 0%`. Weighted progress with `PARTIAL=0.5`:
`1.5/5 = 30%`. This is Mandate compliance, not Prompt 8 documentation progress.

## Before/after delta

Only values with the same Usage Type/unit, scope, window and workload may be
subtracted. Missing after data is shown as `BLOCKED`, never treated as zero.

| Measure | Unit/window | Before | Verification/after | Delta | Status |
|---|---|---:|---:|---:|---|
| `DataTransfer-Regional-Bytes` | GB; CE 2026-07-15..22, account-wide | 357.6794858022 | absent | not computable | BLOCKED |
| `NatGateway-Bytes` | GB; same CE window | 61.9773010455 | absent | not computable | BLOCKED |
| `NatGateway-Hours` | Hrs; same CE window | 158 | absent | not computable | BLOCKED |
| `USE1-DataTransfer-xAZ-Out-Bytes` | GB; same CE window | 1.603371047 | absent | not computable | BLOCKED |
| `USE1-DataTransfer-xAZ-In-Bytes` | GB; same CE window | 1.2116824725 | absent | not computable | BLOCKED |
| OpenSearch operational logs | bytes/daily indices | 8,004,309,801 total | absent after rollout | not computable | BLOCKED |
| Accepted spans | spans/s; 5m | 16.5448867426 | absent after rollout | not computable | BLOCKED |
| Active Prometheus series | series; instant | 230,879 | absent after rollout | not computable | BLOCKED |
| SLO request volume | calls/s; same 5m query/load-generator | 4.6500059723 | 5.5083396702 | +0.8583336979 (+18.4588%) | PASS comparability at stated ±20% |
| Storefront p95 | ms; 5m | baseline idle/NaN | 15,000 | no valid numeric before delta | FAIL threshold |

Cost Explorer rows are account-wide because `Project=ecommerce` was not an
available allocation tag. NAT mirrored byte counters are not summed.

## Implemented but not rolled out

- Reusable Terraform S3 Gateway Endpoint module, scoped to private app/MQ
  egress route table; NAT retained.
- OTel debug exporter removal in the `techx-tf1` sandbox values.
- OpenSearch `otel-logs-*` 3-day ISM policy manifest, disabled behind an owner
  and backup safety gate.

These are code results, not runtime PASS evidence.

## SLO and investigation

- Checkout success: 100% — PASS.
- Browse/frontend success: 100% — PASS.
- Cart success: 100% — PASS.
- Storefront p95: 15,000 ms — FAIL.
- Runtime pods/deployments: healthy at capture.
- Trace `8116e5b4dfe5706856449f1a31e6f299`: 51 Jaeger spans and 18 OpenSearch
  logs correlate — PASS for trace/log.
- Prometheus exemplar lookup: empty — direct metric-to-trace hop PARTIAL.

## Terraform and delivery gates

- `fmt -check`: PASS.
- Root `validate`: PASS.
- S3 endpoint module test: PASS, 1/1.
- Full root plan: BLOCKED by remote-state `S3 HeadObject 403` for current SSO
  role. Destroy/replace count is unknown.
- Apply/Argo rollout: not run.
- PR, CI run and reviewer approval: absent.

## Evidence missing before opening PR

1. **Terraform:** remote-state read permission; protected variables; complete
   plan; explicit add/change/destroy/replace counts; zero-unexpected-change
   review at the exact PR commit.
2. **Orphans:** owner/project confirmation for all three UNKNOWN/HOLD target
   groups; exact approved full ARNs; before/after inventory if cleanup occurs.
3. **Storage sizing:** full 7-day/max-used evidence for Prometheus and root
   disks; protected migration plan; post-migration size/utilization if changed.
4. **Snapshot lifecycle:** owner-approved DLM policy evidence or a documented
   mentor-approved N/A while self-owned snapshot inventory remains zero.
5. **Shared state bucket:** backend-owner confirmation and its approved
   versioning/lifecycle policy; do not impose expiration without ownership.
6. **S3 endpoint runtime:** endpoint `available`, correct VPC/service/type,
   intended prefix-list route only, NAT default route retained.
7. **Network safety:** post-rollout ECR image pull, AWS API access, public
   storefront and private-ops reachability evidence.
8. **Network delta:** same-window NAT bytes/hours and cross-AZ Usage Types after
   rollout, with Cost Explorer finalization timestamp.
9. **Telemetry rollout:** OTel 7/7 Ready with runtime pipelines, refused/dropped
   counters, OpenSearch fresh-log proof and Jaeger trace search.
10. **Retention safety:** operational-log owner approval, recoverable backup,
    ISM policy/index attachment and post-policy storage trend.
11. **Telemetry delta:** same-workload/window accepted/exported rates,
    OpenSearch bytes/docs growth and Prometheus series/cardinality after.
12. **SLO:** storefront p95 below 1 second under comparable workload while all
    success SLI thresholds hold.
13. **Investigation:** working Prometheus exemplar link or explicit mentor
    acceptance of manual service/time → Jaeger → OpenSearch correlation.
14. **Cost ownership/delta:** TF-specific allocation tag/filter or accepted
    account-wide scope plus `logs/13-noncompute-usage-after.json` for the exact
    same Usage Type and finalized-duration window.
15. **Media/delivery:** all 39 screenshots in the authoritative manifest,
    redacted demo video, commit SHA, PR URL, CI checks and reviewer approval.

## Submission decision

Do not present this pack as completed Mandate 18 and do not claim savings.
Opening a draft PR is possible for review, but a completion PR is not justified
until the protected plan and destructive/owner gates are resolved.
