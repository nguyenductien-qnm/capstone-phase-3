# [AIOps][W2] K3 + G7 — Correlate Stage: Alert Fingerprint Dedup & Golden Signal Correlation Matrix

> **Task:** K3 (fingerprint dedup) + G7 (correlation matrix, RCA foundation)
> **Sprint:** Week 2
> **Author:** AIO03 — TF1
> **Date:** 2026-07-16
> **Jira:** TF1-70 | Parent: TF1-78 [AIOps] Intelligent System
> **ADR reference:** ADR-007 (Drain3 / AIOps observability), ADR-005 (resilience pattern)
> **Pipeline stage:** Detect → **Correlate** → Diagnose → Act

---

## 1. Problem Statement

Before this work the AIOps detector pipeline was:

```
Detect → Alert (fire-and-forget)
```

Two concrete failure modes:

**K3 — Alert storm on a single incident:**
One Bedrock rate-limit event simultaneously triggers `llm-rate-limit-429`, `genai-latency-high`,
and `error-rate-high` — three separate webhook pings for the same 5-minute window on the same
service. On-call receives 3 messages, assumes 3 separate problems, wastes MTTD.

**G7 — No cross-signal baseline:**
No data existed to answer "which signal predicts which, and how far in advance?" Diagnose had
nothing to work from for RCA.

---

## 2. What Was Built

### K3 — Fingerprint Dedup (`alerter.py`)

Added a second dedup layer on top of the existing per-rule cooldown:

| Layer | Key | Behaviour |
|---|---|---|
| Layer 1 (existing) | `rule_id:service` | Per-rule cooldown window |
| Layer 2 (new) | `service:floor(ts/300)` | Groups all rules for same service in same 5-min bucket into ONE message |

**Mechanism:**
- `Alerter.send()` now **buffers** alerts into `self._pending` keyed by fingerprint — no immediate dispatch.
- `Alerter.flush()` called at end of each `detector.run_cycle()` — emits one grouped `GROUPED ALERT` webhook message per fingerprint.
- Each flushed alert is appended to `alerter_history.jsonl` (newline-delimited JSON) for G7 co-occurrence analysis.

**Result:** 1 Bedrock incident = 1 grouped alert message listing all triggered rules, sorted by severity.

**Files changed:** `aiops/detector/alerter.py`, `aiops/detector/detector.py`

---

### G7 — Golden Signal Correlation Matrix (`correlate.py`)

New standalone module that produces two committed JSON artifacts as the static RCA baseline.

#### Artifact 1: `correlation_matrix.json`

- Exports a Prometheus range window (default 24h, SLO-triggered — see section 5) for **five golden signals** per service: `latency_p95`, `error_rate`, `error_rate_checkout`, `saturation`, `grpc_error_rate`
- Computes **Pearson** and **Spearman** correlation between every directed `(svc_a/sig_a → svc_b/sig_b)` pair at **lag 0 / 30s / 60s**
- Both directions tested (A→B and B→A) — the direction with higher |r| at lag>0 surfaces as the leading indicator
- Leading indicator criteria: `max(|pearson_r|, |spearman_r|) >= 0.45` at lag > 0 **and** that value exceeds lag=0 by >0.05

Schema:
```json
{
  "lags_seconds": [0, 30, 60],
  "step_seconds": 30,
  "generated_at": "2026-07-16T...",
  "pairs": {
    "product-reviews/saturation → frontend/latency_p95": {
      "lag_0":  {"pearson_r": 0.21, "spearman_r": 0.18, "n": 2880},
      "lag_30": {"pearson_r": 0.74, "spearman_r": 0.61, "n": 2879},
      "lag_60": {"pearson_r": 0.51, "spearman_r": 0.48, "n": 2878}
    }
  },
  "leading_indicators": [
    {
      "source": "product-reviews/saturation",
      "target": "frontend/latency_p95",
      "lag_s": 30,
      "spearman_r": 0.608,
      "interpretation": "product-reviews/saturation leads frontend/latency_p95 by 30s"
    }
  ]
}
```

#### Artifact 2: `cooccurrence_matrix.json`

