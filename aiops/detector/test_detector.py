"""
test_detector.py — Unit tests for detector.py + alerter.py (W1 + W2-K3 dedup).

Run:
    pytest test_detector.py -v
"""
import re
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


# ---------------------------------------------------------------------------
# Silent failure — op=lt, dynamic_enabled, absent()
#
# Do duoc tren EKS 26/07: giet pod `payment` -> detector im lang HOAN TOAN. Moi rule
# metric hien co deu do "hong ma van tra loi" (latency cao, 5xx, error-ratio). Khong
# rule nao do duoc "khong con tra loi gi ca". Xem report/mandate15-eks/report.md muc 4.
#
# Cac test duoi la nguoi dung DAU TIEN cua nhanh op=lt va cua rule khong co nhan
# service_name — ca hai truoc day chua he duoc chay lan nao.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_detector_globals():
    """detector.py giu 2 dict o cap module (metric_history, empty_query_streak).

    Test cu goi metric_history.clear() bang tay; mot global moi ma quen clear se ro ri
    chinh xac theo kieu kho debug nhat (ket qua phu thuoc thu tu test). Autouse de khong
    the quen.
    """
    detector.reset_state()
    yield
    detector.reset_state()


def _collapse_rule(**over):
    """Rule kieu san thong luong: keu khi gia tri TUT xuong duoi nguong."""
    rule = {
        "id": "service-traffic-collapse",
        "type": "metric",
        "query": "dummy_ratio_query",
        "op": "lt",
        "threshold": 0.2,
        "summary": "Luong request SUT — dich vu co the da chet",
        "summary_dynamic": "Luong request tut bat thuong so voi baseline",
        "severity": "critical",
        "dynamic_enabled": False,
    }
    rule.update(over)
    return rule


def test_op_lt_static_fires_when_value_below_threshold():
    prom = MagicMock()
    prom.query.return_value = [(0.05, {"service_name": "payment"})]
    alerts = detector.eval_metric_rule(_collapse_rule(), prom)
    assert len(alerts) == 1
    assert alerts[0][0] == "service-traffic-collapse:payment"


def test_op_lt_static_silent_when_value_at_or_above_threshold():
    """Chan chieu so sanh bi dao. 0.9 la khoe manh, khong duoc keu."""
    prom = MagicMock()
    prom.query.return_value = [(0.9, {"service_name": "payment"})]
    assert detector.eval_metric_rule(_collapse_rule(), prom) == []


def test_static_method_string_uses_the_rule_operator():
    """Chuoi hien thi phai doc dung chieu: '<' cho op=lt, khong phai '>' cung nhac."""
    prom = MagicMock()
    prom.query.return_value = [(0.05, {"service_name": "payment"})]
    fields = field_values(detector.eval_metric_rule(_collapse_rule(), prom)[0])
    assert "<" in fields
    assert ">" not in fields


def test_dynamic_disabled_suppresses_3sigma_that_would_otherwise_fire():
    """Guong doi cua test_dynamic_gate_absent_keeps_previous_behaviour.

    CUNG input, chi khac dynamic_enabled: test kia khang dinh co 1 alert, test nay
    khang dinh khong co alert nao.
    """
    prom = MagicMock()
    assert _feed_baseline_then(prom, _gated_rule(dynamic_enabled=False), 0.5) == []


def test_dynamic_disabled_writes_no_metric_history():
    """Dang chay duoc cua khang dinh 'khong baseline nhiem doc, khong ton bo nho'.

    Rule tat tang dong khong duoc ghi mot mau nao vao metric_history — neu ghi thi sau
    su co, chuoi 0 cua luc chet se nam lai trong cua so va keo mean xuong.
    """
    prom = MagicMock()
    rule = _collapse_rule()
    for val in (1.0, 1.0, 0.9, 1.0, 1.0, 0.05):
        prom.query.return_value = [(val, {"service_name": "payment"})]
        detector.eval_metric_rule(rule, prom)
    assert detector.metric_history == {}


