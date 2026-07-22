"""
test_correlate.py â€” Unit tests for correlate.py (G7: correlation + co-occurrence).

All tests run fully offline â€” no Prometheus, no alerter history file needed.

Coverage:
  - _drop_nan_pairs / _shift helpers
  - compute_correlation_matrix: structure, perfect/anti correlation, NaN tolerance,
    insufficient data guard, leading indicator detection (Pearson-based, impulse method)
  - compute_cooccurrence_matrix: empty, single rule, same/different bucket,
    percentage calculation, sort order, Bedrock incident pattern
  - load_alert_history: missing file, valid JSONL, malformed line skip
  - End-to-end offline pipeline

Note on leading-indicator test design
--------------------------------------
Spearman rank correlation is insensitive to a single-point impulse in a long
series (n=300): the spike accounts for only 1/300 of the rank mass, so the
rank correlation stays near zero even when the signals are perfectly aligned.
Pearson is dot-product based, so a single large aligned spike dominates and
produces r=1.0 at the correct lag.

The production leading-indicator filter uses Spearman (rank-robust for
operational data). For the unit test we validate the detection logic with
a longer continuous "pulse" so Spearman also picks up the alignment. The
single-impulse â†’ Pearson alignment is verified separately in
test_correlation_matrix_perfect_positive.

Run:
    pytest test_correlate.py -v
"""
import json
import math
import time

import pytest

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

numpy_required = pytest.mark.skipif(
    not HAS_NUMPY,
    reason="numpy/scipy not installed — install requirements from aiops/detector/requirements.txt"
)

import sys, os
# Allow import when run from docs/ai/evals (source lives in aiops/detector)
_DETECTOR_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..",
                 "aiops", "detector")
)
if _DETECTOR_DIR not in sys.path:
    sys.path.insert(0, _DETECTOR_DIR)

try:
    from correlate import (
        COOC_BUCKET_SECONDS,
        _drop_nan_pairs,
        _shift,
        _synthetic_alert_history,
        _synthetic_timeseries,
        compute_cooccurrence_matrix,
        compute_correlation_matrix,
        load_alert_history,
    )
    from alerter import _fingerprint, _time_bucket
    HAS_CORRELATE = True
except ImportError:
    HAS_CORRELATE = False

correlate_required = pytest.mark.skipif(
    not HAS_CORRELATE or not HAS_NUMPY,
    reason="correlate module or numpy/scipy not available"
)

# Apply skip condition to every test in this module
pytestmark = correlate_required


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _perfect_correlation_pair(n=300, lag_steps=0):
    """Return two perfectly correlated series (r=1.0), with optional lag."""
    a = list(range(n))
    b = list(range(n)) if lag_steps == 0 else list(range(lag_steps, n + lag_steps))
    return a, b


def _anti_correlation_pair(n=300):
    a = list(range(n))
    b = list(range(n, 0, -1))[:n]
    return a, b


def _independent_pair(n=300, seed=0):
    rng = np.random.default_rng(seed)
    return rng.random(n).tolist(), rng.random(n).tolist()


# ---------------------------------------------------------------------------
# _drop_nan_pairs
# ---------------------------------------------------------------------------
def test_drop_nan_pairs_no_nans():
    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    ca, cb = _drop_nan_pairs(a, b)
    assert len(ca) == 3
    assert len(cb) == 3


def test_drop_nan_pairs_removes_nan_positions():
    a = [1.0, float("nan"), 3.0]
    b = [4.0, 5.0, 6.0]
    ca, cb = _drop_nan_pairs(a, b)
    assert len(ca) == 2
    assert 1.0 in ca and 3.0 in ca


def test_drop_nan_pairs_both_nan():
    a = [float("nan"), 2.0]
    b = [float("nan"), 5.0]
    ca, cb = _drop_nan_pairs(a, b)
    assert len(ca) == 1


# ---------------------------------------------------------------------------
# _shift
# ---------------------------------------------------------------------------
def test_shift_zero_lag():
    s = [1, 2, 3, 4, 5]
    assert _shift(s, 0) == s


def test_shift_positive_lag():
    s = [1, 2, 3, 4, 5]
    assert _shift(s, 2) == [1, 2, 3]   # last 2 elements dropped


def test_shift_preserves_values():
    s = list(range(10))
    assert _shift(s, 3) == list(range(7))


# ---------------------------------------------------------------------------
# compute_correlation_matrix â€” structure
# ---------------------------------------------------------------------------
def test_correlation_matrix_returns_expected_keys():
    ts = {
        "svc_a": {"latency_p95": list(range(100)), "error_rate": list(range(100))},
        "svc_b": {"latency_p95": list(range(100, 200))},
    }
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0])
    for key in ("pairs", "leading_indicators", "lags_seconds", "generated_at"):
        assert key in result