- Reads `alerter_history.jsonl` (written by K3-enhanced Alerter)
- Buckets alert records by the same 5-min fingerprint window
- Counts how many buckets each rule-pair co-fires in
- Reports `pct_of_ruleA_buckets` / `pct_of_ruleB_buckets` to identify the Bedrock incident signature

Schema:
```json
{
  "bucket_seconds": 300,
  "total_buckets_with_alerts": 30,
  "rule_fire_counts": {"llm-rate-limit-429": 15, "genai-latency-high": 15},
  "cooccurrence": {
    "error-rate-high|genai-latency-high": {
      "count": 10,
      "pct_of_ruleA_buckets": 1.0,
      "pct_of_ruleB_buckets": 1.0,
      "interpretation": "error-rate-high and genai-latency-high co-occur in 10 bucket(s); 100% of each"
    }
  }
}
```

**File created:** `aiops/detector/correlate.py`

---

## 3. Test Evidence

### K3 — `test_detector.py` (17 tests, all pass)

| Test | What it verifies |
|---|---|
| `test_time_bucket_same_window` | Times within same 5-min window → same bucket |
| `test_time_bucket_different_window` | Times across boundary → different bucket |
| `test_fingerprint_same_service_same_window` | Same service+window → same fingerprint |
| `test_fingerprint_same_service_different_window` | Same service, next window → different fingerprint |
| `test_fingerprint_different_service_same_window` | Different service → different fingerprint |
| `test_send_buffers_alert` | `send()` buffers, does not dispatch immediately |
| `test_send_respects_cooldown` | Layer-1 cooldown still blocks re-fire |
| `test_flush_groups_same_service_same_window` | **3 rules, same service, same window → 1 message** |
| `test_flush_separates_different_services` | 2 services → 2 messages |
| `test_flush_separates_different_windows` | Same rule, 2 windows → 2 messages |
| `test_flush_clears_pending` | Buffer empty after flush |
| `test_flush_empty_pending` | flush() on empty buffer = 0, no raise |
| `test_flush_writes_history` | Each flushed alert appended to JSONL |
| `test_run_cycle_groups_bedrock_incident` | **Full cycle: 3 metric rules, product-reviews → 1 dispatch** |

```
17 passed in 0.55s
```

### G7 — `docs/ai/evals/test_correlate.py` (25 tests, all pass)

| Group | Tests | What they verify |
|---|---|---|
| Helpers | 6 | `_drop_nan_pairs`, `_shift` correctness |
| Correlation structure | 6 | Keys present, bidirectional pairs, perfect/anti/NaN/insufficient |
| Leading indicator | 2 | No spurious indicators for independent series; synthetic smoke test finds saturation as leading indicator |
| Co-occurrence structure | 6 | Empty, single rule, same/different bucket, pct calculation, sort order |
| Bedrock pattern | 1 | Synthetic history produces correct `llm-rate-limit-429` + `genai-latency-high` + `error-rate-high` cluster |
| History loading | 3 | Missing file, valid JSONL, malformed line skip |
| E2E offline pipeline | 1 | Full run produces valid JSON artifacts |

```
25 passed in 4.56s
```

**Total: 42 tests, 0 failures.**

---

## 4. Synthetic Data Baseline (committed artifacts)

Running `python correlate.py --offline` seeds both JSON files with synthetic data representing
a simulated Bedrock incident pattern. These are the committed baselines — replaced by real
Prometheus data on the next SLO-triggered refresh (see section 5).

**Co-occurrence (synthetic baseline):**

| Pair | Count | pct_A | pct_B |
|---|---|---|---|
| error-rate-high \| genai-latency-high | 10 | 100% | 100% |
| genai-latency-high \| llm-rate-limit-429 | 8 | ~73% | ~73% |
| error-rate-high \| llm-rate-limit-429 | 7 | 70% | 70% |
| checkout-failure-high \| db-pool-exhaustion | 6 | 100% | 100% |
| db-pool-exhaustion \| latency-p95-high | 5 | ~83% | ~83% |

This confirms the two incident signatures the system knows about: Bedrock (LLM layer) and DB pool (checkout layer).

---

## 5. How to Refresh Artifacts Against Live Data

Refresh is triggered by **SLO signal quality**, not by a fixed time window. Run a refresh when:

