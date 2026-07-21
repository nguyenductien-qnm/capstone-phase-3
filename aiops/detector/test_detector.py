import time
import pytest
from unittest.mock import MagicMock
import detector


def field_values(alert):
    """Noi tat ca gia tri field (index 2 cua alert tuple) thanh 1 chuoi de assert substring."""
    return " ".join(str(value) for _, value, _ in alert[2])


def test_eval_metric_rule_static():
    # Setup mock Prometheus client
    prom = MagicMock()
    # Mock data returned: list of tuples (value, labels)
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

    # Clear history before test
    detector.metric_history.clear()

    alerts = detector.eval_metric_rule(rule, prom)
    # With threshold 1.0, checkout (1.5) should fire, storefront (0.5) should not
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
        "threshold": 10.0,  # High static threshold to test only 3-sigma
        "summary": "High latency alert",
        "severity": "warning",
    }

    detector.metric_history.clear()
    
    # Send normal history: 0.1, 0.11, 0.09, 0.1, 0.12 (mean ≈ 0.1, std_dev ≈ 0.01)
    history_values = [0.1, 0.11, 0.09, 0.1, 0.12]
    for val in history_values:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)

    # Now query returns an anomaly: 0.5 (which is way above mean + 3*std_dev)
    prom.query.return_value = [(0.5, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)

    assert len(alerts) == 1
    assert "3-Sigma" in field_values(alerts[0])
    assert "storefront" in alerts[0][0]

def test_eval_log_rule():
    osc = MagicMock()
    # Mock count_matches returning (count, sample_message)
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
    assert alerts[0][0] == "db-error"
    assert alerts[0][1] == "DB error detected"
    assert "5 / 5m" in field_values(alerts[0])
    assert "connection pool timeout" in field_values(alerts[0])


def test_metric_rule_dynamic_only_uses_dynamic_headline():
    """Chi lop 3-sigma keu -> headline KHONG duoc la summary static (trend hieu nham
    'p95 > 1s' khi gia tri thuc 6ms — review 16/07)."""
    prom = MagicMock()
    rule = {
        "id": "latency-test",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 10.0,
        "summary": "p95 > 1s - VI PHAM SLO",
        "summary_dynamic": "Lệch bất thường so với baseline (chưa chạm SLO)",
        "severity": "warning",
    }
    detector.metric_history.clear()
    for val in [0.1, 0.11, 0.09, 0.1, 0.12]:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)
    prom.query.return_value = [(0.5, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1
    assert "Lệch bất thường" in alerts[0][1]
    assert "VI PHAM SLO" not in alerts[0][1]



def test_eval_metric_rule_insufficient_history():
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
    
    # Only 3 points in history
    for val in [0.1, 0.1, 0.1]:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)
        
    # Send an anomaly
    prom.query.return_value = [(15.0, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)
    
    # Static threshold is 10.0, so static alert fires.
    # But EWMA shouldn't fire because len(history) < 5
    assert len(alerts) == 1
    assert "Static" in alerts[0][1]
    assert "EWMA" not in alerts[0][1]


def test_eval_metric_rule_op_lt():
    prom = MagicMock()
    rule = {
        "id": "success-rate-drop",
        "type": "metric",
        "query": "dummy_query",
        "op": "lt",
        "threshold": 0.5, # Static threshold is 0.5
        "summary": "Success rate drop",
        "severity": "critical",
    }
    detector.metric_history.clear()
    
    # Stable baseline around 0.99
    for val in [0.99, 0.98, 1.0, 0.99, 0.995]:
        prom.query.return_value = [(val, {"service_name": "checkout"})]
        detector.eval_metric_rule(rule, prom)
        
    # Sudden drop to 0.8. 
    # Static threshold is 0.5, so static won't fire.
    # But 0.8 is significantly below the baseline of 0.99 (mean) - 3*std
    prom.query.return_value = [(0.8, {"service_name": "checkout"})]
    alerts = detector.eval_metric_rule(rule, prom)
    
    assert len(alerts) == 1
    assert "EWMA 3-Sigma" in alerts[0][1]
    assert "checkout" in alerts[0][0]


def test_eval_log_rule_below_min_count():
    osc = MagicMock()
    osc.count_matches.return_value = (1, "ERROR something minor")

    rule = {
        "id": "db-error",
        "type": "log",
        "match_phrases": ["connection pool"],
        "min_count": 3,
        "window_minutes": 5,
        "summary": "DB error detected",
        "severity": "critical",
    }

    alerts = detector.eval_log_rule(rule, osc)
    # Should not trigger because 1 < 3
    assert len(alerts) == 0


def test_eval_metric_rule_multiple_services():
    prom = MagicMock()
    rule = {
        "id": "multi-service",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 10.0,
        "summary": "High latency",
        "severity": "warning",
    }
    detector.metric_history.clear()
    
    # Send stable baseline for both services
    for i in range(5):
        prom.query.return_value = [
            (0.1, {"service_name": "storefront"}),
            (0.5, {"service_name": "checkout"})
        ]
        detector.eval_metric_rule(rule, prom)
        
    # Anomaly on storefront only
    prom.query.return_value = [
        (2.0, {"service_name": "storefront"}),
        (0.5, {"service_name": "checkout"})
    ]
    alerts = detector.eval_metric_rule(rule, prom)
    
    # Only storefront should trigger an alert
    assert len(alerts) == 1
    assert "storefront" in alerts[0][0]
    assert "checkout" not in alerts[0][0]
# ---- k8s_status rule (review 17/07: OOM dot ngot khong log duoc, phai doc K8s API) ----

from types import SimpleNamespace


def _make_pod(name, labels, oomkilled=False):
    container_status = SimpleNamespace(
        name="main",
        last_state=SimpleNamespace(
            terminated=SimpleNamespace(reason="OOMKilled", finished_at=SimpleNamespace(timestamp=lambda: time.time()))
            if oomkilled else None
        ),
    )
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, labels=labels),
        status=SimpleNamespace(container_statuses=[container_status]),
    )


def test_eval_k8s_status_rule_detects_oomkilled_pod_with_no_log():
    """Tai hien dung phat hien 17/07: khong co log nao ca (app bi SIGKILL truoc khi
    kip ghi), nhung K8s API van xac nhan OOMKilled that -> van phai bat duoc."""
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(
        items=[_make_pod("ad-64766fcbc6-jbrwh", {"opentelemetry.io/name": "ad"}, oomkilled=True)]
    )
    rule = {
        "id": "oom-detected",
        "type": "k8s_status",
        "summary": "OutOfMemory / OOMKilled — pod bị giết vì hết RAM",
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
        items=[_make_pod("ad-64766fcbc6-jbrwh", {"opentelemetry.io/name": "ad"}, oomkilled=False)]
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
    core_v1.list_namespaced_pod.side_effect = RuntimeError("K8s API khong ket noi duoc")
    rule = {"id": "oom-detected", "type": "k8s_status", "summary": "x"}
    alerts = detector.eval_k8s_status_rule(rule, core_v1)
    assert alerts == []

