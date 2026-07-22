#!/usr/bin/env python3
"""
correlate.py  :  [W2-G7] Correlate stage: golden-signal correlation matrix + alert co-occurrence.

Purpose
-------
Produce two static JSON artifacts that serve as the RCA foundation for the
Diagnose stage (Detect --> Correlate --> Diagnose --> Act):

  correlation_matrix.json   :  Pearson + Spearman r between every (service, signal)
                               pair at lag 0 / 30s / 60s over a 24-hour window.
                               Leading indicators surface as high |r| at lag > 0.

  cooccurrence_matrix.json  :  How often each pair of rule_ids fires in the same
                               5-minute bucket from alerter_history.jsonl.
                               Maps to the Bedrock incident signature (K3 context).

Usage
-----
  # Full run against live Prometheus (port-forward or in-cluster):
  export PROM_URL=http://localhost:9090
  python correlate.py --hours 24

  # Offline (uses synthetic data â€” no Prometheus needed):
  python correlate.py --offline

  # Custom output paths:
  python correlate.py --hours 6 --corr-out my_corr.json --cooc-out my_cooc.json

Outputs
-------
Both JSON files are committed to the repo as baselines.  Re-run whenever you
want to refresh with new operational data.

References
----------
  spec: docs/ai/specs/golden_signals_detection.md
  spec: docs/ai/specs/anomaly_remediation.md  (closed-loop Correlate stage)
  ADR-007 (Drain3 / AIOps observability)
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy import stats

log = logging.getLogger("aiops.correlate")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CORR_OUT = os.path.join(_HERE, "correlation_matrix.json")
DEFAULT_COOC_OUT = os.path.join(_HERE, "cooccurrence_matrix.json")
DEFAULT_HISTORY = os.path.join(_HERE, "alerter_history.jsonl")

# Golden-signal PromQL definitions -- aligned exactly with rules.yaml (verified 2026-07-17).
#
# Key differences from the naive version:
#
# 1. latency_p95: excludes infra/observability services using the same exclusion list
#    as the live latency-p95-high rule. False-positive run on 12/07 showed flagd at 4.87s
#    kept triggering the latency rule; grafana/jaeger/etc have no SLO and add noise.
#
# 2. error_rate (non-checkout): excludes checkout so the checkout SLO (99%) and the
#    storefront SLO (99.5%) are measured separately, matching the two distinct rules in
#    rules.yaml (error-budget-burn-fast-standard vs error-budget-burn-fast-checkout).
#
# 3. error_rate_checkout: checkout only, separate series, separate SLO threshold (1%).
#
# 4. saturation: request throughput proxy (rate of completed requests) -- closest
#    approximation without kube metrics.
#
# 5. grpc_error_rate: gRPC-layer error rate using rpc_server_duration_milliseconds_count.
#    Captures faults that HTTP rules are blind to (e.g. productCatalogFailure chaos flag
#    manifests as rpc_grpc_status_code=13 with zero HTTP 5xx). Matches grpc-error-rate-high
#    rule in rules.yaml (semantics verified under chaos on 12/07).
#
# {ns} is substituted with the service_namespace label value at query time.
_INFRA_EXCLUSION = (
    'service_name!~"flagd|flagd-ui|otel-collector|grafana|jaeger|'
    'prometheus|opensearch|load-generator|llm"'
)

GOLDEN_SIGNAL_QUERIES: list[tuple[str, str]] = [
    (
        # p95 latency -- storefront SLO: < 1s.
        # Matches latency-p95-high rule in rules.yaml (infra services excluded).
        "latency_p95",
        "histogram_quantile(0.95, sum by (service_name, le) ("
        "rate(http_server_request_duration_seconds_bucket"
        '{{service_namespace="{ns}", ' + _INFRA_EXCLUSION + '}}[1m])))',
    ),
    (
        # 5xx error rate for non-checkout services -- SLO: < 0.5%.
        # Matches error-budget-burn-fast-standard in rules.yaml.
        "error_rate",
        "sum by (service_name) ("
        "rate(http_server_request_duration_seconds_count"
        '{{service_namespace="{ns}", service_name!="checkout",'
        ' http_response_status_code=~"5.."}}[1m]))'
        " / clamp_min(sum by (service_name) ("
        "rate(http_server_request_duration_seconds_count"
        '{{service_namespace="{ns}", service_name!="checkout"}}[1m])), 0.001)',
    ),
    (
        # 5xx error rate for checkout only -- SLO: < 1% (revenue-critical path).
        # Matches error-budget-burn-fast-checkout in rules.yaml.
        "error_rate_checkout",
        "sum by (service_name) ("
        "rate(http_server_request_duration_seconds_count"
        '{{service_namespace="{ns}", service_name="checkout",'
        ' http_response_status_code=~"5.."}}[1m]))'
        " / clamp_min(sum by (service_name) ("
        "rate(http_server_request_duration_seconds_count"
        '{{service_namespace="{ns}", service_name="checkout"}}[1m])), 0.001)',
    ),
    (
        # Request throughput as saturation proxy.
        # Excludes infra services same as latency_p95.
        "saturation",
        "sum by (service_name) ("
        "rate(http_server_request_duration_seconds_count"
        '{{service_namespace="{ns}", ' + _INFRA_EXCLUSION + '}}[1m]))',
    ),
    (
        # gRPC error rate -- captures productCatalogFailure chaos flag and any
        # RPC-layer fault that does NOT surface as HTTP 5xx (verified under chaos:
        # product-catalog reached 6.6% with rpc_grpc_status_code=13, threshold 5%).
        # Matches grpc-error-rate-high rule in rules.yaml.
        # Error status codes: 2=UNKNOWN, 4=DEADLINE_EXCEEDED, 13=INTERNAL, 14=UNAVAILABLE.
        "grpc_error_rate",
        "sum by (service_name) ("
        "rate(rpc_server_duration_milliseconds_count"
        '{{rpc_grpc_status_code=~"2|4|13|14"}}[1m]))'
        " / clamp_min(sum by (service_name) ("
        "rate(rpc_server_duration_milliseconds_count[1m])), 0.001)",
    ),
]

NAMESPACE = "techx-corp"

# Lags in seconds to test for leading-indicator detection
LAGS_SECONDS: list[int] = [0, 30, 60]

# 5-minute bucket width for co-occurrence (must match alerter.py)
COOC_BUCKET_SECONDS = 300


# ---------------------------------------------------------------------------
# Prometheus range query
# ---------------------------------------------------------------------------
def _prom_range_query(
    base_url: str,
    promql: str,
    start: float,
    end: float,
    step: int = 30,
    timeout: int = 15,
) -> dict[str, list[float]]:
    """
    Execute a Prometheus range query.

    Returns dict: {label_value -> [float, ...]}  (NaN/Inf dropped, gaps filled
    with NaN so all series have the same length).
    """
    import requests  # local import â€” not needed when running offline

    url = f"{base_url.rstrip('/')}/api/v1/query_range"
    params = {
        "query": promql,
        "start": start,
        "end": end,
        "step": step,
    }
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus error: {payload.get('error')}")

    # Expected number of data points
    n_points = math.ceil((end - start) / step) + 1

    result: dict[str, list[float]] = {}
    for series in payload["data"].get("result", []):
        label = series["metric"].get("service_name", "unknown")
        values_raw = series.get("values", [])  # [[ts, val], ...]
        # Build dense array aligned to [start, start+step, start+2*step, ...]
        ts_map: dict[int, float] = {}
        for ts_str, val_str in values_raw:
            try:
                v = float(val_str)
            except (TypeError, ValueError):
                continue
            if math.isnan(v) or math.isinf(v):
                continue
            ts_map[int(float(ts_str))] = v

        dense: list[float] = []
        for i in range(n_points):
            ts_expected = int(start) + i * step
            dense.append(ts_map.get(ts_expected, float("nan")))

        result[label] = dense

    return result


# ---------------------------------------------------------------------------
# Synthetic data (offline mode)
# ---------------------------------------------------------------------------
def _synthetic_timeseries(n: int = 2880, seed: int = 42) -> dict[str, dict[str, list[float]]]:
    """
    Generate realistic synthetic golden-signal timeseries for offline testing.

    Returns: {service_name -> {signal_name -> [float, ...]}}

    Encodes a simulated Bedrock incident at t=1200..1440:
      - product-reviews saturation spikes first  (leading indicator)
      - product-reviews latency follows 30s later
      - frontend latency follows 60s later
      - error_rate spikes at the same time as latency peaks
    """
    rng = np.random.default_rng(seed)

    services = ["frontend", "product-reviews", "checkout", "cart"]
    signals = ["latency_p95", "error_rate", "saturation"]

    data: dict[str, dict[str, list[float]]] = {s: {} for s in services}

    # Base noise levels per signal â€” kept small so the injected incident
    # has a high signal-to-noise ratio and is detectable in correlation tests.
    base = {"latency_p95": 0.15, "error_rate": 0.001, "saturation": 2.5}
    noise_scale = {"latency_p95": 0.005, "error_rate": 0.0001, "saturation": 0.05}

    for svc in services:
        for sig in signals:
            series = (
                base[sig]
                + rng.normal(0, noise_scale[sig], n)
                + noise_scale[sig] * np.sin(np.linspace(0, 4 * np.pi, n))  # diurnal
            )
            series = np.clip(series, 0, None)
            data[svc][sig] = series.tolist()

    # Inject Bedrock incident â€” use relative indices so the function works for any n.
    # Incident occupies the middle 10% of the series (minimum 30 steps).
    incident_start = n // 3
    incident_end = incident_start + max(30, n // 10)

    # Large spike amplitude (>> noise_scale) to produce |r| > 0.5 in correlation tests.
    SAT_SPIKE   = 8.0   # product-reviews saturation (leading indicator)
    LAT_SPIKE   = 3.0   # latency (follows saturation by 1 step = 30s)
    FRONT_SPIKE = 1.5   # frontend latency (follows by 2 steps = 60s)
    ERR_SPIKE   = 0.08  # error rate

    # 1. product-reviews saturation spikes first (leading indicator at lag=30s)
    for i in range(incident_start, incident_end):
        data["product-reviews"]["saturation"][i] += SAT_SPIKE

    # 2. product-reviews latency follows 1 step later (lag 30s)
    for i in range(incident_start + 1, min(incident_end + 1, n)):
        data["product-reviews"]["latency_p95"][i] += LAT_SPIKE

    # 3. frontend latency follows 2 steps later (lag 60s)
    for i in range(incident_start + 2, min(incident_end + 2, n)):
        data["frontend"]["latency_p95"][i] += FRONT_SPIKE

    # 4. error rate co-spikes with latency (lag 0 relative to latency)
    for i in range(incident_start + 1, min(incident_end + 1, n)):
        data["product-reviews"]["error_rate"][i] += ERR_SPIKE
        data["frontend"]["error_rate"][i] += ERR_SPIKE * 0.3

    return data


# ---------------------------------------------------------------------------
# Correlation computation
# ---------------------------------------------------------------------------
def _drop_nan_pairs(a: list[float], b: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Remove index positions where either series has NaN, return aligned arrays."""
    arr_a = np.array(a, dtype=float)
    arr_b = np.array(b, dtype=float)
    mask = ~(np.isnan(arr_a) | np.isnan(arr_b))
    return arr_a[mask], arr_b[mask]


