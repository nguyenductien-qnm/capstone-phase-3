# MANDATE-18 evidence index

`PASS` requires runtime evidence. A code control, proposed command or expected
filename is never proof that a runtime change exists.

## Directive traceability

| Mandate requirement | Status | Raw evidence | Mandatory screenshots | Capture status |
|---|---|---|---|---|
| M18.1 No orphan resources | BLOCKED | `logs/03-orphans-before.json`, `logs/03-orphan-dependency-audit.txt`; after file `logs/04-orphans-after.json` missing | `03a`–`03f` inventory and `04-orphans-after.png` | 0 captured; owner unresolved |
| M18.2 Storage type/right-size/lifecycle | PARTIAL | `logs/05-storage-baseline.json`, `logs/05-storage-prompt4-audit.txt`, `logs/06-lifecycle-baseline.json` | `05a`, `05b`, `06a`–`06c` | 0 captured; no right-size rollout |
| M18.3 Reduce cross-AZ/NAT transfer | PARTIAL | `logs/07-network-before.json`, `logs/07-data-transfer-prompt5.txt`, `logs/08-vpc-endpoints.json`; after usage missing | `07a`, `07b`, `08a`, `08b`, `08c` | 0 captured; plan/rollout blocked |
| M18.4 Telemetry sampling/retention/cardinality with operability | PARTIAL | `logs/09-telemetry-before.txt`, `logs/09-telemetry-prompt6-before.txt`, `logs/11-slo-final-verification.txt`, `logs/12-investigation-drill.txt`; `logs/10-telemetry-after.txt` missing | `09a`–`09f`, `10a`–`10d`, `11a`–`11d`, `12a`–`12c` | 0 captured; no rollout; p95 FAIL |
| M18.5 Top non-compute driver identified and reduced | BLOCKED | `logs/02-noncompute-usage-before.json`; `logs/13-noncompute-usage-after.json` missing | `02-top-driver-before.png`, `13-top-driver-after.png` | 0 captured; attribution/after absent |

Strict directive PASS: `0/5`. Weighted progress (`PARTIAL=0.5`): `30%`.

## Detailed acceptance matrix

| ID | Acceptance | Status | Raw evidence | Screenshot(s) | Screenshot state |
|---|---|---|---|---|---|
| 01 | Correct account/region/cluster/namespace | PASS | `logs/01-scope-identity.txt` | `01-scope-identity.png` | NOT CAPTURED |
| 02 | Rank top driver by comparable Usage Quantity | PARTIAL | `logs/02-noncompute-usage-before.json` | `02-top-driver-before.png` | NOT CAPTURED |
| 03 | Orphan inventory and dependency audit | PARTIAL | `logs/03-orphans-before.json`, `logs/03-orphan-dependency-audit.txt` | `03a-ebs-before.png` … `03f-target-groups-before.png` | NOT CAPTURED |
| 04 | Approved cleanup leaves no confirmed orphan | BLOCKED | Expected `logs/04-orphans-after.json` is absent | `04-orphans-after.png` | NOT CAPTURED; no approved cleanup |
| 05 | Scoped EBS gp3 and evidence-based right-size | PARTIAL | `logs/05-storage-baseline.json`, `logs/05-storage-prompt4-audit.txt` | `05a-ebs-gp3.png`, `05b-pvc-usage.png` | NOT CAPTURED; right-size not rolled out |
| 06 | Snapshot/S3/log lifecycle finite | PARTIAL | `logs/06-lifecycle-baseline.json`, `logs/05-storage-prompt4-audit.txt` | `06a-cloudtrail-lifecycle.png`, `06b-terraform-state-lifecycle-gap.png`, `06c-dlm-baseline.png` | NOT CAPTURED |
| 07 | NAT/cross-AZ baseline with unit discipline | PASS | `logs/07-network-before.json`, `logs/07-data-transfer-prompt5.txt` | `07a-nat-cloudwatch-before.png`, `07b-network-usage-before.png` | NOT CAPTURED |
| 08 | Quantified endpoint decision and safe implementation | PARTIAL | `logs/08-vpc-endpoints.json`, `logs/07-data-transfer-prompt5.txt`, ADR | `08a-vpc-endpoints-before.png`, `08b-s3-endpoint-after.png`, `08c-private-route-after.png` | BEFORE/AFTER NOT CAPTURED; runtime endpoint absent |
| 09 | Telemetry rate/storage/cardinality baseline | PASS | `logs/09-telemetry-before.txt`, `logs/09-telemetry-prompt6-before.txt` | `09a`–`09f` listed in screenshot guide | NOT CAPTURED |
| 10 | Telemetry lower/bounded after change and still operable | BLOCKED | Expected `logs/10-telemetry-after.txt` is absent | `10a`–`10d` | NOT CAPTURED; no rollout |
| 11 | SLO holds under comparable workload | PARTIAL | `logs/11-slo-baseline.txt`, `logs/11-slo-final-verification.txt` | `11a-slo-final-verification.png`, `11b-storefront-p95-failure.png`, `11c-runtime-health.png`, `11d-warning-events.png` | NOT CAPTURED; p95 15s FAIL |
| 12 | Metric/dashboard → trace → log investigation | PARTIAL | `logs/12-investigation-drill.txt` | `12a-jaeger-trace.png`, `12b-opensearch-trace-logs.png`, `12c-prometheus-exemplar-blocked.png` | NOT CAPTURED; exemplar absent |
| 13 | Same-Usage-Type top-driver reduction | BLOCKED | Expected `logs/13-noncompute-usage-after.json` is absent | `13-top-driver-after.png` | NOT CAPTURED; after absent |
| 14 | Complete plan, PR, CI, reviewer and rollback | BLOCKED | `logs/14-pr-readiness-audit.txt`; expected `logs/14-pr-ci.txt` absent | `14a-terraform-plan.png`, `14b-pr-ci-review.png` | NOT CAPTURED; plan 403/PR absent |

## Non-negotiable interpretation notes

- Cost Explorer baseline is account-wide because the TF allocation tag is not
  available. It cannot be presented as `techx-tf1` usage.
- The three empty target groups are UNKNOWN/HOLD, not deletion candidates.
- EBS cannot be shrunk in place; a proposed target size is not runtime savings.
- S3 endpoint and telemetry controls are code-only until rollout evidence.
- Storefront p95 `15,000 ms` is a real FAIL with non-empty histogram buckets.
- The trace/log drill correlates, but direct Prometheus exemplar data is absent.
- Screenshot paths are requirements; no PNG exists in the pack at this audit.