def test_lt_dynamic_reports_lower_bound_not_upper():
    """Nguong dong phai theo CHIEU cua rule.

    Truoc thay doi nay dynamic_threshold luon la mean+3sigma ke ca voi op=lt: nhanh lt
    so sanh voi mean-3sigma nhung chuoi hien thi lai in ra CAN TREN — on-call doc alert
    "gia tri tut xuong" ma thay mot con so lon hon ca gia tri hien tai.
    threshold=-1 de tang tinh khong the keu, co lap dung tang dong.
    """
    prom = MagicMock()
    rule = _collapse_rule(threshold=-1, dynamic_enabled=True)
    alerts = _feed_baseline_then(
        prom, rule, 0.0, baseline=(1.0, 1.1, 0.9, 1.0, 1.05)
    )
    assert len(alerts) == 1
    fields = field_values(alerts[0])
    assert "3-Sigma" in fields

    # Phai khang dinh QUAN HE SO HOC, khong phai su co mat cua chuoi "< th_dev=".
    # Chuoi do xuat hien du nguong in ra la can tren hay can duoi, nen assertion theo
    # chuoi khong phan biet duoc ban cu voi ban moi — da thu va no pass ca hai ben.
    m = re.search(r"th_dev=(-?[\d.]+), mean=(-?[\d.]+)", fields)
    assert m, f"khong doc duoc th_dev/mean tu: {fields}"
    th_dev, mean = float(m.group(1)), float(m.group(2))
    assert th_dev < mean, (
        f"op=lt phai in CAN DUOI (mean-3sigma), thuc te th_dev={th_dev} >= mean={mean} "
        f"— on-call doc alert 'gia tri tut xuong' ma thay mot nguong cao hon ca mean"
    )


def test_lt_dynamic_only_uses_dynamic_headline():
    """Ban sinh doi op=lt cua test_metric_rule_dynamic_only_uses_dynamic_headline."""
    prom = MagicMock()
    rule = _collapse_rule(threshold=-1, dynamic_enabled=True)
    alerts = _feed_baseline_then(
        prom, rule, 0.0, baseline=(1.0, 1.1, 0.9, 1.0, 1.05)
    )
    assert "tut bat thuong" in alerts[0][1]


@pytest.mark.parametrize("bad_op", ["GT", ">", "greater", ""])
def test_unsupported_op_skips_rule_and_logs_error(bad_op, caplog):
    """detector.py truoc day: `value > threshold if op == "gt" else value < threshold`.

    Moi gia tri khac "gt" roi vao nhanh else va chay thanh lt — rule DAO CHIEU trong im
    lang. Gio bo qua rule kem ERROR (fail-closed, khong doan).
    """
    prom = MagicMock()
    prom.query.return_value = [(999.0, {"service_name": "payment"})]
    with caplog.at_level("ERROR"):
        alerts = detector.eval_metric_rule(_gated_rule(op=bad_op), prom)
    assert alerts == []
    assert "op khong hop le" in caplog.text


def test_unsupported_op_does_not_even_query_prometheus():
    """Chan truoc khi goi query: rule hong khong duoc ton mot vong Prometheus nao."""
    prom = MagicMock()
    detector.eval_metric_rule(_gated_rule(op="greater"), prom)
    prom.query.assert_not_called()


def test_absent_style_rule_fires_with_service_from_promql_labels():
    """absent(metric{service_name="payment"}) tra ve 1 KEM nhan cua selector.

    Nho vay dedup_key mang ten service that chu khong phai "unknown" — dieu kien de
    cooldown, nhom alert va cham diem incident_replay deu dung.
    """
    prom = MagicMock()
    prom.query.return_value = [(1.0, {"service_name": "payment",
                                      "span_kind": "SPAN_KIND_SERVER"})]
    rule = {
        "id": "service-absent-payment",
        "type": "metric",
        "query": 'absent(traces_span_metrics_calls_total{service_name="payment"})',
        "op": "gt",
        "threshold": 0,
        "summary": "payment KHONG con phat ra span nao",
        "severity": "critical",
        "dynamic_enabled": False,
        "expect_series": False,
    }
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1
    assert alerts[0][0] == "service-absent-payment:payment"