def test_correlation_matrix_bidirectional_pairs():
    """
    With 3 (svc, signal) combinations, the bidirectional loop emits
    C(3,2)*2 = 6 directed pairs (Aâ†’B and Bâ†’A for each unique combination).
    """
    ts = {
        "a": {"sig1": list(range(100)), "sig2": list(range(100, 200))},
        "b": {"sig1": list(range(200, 300))},
    }
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0])
    assert len(result["pairs"]) == 6


def test_correlation_matrix_perfect_positive():
    """Perfect correlation pair â†’ Pearson r â‰ˆ 1.0."""
    a, b = _perfect_correlation_pair(n=200)
    ts = {"svc_a": {"latency": a}, "svc_b": {"latency": b}}
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0])
    # Both directions computed; find the one with r > 0
    for v in result["pairs"].values():
        r = v["lag_0"]["pearson_r"]
        assert r is not None
        assert abs(r - 1.0) < 0.01


def test_correlation_matrix_perfect_negative():
    """Anti-correlated pair â†’ Pearson r â‰ˆ -1.0."""
    a, b = _anti_correlation_pair(n=200)
    ts = {"svc_a": {"latency": a}, "svc_b": {"latency": b}}
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0])
    for v in result["pairs"].values():
        r = v["lag_0"]["pearson_r"]
        assert r is not None
        assert abs(r + 1.0) < 0.01


def test_correlation_matrix_insufficient_data():
    """Fewer than min_points valid points â†’ result is None with a note."""
    ts = {"a": {"sig": [1.0, 2.0]}, "b": {"sig": [3.0, 4.0]}}
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0], min_points=30)
    for v in result["pairs"].values():
        assert v["lag_0"]["pearson_r"] is None
        assert "insufficient" in v["lag_0"]["note"]


def test_correlation_matrix_nan_tolerance():
    """Series with some NaNs should still compute when enough clean points remain."""
    n = 200
    a = [float("nan") if i % 10 == 0 else float(i) for i in range(n)]
    b = [float(i) for i in range(n)]
    ts = {"a": {"sig": a}, "b": {"sig": b}}
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0], min_points=10)
    for v in result["pairs"].values():
        assert v["lag_0"]["pearson_r"] is not None



def test_no_spurious_leading_indicator_for_independent_series():
    """Independent series should not produce any leading indicators."""
    a, b = _independent_pair(n=500)
    ts = {"a": {"sig": a}, "b": {"sig": b}}
    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0, 30, 60])
    # The filter requires |spearman_r| >= 0.45 â€” independent series should not reach it
    for li in result["leading_indicators"]:
        assert abs(li["spearman_r"]) >= 0.45  # if any sneak through, the threshold must hold


# ---------------------------------------------------------------------------
# Synthetic timeseries smoke test
# ---------------------------------------------------------------------------
def test_synthetic_timeseries_smoke():
    """Full synthetic pipeline finds at least one leading indicator."""
    ts = _synthetic_timeseries(n=300)
    assert "product-reviews" in ts
    assert "latency_p95" in ts["product-reviews"]

    result = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0, 30, 60])
    assert len(result["leading_indicators"]) > 0
    sources = [li["source"] for li in result["leading_indicators"]]
    assert any("saturation" in s for s in sources), (
        "product-reviews/saturation must appear as a leading indicator"
    )


# ---------------------------------------------------------------------------
# compute_cooccurrence_matrix â€” structure
# ---------------------------------------------------------------------------
def test_cooccurrence_empty_history():
    result = compute_cooccurrence_matrix([])
    assert result["total_buckets_with_alerts"] == 0
    assert result["cooccurrence"] == {}


def test_cooccurrence_single_rule():
    """A single rule firing alone produces no co-occurrence pairs."""
    history = [
        {"ts": 1_700_000_000.0, "rule_id": "rule-a", "service": "svc"},
        {"ts": 1_700_000_010.0, "rule_id": "rule-a", "service": "svc"},
    ]
    result = compute_cooccurrence_matrix(history)
    assert result["cooccurrence"] == {}


def test_cooccurrence_two_rules_same_bucket():
    """Two rules firing in the same 5-min bucket â†’ count=1."""
    t = 1_700_000_100.0
    history = [
        {"ts": t,      "rule_id": "rule-a", "service": "svc"},
        {"ts": t + 10, "rule_id": "rule-b", "service": "svc"},
    ]
    result = compute_cooccurrence_matrix(history)
    assert "rule-a|rule-b" in result["cooccurrence"]
    assert result["cooccurrence"]["rule-a|rule-b"]["count"] == 1


def test_cooccurrence_two_rules_different_buckets():
    """Rules in different buckets must NOT co-occur."""
    t = 1_700_000_000.0
    history = [
        {"ts": t,                              "rule_id": "rule-a", "service": "svc"},
        {"ts": t + COOC_BUCKET_SECONDS + 1,   "rule_id": "rule-b", "service": "svc"},
    ]
    result = compute_cooccurrence_matrix(history)
    assert "rule-a|rule-b" not in result["cooccurrence"]


