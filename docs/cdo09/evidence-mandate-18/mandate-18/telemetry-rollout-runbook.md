# Telemetry rollout, verification, and rollback

No command in this document was run during Prompt 6.

## Mandatory preflight

1. Confirm account (redacted in evidence), `us-east-1`, cluster
   `ecommerce-dev-eks`, namespace `techx-tf1`, and Argo app `techx-corp`.
2. Confirm the rendered diff changes only the sandbox OTel exporter lists and
   one OpenSearch ISM ConfigMap/PostSync Job.
3. Obtain owner approval for 3-day operational-log retention.
4. Create and verify an OpenSearch data backup/EBS snapshot if old operational
   logs must be recoverable. Expired index deletion is irreversible otherwise.
5. Record a fixed workload and UTC window; use the same duration, request mix,
   and rate before and after.

## Increment 1: debug exporter removal

Roll out the OTel values change first and watch all seven DaemonSet pods become
Ready. Verify the runtime pipelines still contain:

- traces: `otlp/jaeger`, `spanmetrics`;
- metrics: `otlphttp/prometheus`;
- logs: `opensearch`.

Verify no pipeline references `debug`, accepted/rejected counters are healthy,
Jaeger search works, OpenSearch receives a fresh document, and every SLO query
returns the same semantic series as before.

Rollback: revert only the sandbox exporter override and let Argo sync. This
restores console copies and does not require backend data recovery.

## Increment 2: ISM retention

Only after Increment 1 is stable, set `telemetryRetention.enabled=true` in a
separate reviewed change and allow the PostSync job to create
`otel-logs-retention` and attach it to currently unmanaged `otel-logs-*`
indices. Verify the policy is 3d, all managed indexes match the intended
pattern, Job logs contain no HTTP failure, and filesystem usage trends down.

Configuration rollback: disable `telemetryRetention` and remove the policy
from indices before deleting the policy object. Data rollback is possible only
from the pre-rollout backup; reverting Git cannot restore deleted indices.

## Equal-window after comparison

Run the same workload and save real raw output to
`logs/10-telemetry-after.txt`. Compare accepted spans/logs, deliveries by
exporter, OpenSearch bytes/doc growth, active series/cardinality, refused or
dropped telemetry, checkout/browse/cart success, p95, error budget, Jaeger
lookup, and trace-to-log correlation.

Acceptance requires comparable load, no new refused/dropped telemetry, SLO and
alerts intact, and lower duplicate output or bounded storage. If workload or
window differs, mark comparison `BLOCKED`, not `PASS`.

## Screenshot checklist

- `09a-otel-daemonset-before.png`: 7/7 OTel agents Ready.
- `09b-otel-pipelines-before.png`: read-only pipeline exporters.
- `09c-prom-cardinality-before.png`: active series/cardinality.
- `09d-opensearch-indices-before.png`: daily docs/store size.
- `09e-opensearch-ism-before.png`: zero policies/managed indices.
- `09f-slo-before.png`: SLO dashboard with UTC window.
- `10a-otel-daemonset-after.png`: rollout complete.
- `10b-opensearch-ism-after.png`: policy/index pattern.
- `10c-telemetry-comparison-after.png`: equal-window rates/bytes.
- `10d-slo-after.png`: same workload/window SLO result.

Redact account ID, user ARN, tokens, cookies, credentials, and customer payload.
