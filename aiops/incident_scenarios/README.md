# Labeled incident set (MANDATE-07 #7b)

Ground-truth-labeled scenarios for `aiops/incident_replay.py` (the replay/repro
tool `#7b` requires), proving the detector fires end to end and reporting
precision/recall/lead-time on a labeled set, per the mandate's exact formula.

| File | Type | Service / signal | Proves |
|---|---|---|---|
| `case_real_incident.json` | `real` | checkout — gRPC error rate | detector catches a genuine fault |
| `case_cart_failure.json` | `real` | cart — gRPC error rate | same detection works on a second service |
| `case_image_slow.json` | `real` | image-provider/frontend — p95 latency | a third, different signal class (latency, not errors) |
| `case_quiet_window.json` | `healthy_load` | all monitored rules | the "normal period" the precision figure needs |

The three `real` cases give **K=3** across three services and two signal
classes, which is what `#7b`'s "mở rộng thêm service" asks for. The quiet
window carries no injection at all: `precision = correct fires / total fires`
is only meaningful when the set also contains a stretch where nothing is
wrong, so a detector that alerts constantly is penalised.

> This folder and `incident_replay.py` are built generically so MANDATE-15
> (masking-resistance, healthy-load false-positive check) and MANDATE-22
> (remediation replay via `--check-remediation`) can add their own scenario
> files here in their own PRs without touching the harness itself.

## Running the set

Against a live stack (docker-compose or EKS, wherever Prometheus/flagd for the
target service are reachable). `--alerter-history` should point at whatever
file the detector instance under test is writing:

```bash
for c in case_real_incident case_cart_failure case_image_slow case_quiet_window; do
  python aiops/incident_replay.py run "aiops/incident_scenarios/$c.json" \
      --alerter-history report/mandate07b/alerter_history.jsonl \
      | tee "report/mandate07b/run-${c}.log"
done
```

Each run writes `<scenario>.result.json` next to the scenario file (raw
per-event fired/lead-time + precision/recall + pass/fail verdict) and prints
the same summary to stdout for screenshotting as mandate evidence.

On grading day, when BTC injects the hidden scenario themselves instead of the
team: skip injection, score only, against the window you observed —

```bash
python aiops/incident_replay.py score aiops/incident_scenarios/case_real_incident.json \
    --start <unix_ts_start> --end <unix_ts_end>
```

`--check-remediation` (either subcommand) also pulls
`aiops/remediation/audit_log.jsonl` for the same window — used by MANDATE-22.

Scoring logic lives entirely in `aiops/incident_replay.py::score_events` /
`verdict_for_type` — plain, dependency-free Python, on purpose, so it's
reviewable end to end. Unit tests: `aiops/test_incident_replay.py`.

## Reproducing the stack these were measured on

The `#7b` numbers in `report/mandate07b/` were measured on the local
docker-compose stack, not EKS — flagd on EKS syncs from BTC's central server,
so the team cannot inject a labeled fault there. Two local-only settings are
needed and are **not** workarounds for a broken system:

- `CATALOG_SCHEMA_PHASE=read_new` on `product-catalog` (already committed to
  `docker-compose.yml`). `src/postgresql/init.sql` is at the post-contract
  schema — `catalog.products` has `image_url` and no legacy `picture` column —
  so `read_new` is the phase that matches it. The `dual_read` default emits
  `COALESCE(image_url, p.picture)` and fails with
  `column p.picture does not exist`.
- `LOCUST_HOST=http://frontend:8080` when starting `load-generator`, because
  `frontend-proxy` is skipped (its `flagd-ui` build target fails on
  `mix assets.setup`). Passed on the command line, not committed, since the
  normal stack does route through the proxy.

```bash
cd techx-corp-platform
docker compose up -d --no-build \
    flagd postgresql valkey-cart otel-collector prometheus opensearch kafka \
    product-catalog cart currency payment shipping email quote checkout \
    ad recommendation image-provider shopping-copilot ml-guard frontend
LOCUST_HOST=http://frontend:8080 LOCUST_USERS=15 \
    docker compose up -d --no-build load-generator
```

**Duration/timing caveat**: `duration_seconds`/`settle_seconds` are tuned for
this stack's traffic level, not universal — every metric rule involved uses a
trailing `rate(...[5m])` window, so if traffic volume is much higher or lower
than here, extend the injection duration until the fault clearly dominates
that 5-minute window before trusting a "did not fire" result.