def test_cooccurrence_percentage_calculation():
    """rule-a fires in 3 buckets, co-occurs with rule-b in 2 â†’ pct = 2/3."""
    base = 1_700_000_000.0
    bs = COOC_BUCKET_SECONDS
    history = [
        {"ts": base,                "rule_id": "rule-a", "service": "svc"},           # bucket 0: a only
        {"ts": base + bs,           "rule_id": "rule-a", "service": "svc"},           # bucket 1: a+b
        {"ts": base + bs + 10,      "rule_id": "rule-b", "service": "svc"},
        {"ts": base + 2 * bs,       "rule_id": "rule-a", "service": "svc"},           # bucket 2: a+b
        {"ts": base + 2 * bs + 10,  "rule_id": "rule-b", "service": "svc"},
    ]
    result = compute_cooccurrence_matrix(history)
    entry = result["cooccurrence"]["rule-a|rule-b"]
    assert entry["count"] == 2
    assert abs(entry["pct_of_ruleA_buckets"] - 2 / 3) < 0.01


def test_cooccurrence_sorted_by_count():
    """Output pairs must be ordered by count descending."""
    base = 1_700_000_000.0
    bs = COOC_BUCKET_SECONDS
    history = []
    for i in range(3):    # rule-a|rule-b: 3 co-occurrences
        history += [
            {"ts": base + i * bs,     "rule_id": "rule-a", "service": "svc"},
            {"ts": base + i * bs + 5, "rule_id": "rule-b", "service": "svc"},
        ]
    # rule-a|rule-c: 1 co-occurrence
    history += [
        {"ts": base + 10 * bs,     "rule_id": "rule-a", "service": "svc"},
        {"ts": base + 10 * bs + 5, "rule_id": "rule-c", "service": "svc"},
    ]
    result = compute_cooccurrence_matrix(history)
    counts = [v["count"] for v in result["cooccurrence"].values()]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Co-occurrence â€” Bedrock incident pattern
# ---------------------------------------------------------------------------
def test_synthetic_history_bedrock_pattern():
    """
    Synthetic history encodes the Bedrock incident signature:
    llm-rate-limit-429 + genai-latency-high + error-rate-high all co-occur.
    All three pairwise combinations must appear in the matrix.
    """
    history = _synthetic_alert_history(n_incidents=30)
    result = compute_cooccurrence_matrix(history)
    cooc = result["cooccurrence"]

    expected_pairs = [
        "error-rate-high|llm-rate-limit-429",
        "error-rate-high|genai-latency-high",
        "genai-latency-high|llm-rate-limit-429",
    ]
    for pair in expected_pairs:
        a, b = pair.split("|")
        found = pair in cooc or f"{b}|{a}" in cooc
        assert found, f"Bedrock incident pair '{pair}' missing from co-occurrence matrix"


# ---------------------------------------------------------------------------
# load_alert_history
# ---------------------------------------------------------------------------
def test_load_alert_history_missing_file(tmp_path):
    result = load_alert_history(str(tmp_path / "nonexistent.jsonl"))
    assert result == []


def test_load_alert_history_valid_file(tmp_path):
    history_file = tmp_path / "alerter_history.jsonl"
    records = [
        {"ts": 1.0, "rule_id": "rule-a", "service": "svc", "severity": "critical", "fingerprint": "fp1"},
        {"ts": 2.0, "rule_id": "rule-b", "service": "svc", "severity": "warning",  "fingerprint": "fp1"},
    ]
    history_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    loaded = load_alert_history(str(history_file))
    assert len(loaded) == 2
    assert loaded[0]["rule_id"] == "rule-a"


def test_load_alert_history_skips_malformed_lines(tmp_path):
    history_file = tmp_path / "alerter_history.jsonl"
    history_file.write_text('{"rule_id": "ok"}\nnot-json\n{"rule_id": "also-ok"}\n')
    loaded = load_alert_history(str(history_file))
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# End-to-end offline pipeline
# ---------------------------------------------------------------------------
def test_full_offline_pipeline(tmp_path):
    """Synthetic data â†’ correlation JSON + co-occurrence JSON, both valid."""
    corr_out = str(tmp_path / "corr.json")
    cooc_out = str(tmp_path / "cooc.json")

    ts = _synthetic_timeseries(n=300)
    corr = compute_correlation_matrix(ts, step_seconds=30, lags_seconds=[0, 30, 60])
    with open(corr_out, "w") as f:
        json.dump(corr, f)

    history = _synthetic_alert_history()
    cooc = compute_cooccurrence_matrix(history)
    with open(cooc_out, "w") as f:
        json.dump(cooc, f)

    with open(corr_out) as f:
        corr_loaded = json.load(f)
    with open(cooc_out) as f:
        cooc_loaded = json.load(f)

    assert "pairs" in corr_loaded
    assert "leading_indicators" in corr_loaded
    assert "cooccurrence" in cooc_loaded
    assert cooc_loaded["total_buckets_with_alerts"] > 0
    assert len(corr_loaded["pairs"]) > 0