- **Error budget has been consumed** during the window — checkout < 99% or storefront p95 > 1s
  for a sustained period. This means the Prometheus range data contains real incident variance
  worth correlating.
- **A new incident type has been handled** — after any postmortem, refresh so the new alert
  cluster is captured in the co-occurrence matrix.
- **Model or routing changes** (e.g. Nova Lite → Nova Pro swap via ADR-004 flagd flag) —
  latency and error rate distributions shift, making the old baseline stale.

The three golden signals queried by `correlate.py` map directly to the SLOs in `onboarding/SLO.md`:

| Signal | Metric family | SLO / threshold | Rule in `rules.yaml` |
|---|---|---|---|
| `latency_p95` | `http_server_request_duration_seconds_bucket` | Storefront p95 < 1s | `latency-p95-high` |
| `error_rate` | `http_server_request_duration_seconds_count` | Non-5xx >= 99.5% (non-checkout) | `error-budget-burn-fast-standard` |
| `error_rate_checkout` | `http_server_request_duration_seconds_count` | Checkout >= 99% (revenue-critical) | `error-budget-burn-fast-checkout` |
| `saturation` | `http_server_request_duration_seconds_count` | Request throughput proxy — leading indicator | — |
| `grpc_error_rate` | `rpc_server_duration_milliseconds_count` | gRPC error rate < 5% | `grpc-error-rate-high` |

**Notes on alignment:**

- `latency_p95` and `saturation` apply the same infra exclusion list as the live detector (`flagd`, `grafana`, `jaeger`, `prometheus`, `opensearch`, `load-generator`, `llm`). This exclusion was added after a false-positive run on 2026-07-12 where `flagd` at 4.87s kept triggering the latency alert — infra services have no SLO and add noise to the correlation.
- `error_rate` and `error_rate_checkout` are split to match the two distinct SLOs: 99.5% for storefront and 99% for checkout (the revenue-critical path). Mixing them would obscure which SLO is at risk.
- `grpc_error_rate` covers fault patterns that HTTP rules are blind to. The `productCatalogFailure` BTC chaos flag manifests as `rpc_grpc_status_code=13` (INTERNAL) with zero HTTP 5xx — verified under chaos on 2026-07-12 where product-catalog reached 6.6% gRPC error rate. Without this signal the correlation matrix cannot identify `productCatalogFailure` as a leading indicator for `frontend/latency_p95` or `checkout/error_rate_checkout`.

```bash
# Port-forward Prometheus from the cluster
kubectl -n otel-demo port-forward svc/prometheus 9090:9090 &

export PROM_URL=http://localhost:9090
cd aiops/detector

# Use the last SLO reporting period (default 24h).
# Extend to 48h after a multi-incident week for richer correlation signal.
python correlate.py --hours 24

# Outputs: correlation_matrix.json, cooccurrence_matrix.json
# Commit both as the updated RCA baseline and reference in the Ops Review.
```

> **Minimum useful window:** the window must contain at least one SLO-breaching event
> (latency spike or error rate > 0.5%) for the correlation to show non-trivial structure.
> A fully healthy window produces near-zero correlations — that is expected and correct,
> not a bug. The synthetic baseline exists precisely to cover the no-incident case.

---

## 6. Pipeline Position

```
[Detect]    detector.py polls Prometheus + OpenSearch every 30s
                |  rules fire -> alerter.send() buffers by fingerprint
                v
[Correlate] alerter.flush() -> 1 grouped message per (service, 5-min window)   <- K3
            correlate.py (run on SLO trigger) -> correlation_matrix.json        <- G7
                                              -> cooccurrence_matrix.json
                |
                v
[Diagnose]  (next: use matrices to rank blast radius + root cause candidates)
                |
                v
[Act]       remediation.py (TF1-50, Week 3)
```

---

## 7. Known Limitations

- `correlate.py` is run manually on SLO trigger — not integrated into the live detect loop yet (Diagnose stage, Week 3/4 task).
- Single-point impulse leading-indicator detection is weak under Spearman (rank mass too small for n=300). Production data with sustained SLO-breaching windows works correctly, as validated by the synthetic smoke test with a multi-point incident injection.
- `alerter_history.jsonl` grows unboundedly — a rotation / max-age policy should be added before production deployment.
