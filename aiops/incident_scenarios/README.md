# Labeled incident set (MANDATE-07 #7b / MANDATE-15)

3 committed cases, each a ground-truth-labeled scenario for
`aiops/incident_replay.py` (the replay/repro tool both mandates require):

| File | Type | Proves |
|---|---|---|
| `case_real_incident.json` | `real` | detector fires on a genuine incident (#7b precision/recall/lead-time) |
| `case_masking.json` | `masking` | a noise spike doesn't hide a smaller, separate real incident right after (#15) |
| `case_healthy_load.json` | `healthy_load` | elevated-but-legitimate traffic does not false-alarm (#15) |

Run against a live stack (docker-compose or EKS, wherever Prometheus/flagd for
this scenario's target service are reachable):

```bash
python aiops/incident_replay.py run aiops/incident_scenarios/case_real_incident.json
python aiops/incident_replay.py run aiops/incident_scenarios/case_masking.json
LOCUST_HOST=http://<frontend-host>:8080 \
  python aiops/incident_replay.py run aiops/incident_scenarios/case_healthy_load.json
```

Each run writes `<scenario>.result.json` next to the scenario file (raw
per-event fired/lead-time + precision/recall + pass/fail verdict) and prints
the same summary to stdout for screenshotting as mandate evidence.

On grading day, when BTC injects the hidden scenario set themselves instead of
the team: skip injection, score only, against the window you observed —

```bash
python aiops/incident_replay.py score aiops/incident_scenarios/case_real_incident.json \
    --start <unix_ts_start> --end <unix_ts_end>
```

`--check-remediation` (either subcommand) also pulls
`aiops/remediation/audit_log.jsonl` for the same window — use it for
MANDATE-22 cases to show detect→safety-check→act→verify(→rollback/escalate).

Scoring logic lives entirely in `aiops/incident_replay.py::score_events` /
`verdict_for_type` — plain, dependency-free Python, on purpose (MANDATE-15
requires the scoring logic to be open for a mentor to read). Unit tests for
both the scoring logic and these 3 scenario files:
`aiops/test_incident_replay.py`.

**Duration/timing caveat**: `duration_seconds`/`settle_seconds` in these files
are a starting point, not independently verified against live traffic —
`latency-p95-high`/`grpc-error-rate-high`/etc. all use a trailing
`rate(...[5m])` window, so if actual traffic volume is much higher or lower
than assumed, extend the injection duration until the fault clearly dominates
that 5-minute window before trusting a "did not fire" result.