def _shift(series: list[float], lag_steps: int) -> list[float]:
    """
    Shift a series forward by lag_steps positions.

    Signal A at lag=k means: does A[t] predict B[t+k]?
    We align A[0..n-k] with B[k..n].
    """
    if lag_steps == 0:
        return series
    return series[:-lag_steps] if lag_steps > 0 else series


def compute_correlation_matrix(
    timeseries: dict[str, dict[str, list[float]]],
    step_seconds: int = 30,
    lags_seconds: list[int] | None = None,
    min_points: int = 30,
) -> dict:
    """
    Compute Pearson and Spearman correlation between every (service, signal) pair
    at each requested lag.

    Parameters
    ----------
    timeseries   : {service -> {signal -> [float]}}
    step_seconds : seconds between consecutive data points
    lags_seconds : lags to test (default: LAGS_SECONDS)
    min_points   : minimum valid (non-NaN) overlapping points required

    Returns
    -------
    {
      "lags_seconds": [0, 30, 60],
      "step_seconds": 30,
      "generated_at": "<iso>",
      "pairs": {
        "<svcA>/<sigA> â†’ <svcB>/<sigB>": {
          "lag_0":  {"pearson_r": float, "pearson_p": float,
                     "spearman_r": float, "spearman_p": float, "n": int},
          "lag_30": {...},
          "lag_60": {...},
        },
        ...
      },
      "leading_indicators": [
        {"source": "product-reviews/saturation",
         "target": "frontend/latency_p95",
         "lag_s": 30,
         "spearman_r": 0.73,
         "interpretation": "saturation in product-reviews leads latency in frontend by 30s"},
        ...
      ]
    }
    """
    if lags_seconds is None:
        lags_seconds = LAGS_SECONDS

    # Build flat list of (service, signal, series) keys
    keys: list[tuple[str, str]] = []
    for svc, signals in sorted(timeseries.items()):
        for sig, _ in sorted(signals.items()):
            keys.append((svc, sig))

    pairs: dict[str, dict] = {}
    leading_indicators: list[dict] = []

    def _compute_pair(src_svc, src_sig, src_series, tgt_svc, tgt_sig, tgt_series):
        """Compute correlation for one directed pair (src predicts tgt at lag_s ahead)."""
        pair_key = f"{src_svc}/{src_sig} \u2192 {tgt_svc}/{tgt_sig}"
        pairs[pair_key] = {}
        best_spearman_r = 0.0
        best_lag = 0

        for lag_s in lags_seconds:
            lag_steps = lag_s // step_seconds
            label = f"lag_{lag_s}"

            src_shifted = _shift(src_series, lag_steps)
            tgt_aligned = tgt_series[lag_steps:] if lag_steps > 0 else tgt_series

            a_clean, b_clean = _drop_nan_pairs(src_shifted, tgt_aligned)

            if len(a_clean) < min_points:
                pairs[pair_key][label] = {
                    "pearson_r": None, "pearson_p": None,
                    "spearman_r": None, "spearman_p": None,
                    "n": int(len(a_clean)), "note": "insufficient data",
                }
                continue

            p_r, p_p = stats.pearsonr(a_clean, b_clean)
            s_r, s_p = stats.spearmanr(a_clean, b_clean)

            pairs[pair_key][label] = {
                "pearson_r": round(float(p_r), 4),
                "pearson_p": round(float(p_p), 6),
                "spearman_r": round(float(s_r), 4),
                "spearman_p": round(float(s_p), 6),
                "n": int(len(a_clean)),
            }

            if abs(s_r) > abs(best_spearman_r):
                best_spearman_r = s_r
                best_lag = lag_s

        # Leading indicator: use the stronger of Spearman/Pearson at each lag.
        # Spearman is preferred for operational data (robust to outliers), but
        # Pearson is used as a fallback when the signal is pulse-shaped and
        # Spearman rank mass is too diluted (e.g. a short burst in a long series).
        def _best_r_at(lag_label):
            entry = pairs[pair_key].get(lag_label) or {}
            sr = abs(entry.get("spearman_r") or 0.0)
            pr = abs(entry.get("pearson_r") or 0.0)
            return max(sr, pr), entry.get("spearman_r") or 0.0

        lag0_combined, _ = _best_r_at("lag_0")
        best_combined, best_spearman_for_report = _best_r_at(f"lag_{best_lag}")

        if (
            best_lag > 0
            and best_combined >= 0.45
            and best_combined > lag0_combined + 0.05
        ):
            leading_indicators.append({
                "source": f"{src_svc}/{src_sig}",
                "target": f"{tgt_svc}/{tgt_sig}",
                "lag_s": best_lag,
                "pearson_r": (pairs[pair_key].get(f"lag_{best_lag}") or {}).get("pearson_r"),
                "spearman_r": round(float(best_spearman_for_report), 4),
                "interpretation": (
                    f"{src_svc}/{src_sig} leads {tgt_svc}/{tgt_sig} by {best_lag}s "
                    f"(spearman r={best_spearman_for_report:.3f})"
                ),
            })

    # Both directions: Aâ†’B and Bâ†’A (both may be leading indicators in different scenarios)
    for i, (svc_a, sig_a) in enumerate(keys):
        for svc_b, sig_b in keys[i + 1:]:
            _compute_pair(svc_a, sig_a, timeseries[svc_a][sig_a],
                          svc_b, sig_b, timeseries[svc_b][sig_b])
            _compute_pair(svc_b, sig_b, timeseries[svc_b][sig_b],
                          svc_a, sig_a, timeseries[svc_a][sig_a])

    # Sort leading indicators by |spearman_r| descending
    leading_indicators.sort(key=lambda x: abs(x["spearman_r"]), reverse=True)

    return {
        "lags_seconds": lags_seconds,
        "step_seconds": step_seconds,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pairs": pairs,
        "leading_indicators": leading_indicators,
    }


