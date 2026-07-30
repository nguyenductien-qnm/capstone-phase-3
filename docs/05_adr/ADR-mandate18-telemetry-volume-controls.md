# ADR: minimal telemetry volume controls

Status: proposed and rendered; not rolled out.

## Decision

1. In the `techx-develop` runtime values only, remove the OTel `debug` exporter
   from traces, metrics, and logs. Keep Jaeger, Prometheus, OpenSearch, and the
   `spanmetrics` connector unchanged.
2. Add a safety-gated OpenSearch ISM policy for only `otel-logs-*`: hot
   immediately and delete after `3d`. It remains disabled in auto-sync values
   until owner approval and backup exist. The pattern does not match
   CloudTrail, EKS control-plane, MSK, RDS, or audit Lambda log groups.
3. Do not add probabilistic or tail sampling in this change.
4. Do not add a message-content filter yet. Dropping text without owner review
   could hide an operational signal; removing the verified duplicate debug
   sink is the safe first increment.

## Evidence and sizing

OpenSearch uses 8.004 GB of a 10.464 GB filesystem (77%). Daily OTel log
indices varied from 0.276 GB to 3.154 GB for complete observed days. A 3-day
window bounds growth while leaving more headroom than the current unbounded
policy. This is an operational retention decision, not a claim that old data
is backed up.

Prometheus already has finite `7d` retention. Two AWS-created log groups have
unset retention, but they are not imported into the Terraform state reviewed
here; adopting them without import/ownership confirmation is outside this
minimal Helm change.

## Sampling decision

Runtime is seven OTel agent collectors in a DaemonSet. The OTLP Service selects
all agents and uses `internalTrafficPolicy: Local`; there is no dedicated trace
gateway and no trace-ID-aware load-balancing tier.

- Probabilistic sampling is rejected because it cannot guarantee retaining
  100% of error/critical traces.
- Tail sampling on each agent is rejected because one agent may not see every
  span of a trace.
- A future design may use agent-to-gateway routing by trace ID and a gateway
  tail-sampling policy that always retains `ERROR`, then samples successful
  traces. That topology change is not the smallest safe change.

## SLO and audit safety

The SLO dashboard and alerts query `traces_span_metrics_*`. The trace pipeline
still exports to `spanmetrics`, so their metric contract is unchanged. Jaeger
also remains enabled for trace investigation. No receiver, transform, batch,
resource detection, or application backend exporter is removed.

AWS audit/security retention remains independent: CloudTrail 90d CloudWatch
plus its S3 lifecycle, EKS control-plane 7d, audit Slack Lambda 30d, and MSK 3d.
The ISM pattern is deliberately restricted to operational `otel-logs-*`.

## Consequences

- Collector stdout volume and duplicate exporter work should fall.
- Aggregate `otelcol_exporter_sent_*` rates will fall because they count fewer
  exporter deliveries; this is expected and is not telemetry loss.
- OpenSearch will delete indices older than 3d after rollout and ISM execution.
  Deleted data cannot be restored without a pre-rollout backup.
- Runtime effectiveness and SLO safety remain unverified until a controlled
  rollout and equal-window workload comparison are completed.
