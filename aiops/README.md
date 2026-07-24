# AIOps

- `log_clustering/`: reads raw logs and clusters recurring patterns with Drain3.
- `detector/`: evaluates telemetry rules (static SLO threshold + per-service rolling
  3-sigma) and emits operational alerts. Detect-only — no K8s write access, never
  touches flagd. MANDATE-07/#15.
- `remediation/`: closed-loop auto-mitigation for OOM (detect → safety-check
  (error-budget/blast-radius/dry-run) → restart pod → verify via real telemetry →
  circuit-breaker/escalate on failure). Separate component/ServiceAccount from
  `detector/` on purpose (least-privilege — detector never gets K8s write access).
  MANDATE-22.
- `incident_replay.py` + `incident_scenarios/`: shared replay/scoring harness and
  labeled incident set (real / masking / healthy_load) used to measure
  precision/recall/lead-time (#7b) and prove masking-resistance + no-false-alarm
  (MANDATE-15). See `incident_scenarios/README.md`.

Full method/decision history: `docs/ai/05_adrs.md` (ADR-012 detection method,
ADR-013 remediation, ADR-015 MANDATE-15 masking/baseline/MTTD).
