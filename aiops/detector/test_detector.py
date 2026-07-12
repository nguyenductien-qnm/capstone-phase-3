import pytest
from unittest.mock import MagicMock
import detector

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
    assert "Static" in alerts[0][1]

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
    assert "3-Sigma" in alerts[0][1]
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
    assert "so log khop=5" in alerts[0][1]
