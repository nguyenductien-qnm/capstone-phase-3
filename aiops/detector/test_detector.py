"""
test_detector.py — Unit tests for detector.py + alerter.py (W1 + W2-K3 dedup).

Run:
    pytest test_detector.py -v
"""
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import detector
from alerter import Alerter, _fingerprint, _time_bucket


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_alert_history(tmp_path, monkeypatch):
    """Send every test's alert history to a temp file.

    `Alerter.flush()` appends each dispatched alert to the path returned by
    `alerter._history_path()`, which defaults to
    `aiops/detector/alerter_history.jsonl` — a file that is committed. Without
    this, running the suite appended real rows to that tracked file and left
    the working tree dirty. Autouse so a new test that flushes cannot
    reintroduce the leak by forgetting to opt in.
    """
    monkeypatch.setenv("ALERTER_HISTORY_FILE",
                       str(tmp_path / "alerter_history.jsonl"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_alerter(cooldown=0, bucket=300):
    """Return an Alerter in stdout mode with no cooldown (for test isolation)."""
    return Alerter(provider="stdout", cooldown_seconds=cooldown, bucket_seconds=bucket)


def field_values(alert):
    """Concatenate all field values in an alert tuple for substring assertions."""
    return " ".join(str(value) for _, value, _ in alert[2])


# ---------------------------------------------------------------------------
# W1 — static + 3-sigma metric detection
# ---------------------------------------------------------------------------
def test_eval_metric_rule_static():
    prom = MagicMock()
    prom.query.return_value = [
        (0.5, {"service_name": "storefront"}),
        (1.5, {"service_name": "checkout"}),
    ]
    rule = {
        "id": "latency-test",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 1.0,
        "summary": "High latency alert",
        "severity": "warning",
    }
    detector.metric_history.clear()
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1
    assert "checkout" in alerts[0][0]
    assert "Static" in field_values(alerts[0])


def test_eval_metric_rule_3sigma():
    prom = MagicMock()
    rule = {
        "id": "latency-test",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 10.0,
        "summary": "High latency alert",
        "severity": "warning",
    }
    detector.metric_history.clear()
    for val in [0.1, 0.11, 0.09, 0.1, 0.12]:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)
    prom.query.return_value = [(0.5, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1
    assert "3-Sigma" in field_values(alerts[0])
    assert "storefront" in alerts[0][0]


def _feed_baseline_then(prom, rule, spike, baseline=(0.1, 0.11, 0.09, 0.1, 0.12)):
    """Seed 5 quiet samples (min needed to arm 3-sigma), then evaluate `spike`."""
    detector.metric_history.clear()
    for val in baseline:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)
    prom.query.return_value = [(spike, {"service_name": "storefront"})]
    return detector.eval_metric_rule(rule, prom)


def _gated_rule(**over):
    rule = {
        "id": "latency-test",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 10.0,
        "summary": "p95 > SLO",
        "summary_dynamic": "Baseline deviation (not yet at SLO threshold)",
        "severity": "warning",
    }
    rule.update(over)
    return rule


def test_dynamic_gate_suppresses_spike_far_below_slo():
    """A 3-sigma spike that is nowhere near the SLO must NOT page.

    Measured on EKS 27/07: cart p95 moving 5ms -> 20ms clears 3-sigma while the SLO
    is 1000ms, and that shape produced 12 of 12 false alarms in 12h. The gate exists
    to make "statistically odd" and "operationally meaningful" stop being the same
    thing. 0.5 is >3-sigma over the 0.1 baseline but only 5% of threshold 10.0.
    """
    prom = MagicMock()
    alerts = _feed_baseline_then(prom, _gated_rule(dynamic_min_fraction=0.20), 0.5)
    assert alerts == []


def test_dynamic_gate_still_fires_once_value_approaches_slo():
    """Same spike shape, but now past the gate -> the early warning must survive."""
    prom = MagicMock()
    rule = _gated_rule(dynamic_min_fraction=0.20)
    alerts = _feed_baseline_then(prom, rule, 3.0)  # 30% of threshold, above gate 20%
    assert len(alerts) == 1
    assert "3-Sigma" in field_values(alerts[0])
    # Dynamic-only alert keeps the dynamic headline, not the SLO one.
    assert "Baseline deviation" in alerts[0][1]


def test_dynamic_gate_absent_keeps_previous_behaviour():
    """Regression guard: rules that don't declare the gate behave exactly as before.

    The gate was introduced with no default on purpose — 11 metric rules ship without
    it and none of their behaviour may change silently.
    """
    prom = MagicMock()
    alerts = _feed_baseline_then(prom, _gated_rule(), 0.5)
    assert len(alerts) == 1
    assert "3-Sigma" in field_values(alerts[0])


def test_static_breach_fires_even_when_below_dynamic_gate():
    """The gate only guards the dynamic layer; an SLO breach always pages.

    Gate 0.20 with threshold 10.0 would block anything under 2.0, so a static breach
    at 12.0 also proves the gate is not accidentally applied to layer 1.
    """
    prom = MagicMock()
    rule = _gated_rule(dynamic_min_fraction=0.20)
    detector.metric_history.clear()
    prom.query.return_value = [(12.0, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1
    assert "Static" in field_values(alerts[0])
    assert "p95 > SLO" in alerts[0][1]


def test_eval_log_rule():
    osc = MagicMock()
    osc.count_matches.return_value = (5, "ERROR connection pool timeout")
    rule = {
        "id": "db-error",
        "type": "log",
        "match_phrases": ["connection pool"],
        "min_count": 2,
        "window_minutes": 5,
        "summary": "DB error detected",
        "severity": "critical",
    }
    alerts = detector.eval_log_rule(rule, osc)
    assert len(alerts) == 1
    assert alerts[0][0] == "db-error:log"
    assert alerts[0][1] == "DB error detected"
    assert "5 / 5m" in field_values(alerts[0])
    assert "connection pool timeout" in field_values(alerts[0])


def test_metric_rule_dynamic_only_uses_dynamic_headline():
    """3-sigma-only alert must use summary_dynamic, not the SLO summary (review 16/07)."""
    prom = MagicMock()
    rule = {
        "id": "latency-test",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 10.0,
        "summary": "p95 > 1s - SLO BREACH",
        "summary_dynamic": "Baseline deviation (not yet at SLO threshold)",
        "severity": "warning",
    }
    detector.metric_history.clear()
    for val in [0.1, 0.11, 0.09, 0.1, 0.12]:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)
    prom.query.return_value = [(0.5, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1
    assert "Baseline deviation" in alerts[0][1]
    assert "SLO BREACH" not in alerts[0][1]


# ---------------------------------------------------------------------------
# W1 — k8s_status rule (OOM via K8s API, not logs)
# ---------------------------------------------------------------------------
def _make_pod(name, labels, oomkilled=False):
    container_status = SimpleNamespace(
        name="main",
        last_state=SimpleNamespace(
            terminated=SimpleNamespace(
                reason="OOMKilled",
                finished_at=SimpleNamespace(timestamp=lambda: time.time()),
            ) if oomkilled else None
        ),
    )
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, labels=labels),
        status=SimpleNamespace(container_statuses=[container_status]),
    )


def test_eval_k8s_status_rule_detects_oomkilled_pod_with_no_log():
    """No logs present (SIGKILL before write), but K8s API confirms OOMKilled."""
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(
        items=[_make_pod("ad-64766fcbc6-jbrwh",
                         {"opentelemetry.io/name": "ad"}, oomkilled=True)]
    )
    rule = {
        "id": "oom-detected",
        "type": "k8s_status",
        "summary": "OutOfMemory / OOMKilled — pod killed due to OOM",
        "k8s_namespace": "techx-tf1",
        "service_label_key": "opentelemetry.io/name",
        "lookback_seconds": 300,
    }
    alerts = detector.eval_k8s_status_rule(rule, core_v1)
    assert len(alerts) == 1
    assert alerts[0][0] == "oom-detected:ad"
    assert "OutOfMemory" in alerts[0][1]
    assert "ad-64766fcbc6-jbrwh" in field_values(alerts[0])


def test_eval_k8s_status_rule_no_alert_when_no_oom():
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(
        items=[_make_pod("ad-64766fcbc6-jbrwh",
                         {"opentelemetry.io/name": "ad"}, oomkilled=False)]
    )
    rule = {
        "id": "oom-detected",
        "type": "k8s_status",
        "summary": "OutOfMemory / OOMKilled",
        "k8s_namespace": "techx-tf1",
        "service_label_key": "opentelemetry.io/name",
    }
    alerts = detector.eval_k8s_status_rule(rule, core_v1)
    assert alerts == []


def test_eval_k8s_status_rule_handles_api_error_gracefully():
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.side_effect = RuntimeError("K8s API unreachable")
    rule = {"id": "oom-detected", "type": "k8s_status", "summary": "x"}
    alerts = detector.eval_k8s_status_rule(rule, core_v1)
    assert alerts == []


# ---------------------------------------------------------------------------
# W2-K3 — fingerprint helpers
# ---------------------------------------------------------------------------
def test_time_bucket_same_window():
    t1 = 1_000_200.0
    t2 = t1 + 99
    assert _time_bucket(t1) == _time_bucket(t2)


def test_time_bucket_different_window():
    t1 = 1_000_000.0
    t2 = t1 + 300
    assert _time_bucket(t1) != _time_bucket(t2)


def test_fingerprint_same_service_same_window():
    now = 1_700_000_000.0
    assert _fingerprint("product-reviews", now) == _fingerprint("product-reviews", now + 10)


def test_fingerprint_same_service_different_window():
    now = 1_700_000_000.0
    assert _fingerprint("product-reviews", now) != _fingerprint("product-reviews", now + 300)


def test_fingerprint_different_service_same_window():
    now = 1_700_000_000.0
    assert _fingerprint("product-reviews", now) != _fingerprint("checkout", now)


# ---------------------------------------------------------------------------
# W2-K3 — Alerter.send() buffering
# ---------------------------------------------------------------------------
def test_send_buffers_alert(capsys):
    alerter = _make_alerter()
    result = alerter.send("rule-a:svc-x", "critical", "rule-a", "msg 1")
    assert result is True
    captured = capsys.readouterr()
    assert captured.out == ""          # nothing printed yet — flush not called
    assert len(alerter._pending) == 1


def test_send_respects_cooldown():
    alerter = _make_alerter(cooldown=600)
    alerter.send("rule-a:svc-x", "critical", "rule-a", "first")
    result = alerter.send("rule-a:svc-x", "critical", "rule-a", "second")
    assert result is False
    total = sum(len(v) for v in alerter._pending.values())
    assert total == 1


# ---------------------------------------------------------------------------
# W2-K3 — flush() grouping
# ---------------------------------------------------------------------------
def test_flush_groups_same_service_same_window(capsys):
    """3 rules, same service, same window -> 1 grouped message."""
    alerter = _make_alerter()
    fixed_ts = 1_700_000_100.0
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = fixed_ts
        mock_time.strftime = time.strftime
        alerter.send("llm-rate-limit-429:product-reviews", "critical",
                     "llm-rate-limit-429", "LLM 429")
        alerter.send("genai-latency-high:product-reviews", "warning",
                     "genai-latency-high", "GenAI slow")
        alerter.send("error-rate-high:product-reviews", "critical",
                     "error-rate-high", "5xx spike")
    dispatched = alerter.flush()
    captured = capsys.readouterr()
    assert dispatched == 1
    assert "GROUPED ALERT" in captured.out
    assert "3 rule(s)" in captured.out
    assert "llm-rate-limit-429" in captured.out
    assert "genai-latency-high" in captured.out
    assert "error-rate-high" in captured.out


def test_flush_separates_different_services(capsys):
    alerter = _make_alerter()
    fixed_ts = 1_700_000_100.0
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = fixed_ts
        mock_time.strftime = time.strftime
        alerter.send("latency-p95-high:frontend", "warning", "latency-p95-high", "slow")
        alerter.send("latency-p95-high:product-reviews", "warning", "latency-p95-high", "slow")
    assert alerter.flush() == 2


def test_flush_separates_different_windows(capsys):
    alerter = _make_alerter()
    t1 = 1_700_000_100.0
    t2 = t1 + 300
    with patch("alerter.time") as mock_time:
        mock_time.strftime = time.strftime
        mock_time.time.return_value = t1
        alerter.send("llm-rate-limit-429:product-reviews", "critical",
                     "llm-rate-limit-429", "first")
        mock_time.time.return_value = t2
        alerter.send("llm-rate-limit-429:product-reviews", "critical",
                     "llm-rate-limit-429", "second")
    assert alerter.flush() == 2


def test_flush_clears_pending(capsys):
    alerter = _make_alerter()
    alerter.send("rule-a:svc", "info", "rule-a", "msg")
    alerter.flush()
    assert alerter._pending == {}


def test_flush_empty_pending():
    assert _make_alerter().flush() == 0


def test_flush_writes_history(tmp_path, capsys):
    """Each flushed alert must be appended to the history JSONL file."""
    import json
    history_file = tmp_path / "alerter_history.jsonl"
    import alerter as alerter_module
    with patch.object(alerter_module, "_history_path", return_value=str(history_file)):
        a = _make_alerter()
        fixed_ts = 1_700_000_100.0
        with patch("alerter.time") as mock_time:
            mock_time.time.return_value = fixed_ts
            mock_time.strftime = time.strftime
            a.send("llm-rate-limit-429:product-reviews", "critical",
                   "llm-rate-limit-429", "LLM 429")
        a.flush()
    lines = history_file.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["rule_id"] == "llm-rate-limit-429"
    assert record["service"] == "product-reviews"


# ---------------------------------------------------------------------------
# W2-K3 — run_cycle integration
# ---------------------------------------------------------------------------
def test_run_cycle_groups_bedrock_incident(capsys):
    """3 metric rules for the same service in the same window -> 1 grouped alert."""
    prom = MagicMock()
    osc = MagicMock()
    osc.count_matches.return_value = (0, None)
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[])

    prom.query.return_value = [(2.5, {"service_name": "product-reviews"})]

    cfg = {
        "rules": [
            {
                "id": "genai-latency-high",
                "type": "metric",
                "query": "histogram_quantile...",
                "op": "gt",
                "threshold": 2.0,
                "summary": "GenAI slow",
                "severity": "warning",
            },
            {
                "id": "error-rate-high",
                "type": "metric",
                "query": "rate(errors...)",
                "op": "gt",
                "threshold": 0.005,
                "summary": "5xx spike",
                "severity": "critical",
            },
            {
                "id": "latency-p95-high",
                "type": "metric",
                "query": "histogram_quantile...",
                "op": "gt",
                "threshold": 1.0,
                "summary": "p95 breach",
                "severity": "warning",
            },
        ]
    }

    alerter = _make_alerter()
    detector.metric_history.clear()

    fixed_ts = 1_700_000_100.0
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = fixed_ts
        mock_time.strftime = time.strftime
        dispatched = detector.run_cycle(cfg, prom, osc, core_v1, alerter)

    assert dispatched == 1, (
        "Three metric rules for the same service in the same window "
        "must produce exactly 1 grouped alert (K3 fingerprint dedup)"
    )
    captured = capsys.readouterr()
    assert "GROUPED ALERT" in captured.out
    assert "3 rule(s)" in captured.out
