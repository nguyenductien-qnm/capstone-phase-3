"""Unit tests for the pure scoring logic in incident_replay.py — the part
MANDATE-15 requires to be readable/open ("logic cham phai mo de mentor soi").
Harness introduced for MANDATE-07 #7b, reused here for MANDATE-15's masking/
healthy-load scenarios (see aiops/incident_scenarios/README.md). No live
Prometheus/K8s/flagd needed: score_events/verdict_for_type/check_remediation
only read a JSONL file and compare timestamps.

Run:
    pytest aiops/test_incident_replay.py -v
"""
import glob
import json
import os

import incident_replay as ir

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incident_scenarios")


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_score_events_real_incident_caught_with_lead_time(tmp_path):
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1000.0, "rule_id": "grpc-error-rate-high", "service": "checkout"},
    ])
    events = [{
        "label": "incident", "service": "checkout",
        "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
        "t_start": 980.0, "t_end": 1040.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=10)
    pe = score["per_event"][0]
    assert pe["fired"] is True
    assert pe["lead_time_seconds"] == 20.0
    assert score["metrics"]["recall"] == 1.0
    assert score["metrics"]["precision"] == 1.0


def test_score_events_missed_incident_recall_zero(tmp_path):
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [])  # detector never fired
    events = [{
        "label": "incident", "service": "checkout",
        "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
        "t_start": 980.0, "t_end": 1040.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=10)
    assert score["per_event"][0]["fired"] is False
    assert score["metrics"]["recall"] == 0.0
    assert score["metrics"]["precision"] is None  # no fires at all -> undefined, not 0


def test_score_events_ignores_alert_before_incident_start(tmp_path):
    """An alert that fired BEFORE t_start belongs to a prior/unrelated window,
    not to this incident — must not count as a match."""
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 900.0, "rule_id": "grpc-error-rate-high", "service": "checkout"},
    ])
    events = [{
        "label": "incident", "service": "checkout",
        "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
        "t_start": 980.0, "t_end": 1040.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=10)
    assert score["per_event"][0]["fired"] is False


def test_score_events_precision_penalizes_extra_unrelated_fires(tmp_path):
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1000.0, "rule_id": "grpc-error-rate-high", "service": "checkout"},
        {"ts": 1010.0, "rule_id": "latency-p95-high", "service": "cart"},  # unrelated FP
    ])
    events = [{
        "label": "incident", "service": "checkout",
        "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
        "t_start": 980.0, "t_end": 1040.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=10)
    assert score["metrics"]["total_fires_observed"] == 2
    assert score["metrics"]["correct_fires"] == 1
    assert score["metrics"]["precision"] == 0.5


def test_verdict_masking_case_fails_when_second_event_not_caught():
    per_event = [
        {"label": "noise-spike", "expect_fire": True, "fired": True},
        {"label": "subtle-incident", "expect_fire": True, "fired": False},
    ]
    ok, reason = ir.verdict_for_type("masking", per_event)
    assert ok is False
    assert "subtle-incident" in reason


def test_verdict_masking_case_passes_when_both_caught():
    per_event = [
        {"label": "noise-spike", "expect_fire": True, "fired": True},
        {"label": "subtle-incident", "expect_fire": True, "fired": True},
    ]
    ok, _ = ir.verdict_for_type("masking", per_event)
    assert ok is True


def test_verdict_healthy_load_fails_on_false_positive():
    per_event = [{"label": "load-only", "expect_fire": False, "fired": True}]
    ok, reason = ir.verdict_for_type("healthy_load", per_event)
    assert ok is False
    assert "load-only" in reason


def test_verdict_healthy_load_passes_when_silent():
    per_event = [{"label": "load-only", "expect_fire": False, "fired": False}]
    ok, _ = ir.verdict_for_type("healthy_load", per_event)
    assert ok is True


def test_verdict_real_incident_passes_when_fired():
    per_event = [{"label": "incident", "expect_fire": True, "fired": True}]
    ok, _ = ir.verdict_for_type("real", per_event)
    assert ok is True


def test_normalize_events_healthy_load_watches_monitored_rule_ids():
    """expected_rule_ids is empty on purpose for a healthy_load scenario
    (nothing SHOULD fire) — monitored_rule_ids is what we actually match
    against to detect a false positive (MANDATE-15)."""
    scenario = {
        "id": "case-healthy-load-001", "type": "healthy_load", "service": "frontend",
        "expected_rule_ids": [], "monitored_rule_ids": ["latency-p95-high"],
        "expect_fire": False, "duration_seconds": 10,
    }
    events = ir._normalize_events(scenario)
    assert events[0]["expected_rule_ids"] == ["latency-p95-high"]


def test_healthy_load_scenario_end_to_end_false_positive_detected(tmp_path):
    """A latency-p95-high alert firing for frontend during a 'healthy load'
    window must be scored as a false positive -> verdict FAIL."""
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1050.0, "rule_id": "latency-p95-high", "service": "frontend"},
    ])
    scenario = {
        "id": "case-healthy-load-001", "type": "healthy_load", "service": "frontend",
        "expected_rule_ids": [], "monitored_rule_ids": ["latency-p95-high"],
        "expect_fire": False, "duration_seconds": 100, "settle_seconds": 10,
    }
    events = ir._normalize_events(scenario)
    events[0]["t_start"] = 1000.0
    events[0]["t_end"] = 1100.0
    score = ir.score_events(events, str(history), settle_seconds=10)
    ok, reason = ir.verdict_for_type("healthy_load", score["per_event"])
    assert ok is False
    assert "case-healthy-load-001" in reason


def test_committed_scenario_files_parse_and_normalize():
    """Every committed labeled-incident-set file must at least be
    well-formed and produce events with the fields score_events() needs."""
    files = glob.glob(os.path.join(SCENARIOS_DIR, "*.json"))
    assert len(files) >= 3
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            scenario = json.load(f)
        assert scenario["type"] in ("real", "masking", "healthy_load")
        events = ir._normalize_events(scenario)
        assert len(events) >= 1
        for ev in events:
            assert "expect_fire" in ev
            assert isinstance(ev.get("expected_rule_ids"), list)
            assert ev.get("inject") is not None


def test_check_remediation_filters_to_window(tmp_path):
    audit = tmp_path / "audit_log.jsonl"
    _write_jsonl(audit, [
        {"ts": 500.0, "outcome": "dry_run"},
        {"ts": 1000.0, "outcome": "verified_pass"},
        {"ts": 2000.0, "outcome": "verified_pass"},
    ])
    records = ir.check_remediation(str(audit), window_start=900.0, window_end=1500.0)
    assert len(records) == 1
    assert records[0]["outcome"] == "verified_pass"