# ---------------------------------------------------------------------------
# Co-occurrence computation
# ---------------------------------------------------------------------------
def load_alert_history(path: str) -> list[dict]:
    """Load alerter_history.jsonl. Returns [] if file missing (first run)."""
    if not os.path.isfile(path):
        log.warning("alert history not found at %s â€” co-occurrence will use empty history", path)
        return []
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                log.debug("skipping malformed history line: %s", exc)
    return records


def _synthetic_alert_history(n_incidents: int = 20, seed: int = 7) -> list[dict]:
    """
    Generate synthetic alert history for offline testing.

    Simulates two incident types:
      Type A (Bedrock): llm-rate-limit-429 + genai-latency-high + error-rate-high
      Type B (DB):      db-pool-exhaustion + checkout-failure-high + latency-p95-high
    """
    rng = np.random.default_rng(seed)
    base_ts = time.time() - 86400  # 24h ago
    records = []

    incident_a_rules = ["llm-rate-limit-429", "genai-latency-high", "error-rate-high"]
    incident_b_rules = ["db-pool-exhaustion", "checkout-failure-high", "latency-p95-high"]

    for i in range(n_incidents):
        ts = base_ts + i * 3600 + rng.integers(0, 300)
        incident_type = "A" if i % 3 != 0 else "B"
        rules = incident_a_rules if incident_type == "A" else incident_b_rules
        service = "product-reviews" if incident_type == "A" else "checkout"
        fp = f"{service}:{int(ts // COOC_BUCKET_SECONDS)}"

        for rule_id in rules:
            # Each rule fires in the same 5-min bucket Â± small jitter
            jitter = rng.integers(0, COOC_BUCKET_SECONDS)
            records.append({
                "ts": ts + jitter,
                "rule_id": rule_id,
                "service": service,
                "severity": "critical",
                "fingerprint": fp,
            })

    return records


