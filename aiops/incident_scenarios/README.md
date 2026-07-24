# Labeled incident set (MANDATE-07 #7b)

`case_real_incident.json` — ground-truth-labeled scenario for
`aiops/incident_replay.py` (the replay/repro tool `#7b` requires), proving
the detector fires end to end and reporting precision/recall/lead-time on a
labeled case, per the mandate's exact formula.

> This folder and `incident_replay.py` are built generically so MANDATE-15
> (masking-resistance, healthy-load false-positive check) and MANDATE-22
> (remediation replay via `--check-remediation`) can add their own scenario
> files here in their own PRs without touching the harness itself.

Run against a live stack (docker-compose or EKS, wherever Prometheus/flagd for
the target service are reachable):

```bash
python aiops/incident_replay.py run aiops/incident_scenarios/case_real_incident.json
```

Writes `case_real_incident.result.json` next to the scenario file (raw
per-event fired/lead-time + precision/recall) and prints the same summary to
stdout for screenshotting as mandate evidence.

On grading day, when BTC injects the hidden scenario themselves instead of the
team: skip injection, score only, against the window you observed —

```bash
python aiops/incident_replay.py score aiops/incident_scenarios/case_real_incident.json \
    --start <unix_ts_start> --end <unix_ts_end>
```

Scoring logic lives entirely in `aiops/incident_replay.py::score_events` /
`verdict_for_type` — plain, dependency-free Python, on purpose, so it's
reviewable end to end. Unit tests: `aiops/test_incident_replay.py`.

**Duration/timing caveat**: `duration_seconds`/`settle_seconds` in this file
are a starting point, not independently verified against live traffic —
`grpc-error-rate-high`/`error-budget-burn-fast-checkout` both use a trailing
`rate(...[5m])` window, so if actual traffic volume is much higher or lower
than assumed, extend the injection duration until the fault clearly dominates
that 5-minute window before trusting a "did not fire" result.