def test_run_cycle_absent_rule_groups_under_real_service_not_unknown(capsys):
    """Dang chay duoc cua ly do chon absent() voi matcher '=' thay vi '=~'.

    Aggregation (sum/rate) va matcher regex deu xoa nhan truoc khi absent() kip doc,
    cho ra {} -> svc="unknown" -> moi rule absent don chung mot ro "unknown".
    """
    prom = MagicMock()
    prom.query.return_value = [(1.0, {"service_name": "payment"})]
    osc = MagicMock()
    osc.count_matches.return_value = (0, None)
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[])

    cfg = {
        "rules": [{
            "id": "service-absent-payment",
            "type": "metric",
            "query": 'absent(traces_span_metrics_calls_total{service_name="payment"})',
            "op": "gt",
            "threshold": 0,
            "summary": "payment bien mat khoi telemetry",
            "severity": "critical",
            "dynamic_enabled": False,
            "expect_series": False,
        }]
    }
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = 1_700_000_100.0
        mock_time.strftime = time.strftime
        detector.run_cycle(cfg, prom, osc, core_v1, _make_alerter())

    out = capsys.readouterr().out
    assert "payment" in out
    assert "unknown" not in out


# ---------------------------------------------------------------------------
# Detector tu to cao rule cam cua chinh no
#
# PromQL sai ten metric TRA VE CHUOI RONG chu khong nem loi, va eval_metric_rule nuot
# im lang chuoi rong. Do la cach `kafka-consumer-lag-high` nam cam hang tuan trong khi
# ai cung tuong no dang canh queue lag (do 26/07, report/mandate15-eks/report.md 4.4).
# ---------------------------------------------------------------------------
def _silent_rule(**over):
    rule = {
        "id": "kafka-lag-test",
        "type": "metric",
        "query": 'max by (group) (kafka_consumer_group_lag{namespace="techx-tf1"})',
        "op": "gt",
        "threshold": 1000,
        "summary": "Kafka consumer lag cao",
        "severity": "warning",
    }
    rule.update(over)
    return rule


def _silent_cfg(cycles=2, **over):
    return {"silent_rule_cycles": cycles, "rules": [_silent_rule(**over)]}


def _cycle_deps(query_result=None):
    """(prom, osc, core_v1) voi query tra ve `query_result` (mac dinh: rong)."""
    prom = MagicMock()
    prom.query.return_value = query_result if query_result is not None else []
    osc = MagicMock()
    osc.count_matches.return_value = (0, None)
    core_v1 = MagicMock()
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[])
    return prom, osc, core_v1


def test_empty_series_increments_silent_streak():
    prom, _, _ = _cycle_deps()
    rule = _silent_rule()
    for _ in range(3):
        detector.eval_metric_rule(rule, prom)
    assert detector.empty_query_streak["kafka-lag-test"] == 3


def test_non_empty_series_resets_silent_streak():
    prom, _, _ = _cycle_deps()
    rule = _silent_rule()
    detector.eval_metric_rule(rule, prom)
    detector.eval_metric_rule(rule, prom)
    prom.query.return_value = [(5.0, {"service_name": "fraud-detection"})]
    detector.eval_metric_rule(rule, prom)
    assert "kafka-lag-test" not in detector.empty_query_streak


def test_query_exception_does_not_count_as_silent():
    """Prometheus sap la su co HA TANG, khong phai bang chung rule mu.

    Dem no vao se bao "query sai ten metric" moi khi Prometheus sap — dung luc on-call
    can tin cay nhat.
    """
    prom = MagicMock()
    prom.query.side_effect = RuntimeError("prometheus down")
    rule = _silent_rule()
    for _ in range(3):
        detector.eval_metric_rule(rule, prom)
    assert detector.empty_query_streak == {}


def test_run_cycle_does_not_report_silent_rule_before_threshold():
    prom, osc, core_v1 = _cycle_deps()
    dispatched = detector.run_cycle(_silent_cfg(cycles=2), prom, osc, core_v1,
                                    _make_alerter())
    assert dispatched == 0


def test_run_cycle_reports_silent_rule_exactly_once_at_threshold(capsys):
    """Chot chan hoi quy `>=` thay vi `==`.

    Viet `>=` la phan xa tu nhien va no khien canh bao ban lai MOI chu ky cho toi het
    doi rule — bien mot canh bao huu ich thanh nguon spam khien on-call tat thong bao.
    """
    prom, osc, core_v1 = _cycle_deps()
    cfg = _silent_cfg(cycles=2)
    alerter = _make_alerter()
    total = 0
    per_cycle = []
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = 1_700_000_100.0
        mock_time.strftime = time.strftime
        for _ in range(4):
            n = detector.run_cycle(cfg, prom, osc, core_v1, alerter)
            per_cycle.append(n)
            total += n
    assert total == 1, f"phai bao dung 1 lan, thuc te {per_cycle}"
    assert per_cycle[1] == 1, f"phai bao o chu ky thu 2, thuc te {per_cycle}"
    assert "detector-silent-rule" in capsys.readouterr().out


