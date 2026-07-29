# MANDATE-18 mentor demo script

Target duration: 8–10 minutes. Do not record until mandatory screenshots and
runtime after evidence exist. Account/caller/customer data must be redacted.

## 00:00–00:40 — Scope and honesty statement

Show `README.md` and scope screenshot. Say region, cluster, namespace and Git
revision. State explicitly whether the demo is baseline-only or after rollout.
Do not say “completed” while index contains BLOCKED requirements.

## 00:40–01:40 — Top cost driver

Show Cost Explorer Usage Quantity screenshot and read:

- `DataTransfer-Regional-Bytes = 357.6794858022 GB`;
- `NatGateway-Bytes = 61.9773010455 GB`;
- `NatGateway-Hours = 158 Hrs`.

Explain these are account-wide because the TF allocation tag is unavailable.
Do not compare GB to hours/GB-month or claim reduction without the same-filter
after screenshot.

## 01:40–02:30 — Orphans

Show inventory and the three target groups. Read classification UNKNOWN/HOLD,
owner gap and the fact that `testt` belongs to another VPC. If no approved
cleanup occurred, show the missing after row and say no resource was deleted.

## 02:30–03:30 — Storage

Show 9/9 EBS gp3, attachment and PVC usage:

- Prometheus about 25.9% used;
- OpenSearch about 76.8–77% used.

Show CloudTrail S3 lifecycle and the state-bucket/DLM gaps. Explain why EBS was
not shrunk in place and why no right-size saving is claimed yet.

## 03:30–04:40 — Data transfer

Show NAT 24h metrics and current route table. Then show the Terraform plan/PR
or, if still blocked, the ADR and explicit `S3 endpoint runtime=PENDING` row.
Explain why NAT remains and why ECR interface endpoints were rejected at the
measured scale.

## 04:40–05:50 — Telemetry

Show accepted spans/log rate, 230,879 active series, top cardinality labels,
OpenSearch daily growth and zero ISM policies. If rollout happened, show the
same-window after values and ISM status. If not, show that the 3-day policy is
safety-gated and do not claim lower telemetry.

## 05:50–07:10 — SLO and investigation

Show the exact 5m SLO window:

- checkout/browse/cart = 100%;
- request volume baseline 4.6500/s vs verification 5.5083/s (+18.4588%);
- storefront p95 = 15,000 ms (FAIL until remediated).

Open Jaeger trace `8116e5b4dfe5706856449f1a31e6f299`, show the 51-span
waterfall and checkout PlaceOrder span. Filter OpenSearch by the same trace ID
and show matching logs. Show the empty Prometheus exemplar result and call the
direct metric hop PARTIAL unless it has since been fixed.

## 07:10–08:20 — Plan, rollback and PR

Show the protected Terraform plan summary, CI and reviewer approval only if
they exist. Read add/change/destroy/replace counts. Demonstrate that rollback
keeps NAT and that ISM-deleted data requires a backup, not merely Git revert.

## 08:20–09:00 — Final result

Show `EVIDENCE-INDEX.md` and `mandate-18.md`. Read all remaining PARTIAL and
BLOCKED rows. Conclude with measured deltas only; never convert absent after
data to zero or estimated savings.

## Recording checklist

- Browser address bar/account menu/customer identifiers hidden.
- UTC window and units visible on every chart.
- No jump cuts that conceal a failed/empty result.
- Raw log filename is mentioned for every screenshot.
- Final video filename: `mandate-18-demo.mp4`; link it from the PR, do not store
  credentials or signed sharing URLs in the repository.
