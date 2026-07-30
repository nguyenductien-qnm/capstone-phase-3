# AIOps

- `log_clustering/`: reads raw logs and clusters recurring patterns with Drain3.
- `detector/`: evaluates telemetry rules (static SLO threshold + per-service rolling
  3-sigma) and emits operational alerts. Detect-only — no K8s write access, never
  touches flagd. MANDATE-07/#15.
- `incident_replay.py` + `incident_scenarios/`: replay/scoring harness and labeled
  incident set used to measure precision/recall/lead-time on a labeled case (#7b).
  See `incident_scenarios/README.md`.

Full method/decision history: `docs/ai/05_adrs.md` (ADR-012: detection method +
#7b addendum).