def test_silent_rule_report_recovers_and_rearms():
    """Mu -> song -> mu thi phai bao lai lan nua, khong im luon."""
    prom, osc, core_v1 = _cycle_deps()
    cfg = _silent_cfg(cycles=2)
    alerter = _make_alerter()
    total = 0
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = 1_700_000_100.0
        mock_time.strftime = time.strftime
        for _ in range(2):
            total += detector.run_cycle(cfg, prom, osc, core_v1, alerter)
        prom.query.return_value = [(5.0, {"service_name": "fraud-detection"})]
        detector.run_cycle(cfg, prom, osc, core_v1, alerter)
        prom.query.return_value = []
        for _ in range(2):
            total += detector.run_cycle(cfg, prom, osc, core_v1, alerter)
    assert total == 2


def test_expect_series_false_never_reports_silent_rule():
    """Rule rong-khi-khoe (burn-rate co menh de `and`, absent() cua service dang song)."""
    prom, osc, core_v1 = _cycle_deps()
    cfg = _silent_cfg(cycles=2, expect_series=False)
    alerter = _make_alerter()
    total = sum(detector.run_cycle(cfg, prom, osc, core_v1, alerter) for _ in range(10))
    assert total == 0


def test_silent_rule_report_is_info_severity_and_rule_scoped_key():
    """severity=info, va dedup key mang rule_id o o "service".

    alerter tach service tu dedup_key, nen moi rule mu thanh mot nhom rieng. Dung key
    chung se bi cooldown nuot rule mu thu hai tro di ngay trong cung chu ky.
    """
    prom, osc, core_v1 = _cycle_deps()
    alerter = MagicMock()
    for _ in range(2):
        detector.run_cycle(_silent_cfg(cycles=2), prom, osc, core_v1, alerter)
    calls = [c for c in alerter.send.call_args_list
             if c.args[0].startswith("detector-silent-rule")]
    assert len(calls) == 1
    dedup_key, severity, rule_id = calls[0].args[0], calls[0].args[1], calls[0].args[2]
    assert dedup_key == "detector-silent-rule:kafka-lag-test"
    assert severity == "info"
    assert rule_id == "detector-silent-rule"


def test_silent_rule_report_names_the_query_in_fields():
    """Alert phai hanh dong duoc, khong chi to cao suong."""
    prom, osc, core_v1 = _cycle_deps()
    alerter = MagicMock()
    for _ in range(2):
        detector.run_cycle(_silent_cfg(cycles=2), prom, osc, core_v1, alerter)
    call = next(c for c in alerter.send.call_args_list
                if c.args[0].startswith("detector-silent-rule"))
    fields = " ".join(str(v) for _, v, _ in call.kwargs["fields"])
    assert "kafka-lag-test" in fields
    assert "kafka_consumer_group_lag" in fields


def test_log_rule_with_zero_matches_is_not_reported_as_silent():
    """Chan pham vi: log rule tra count=0 hop le suot ngay."""
    prom, osc, core_v1 = _cycle_deps()
    cfg = {
        "silent_rule_cycles": 2,
        "rules": [{
            "id": "dns-resolution-error",
            "type": "log",
            "match_phrases": ["NXDOMAIN"],
            "min_count": 1,
            "summary": "Loi DNS",
            "severity": "warning",
        }],
    }
    alerter = _make_alerter()
    total = sum(detector.run_cycle(cfg, prom, osc, core_v1, alerter) for _ in range(5))
    assert total == 0


def test_silent_after_one_reports_on_first_cycle():
    """Ngu nghia cua `--once`: mot chu ky du de goi ten moi rule tra ve 0 series.

    Bien --once thanh LINTER — sua rules.yaml xong chay mot lenh la biet rule nao go sai
    ten metric, thay vi doi 60 phut o che do chay lien tuc.
    """
    prom, osc, core_v1 = _cycle_deps()
    with patch("alerter.time") as mock_time:
        mock_time.time.return_value = 1_700_000_100.0
        mock_time.strftime = time.strftime
        dispatched = detector.run_cycle(
            {"rules": [_silent_rule()]}, prom, osc, core_v1,
            _make_alerter(), silent_after=1,
        )
    assert dispatched == 1