def compute_cooccurrence_matrix(
    history: list[dict],
    bucket_seconds: int = COOC_BUCKET_SECONDS,
) -> dict:
    """
    Count how often each pair of rule_ids fires in the same time bucket.

    Returns
    -------
    {
      "bucket_seconds": 300,
      "generated_at": "<iso>",
      "total_buckets_with_alerts": int,
      "rule_fire_counts": {"rule_id": count, ...},
      "cooccurrence": {
        "<ruleA>|<ruleB>": {
          "count": int,
          "pct_of_ruleA_buckets": float,
          "pct_of_ruleB_buckets": float,
          "interpretation": "..."
        },
        ...
      }
    }
    """
    # Bucket â†’ set of rule_ids
    bucket_rules: dict[int, set] = defaultdict(set)
    rule_counts: dict[str, int] = defaultdict(int)

    for rec in history:
        ts = rec.get("ts", 0)
        rule_id = rec.get("rule_id", "unknown")
        bucket = int(float(ts) // bucket_seconds)
        bucket_rules[bucket].add(rule_id)
        rule_counts[rule_id] += 1

    # Count co-occurrences
    cooc_counts: dict[str, int] = defaultdict(int)
    for _bucket, rules_set in bucket_rules.items():
        rules_list = sorted(rules_set)
        for i, r_a in enumerate(rules_list):
            for r_b in rules_list[i + 1:]:
                pair_key = f"{r_a}|{r_b}"
                cooc_counts[pair_key] += 1

    # Build output
    cooccurrence: dict[str, dict] = {}
    for pair_key, count in sorted(cooc_counts.items(), key=lambda x: -x[1]):
        r_a, r_b = pair_key.split("|", 1)
        buckets_a = sum(1 for rules in bucket_rules.values() if r_a in rules)
        buckets_b = sum(1 for rules in bucket_rules.values() if r_b in rules)
        pct_a = round(count / buckets_a, 4) if buckets_a else 0.0
        pct_b = round(count / buckets_b, 4) if buckets_b else 0.0
        cooccurrence[pair_key] = {
            "count": count,
            "pct_of_ruleA_buckets": pct_a,
            "pct_of_ruleB_buckets": pct_b,
            "interpretation": (
                f"{r_a} and {r_b} co-occur in {count} bucket(s); "
                f"{pct_a:.0%} of {r_a} buckets, {pct_b:.0%} of {r_b} buckets"
            ),
        }

    return {
        "bucket_seconds": bucket_seconds,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_buckets_with_alerts": len(bucket_rules),
        "rule_fire_counts": dict(rule_counts),
        "cooccurrence": cooccurrence,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="[W2-G7] Correlate stage: correlation + co-occurrence")
    parser.add_argument("--hours", type=float, default=24.0,
                        help="Look-back window in hours (default: 24)")
    parser.add_argument("--step", type=int, default=30,
                        help="Prometheus range step in seconds (default: 30)")
    parser.add_argument("--namespace", default=NAMESPACE,
                        help=f"K8s service namespace label (default: {NAMESPACE})")
    parser.add_argument("--offline", action="store_true",
                        help="Use synthetic data â€” no Prometheus/history required")
    parser.add_argument("--corr-out", default=DEFAULT_CORR_OUT,
                        help="Output path for correlation_matrix.json")
    parser.add_argument("--cooc-out", default=DEFAULT_COOC_OUT,
                        help="Output path for cooccurrence_matrix.json")
    parser.add_argument("--history", default=DEFAULT_HISTORY,
                        help="Path to alerter_history.jsonl")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # 1. Build timeseries data
    # -----------------------------------------------------------------------
    if args.offline:
        log.info("offline mode â€” using synthetic timeseries")
        timeseries = _synthetic_timeseries()
        step = args.step
    else:
        prom_url = os.environ.get("PROM_URL", "http://localhost:9090")
        log.info("querying Prometheus at %s for last %.1fh (step=%ds)",
                 prom_url, args.hours, args.step)

        end_ts = time.time()
        start_ts = end_ts - args.hours * 3600
        step = args.step

        timeseries: dict[str, dict[str, list[float]]] = defaultdict(dict)
        for sig_name, query_tpl in GOLDEN_SIGNAL_QUERIES:
            query = query_tpl.format(ns=args.namespace)
            log.info("  fetching signal: %s", sig_name)
            try:
                svc_series = _prom_range_query(prom_url, query, start_ts, end_ts, step=step)
                for svc, series in svc_series.items():
                    timeseries[svc][sig_name] = series
                log.info("  â†’ %d service(s) found", len(svc_series))
            except Exception as exc:  # noqa: BLE001
                log.error("  Prometheus query failed for %s: %s", sig_name, exc)

        if not timeseries:
            log.error("no timeseries data fetched â€” aborting. Use --offline to test without Prometheus.")
            sys.exit(1)

    # -----------------------------------------------------------------------
    # 2. Correlation matrix
    # -----------------------------------------------------------------------
    log.info("computing correlation matrix (lags=%s)...", LAGS_SECONDS)
    corr_result = compute_correlation_matrix(timeseries, step_seconds=step)
    n_pairs = len(corr_result["pairs"])
    n_leading = len(corr_result["leading_indicators"])
    log.info("  %d pairs computed, %d leading indicator(s) identified", n_pairs, n_leading)

    with open(args.corr_out, "w", encoding="utf-8") as fh:
        json.dump(corr_result, fh, indent=2)
    log.info("correlation matrix written â†’ %s", args.corr_out)

    if corr_result["leading_indicators"]:
        log.info("top leading indicators:")
        for li in corr_result["leading_indicators"][:5]:
            log.info("  %s", li["interpretation"])

    # -----------------------------------------------------------------------
    # 3. Co-occurrence matrix
    # -----------------------------------------------------------------------
    if args.offline:
        log.info("offline mode â€” using synthetic alert history")
        history = _synthetic_alert_history()
    else:
        history = load_alert_history(args.history)
        log.info("loaded %d alert history records from %s", len(history), args.history)

    log.info("computing alert co-occurrence matrix...")
    cooc_result = compute_cooccurrence_matrix(history)
    n_pairs_cooc = len(cooc_result["cooccurrence"])
    log.info("  %d co-occurring rule pairs found across %d alert buckets",
             n_pairs_cooc, cooc_result["total_buckets_with_alerts"])

    with open(args.cooc_out, "w", encoding="utf-8") as fh:
        json.dump(cooc_result, fh, indent=2)
    log.info("co-occurrence matrix written â†’ %s", args.cooc_out)

    if cooc_result["cooccurrence"]:
        log.info("top co-occurring rule pairs:")
        for pair_key, entry in list(cooc_result["cooccurrence"].items())[:5]:
            log.info("  %s â€” count=%d", pair_key, entry["count"])

    log.info("done.")


if __name__ == "__main__":
    main()