def test_silent_rule_cycles_defaults_when_cfg_omits_it():
    """cfg khong khai bao thi dung SILENT_RULE_CYCLES, khong phai bao ngay."""
    prom, osc, core_v1 = _cycle_deps()
    alerter = _make_alerter()
    total = sum(
        detector.run_cycle({"rules": [_silent_rule()]}, prom, osc, core_v1, alerter)
        for _ in range(5)
    )
    assert total == 0
    assert detector.SILENT_RULE_CYCLES > 5


# ---------------------------------------------------------------------------
# MANDATE-15 — masking-resistance (winsorize)
#
# Test nay giu nguyen tu PR #343 (tac gia TienThanh). Phan code no bao ve da duoc
# dat lai vao cau truc hien tai cua eval_metric_rule (cong SLO + dynamic_enabled +
# nguong theo chieu op), nhung khang dinh thi khong doi.
# ---------------------------------------------------------------------------
def test_dynamic_detection_not_masked_by_prior_spike():
    """MANDATE-15 masking case: mot spike nhieu don le khong duoc phep nang baseline
    truot len du de che mot su co RIENG BIET, NHO HON ngay sau do.

    Hoi quy cho loi ma eval_metric_rule nhoi gia tri bat thuong THO vao metric_history,
    keo mean/std ve phia spike suot ~30 chu ky va day dynamic_threshold len tren gia tri
    tiep theo — von that su bat thuong nhung nho hon.
    """
    prom = MagicMock()
    rule = {
        "id": "latency-test",
        "type": "metric",
        "query": "dummy_query",
        "op": "gt",
        "threshold": 100.0,  # nguong tinh khong bao gio keu -> co lap dung tang 3-sigma
        "summary": "High latency alert",
        "severity": "warning",
    }
    detector.reset_state()

    for val in [0.1, 0.11, 0.09, 0.1, 0.12]:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)

    prom.query.return_value = [(5.0, {"service_name": "storefront"})]
    spike_alerts = detector.eval_metric_rule(rule, prom)
    assert len(spike_alerts) == 1

    prom.query.return_value = [(0.5, {"service_name": "storefront"})]
    incident_alerts = detector.eval_metric_rule(rule, prom)
    assert len(incident_alerts) == 1, (
        "mot spike truoc do khong duoc phep nang mean/std du de che mot su co "
        "rieng biet, nho hon trong cung cua so"
    )


def test_winsorize_clips_the_stored_sample_not_the_fired_value():
    """Kep chi anh huong thu duoc GHI vao history, khong anh huong quyet dinh keu.

    Neu ai do nham va kep ca gia tri dem so sanh thi spike se thoi khong keu nua —
    tuc bien mot ban va chong-che thanh mot lo hong phat hien.
    """
    prom = MagicMock()
    rule = {
        "id": "latency-test", "type": "metric", "query": "q", "op": "gt",
        "threshold": 100.0, "summary": "s", "severity": "warning",
    }
    detector.reset_state()
    for val in [0.1, 0.11, 0.09, 0.1, 0.12]:
        prom.query.return_value = [(val, {"service_name": "storefront"})]
        detector.eval_metric_rule(rule, prom)

    prom.query.return_value = [(5.0, {"service_name": "storefront"})]
    alerts = detector.eval_metric_rule(rule, prom)
    assert len(alerts) == 1, "spike phai van keu"
    assert "5.0000" in field_values(alerts[0]), "alert phai bao gia tri THAT, khong phai gia tri da kep"
    assert max(detector.metric_history["latency-test:storefront"]) < 5.0, "history phai luu gia tri DA KEP"


def test_dynamic_disabled_rule_is_untouched_by_winsorize():
    """Rule tat tang dong khong ghi history, nen khong co gi de kep."""
    prom = MagicMock()
    rule = _collapse_rule()
    for val in (1.0, 1.0, 0.9, 1.0, 1.0, 0.05):
        prom.query.return_value = [(val, {"service_name": "payment"})]
        detector.eval_metric_rule(rule, prom)
    assert detector.metric_history == {}
