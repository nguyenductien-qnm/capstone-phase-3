"""Unit tests for the pure scoring logic in incident_replay.py (MANDATE-07 #7b
precision/recall/lead-time harness — also reused by MANDATE-15/22, see
aiops/incident_scenarios/README.md). No live Prometheus/K8s/flagd needed:
score_events/verdict_for_type/check_remediation only read a JSONL file and
compare timestamps.

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


def test_alert_in_no_fire_window_is_not_counted_as_a_correct_fire(tmp_path):
    """An alert during a window that should stay silent is a false positive.

    It used to land in correct_fires because the watch set matched, which
    reported precision 1.0 for a window whose whole point was to catch
    over-alerting. Found when the #7b set-level numbers were recomputed.
    """
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1000.0, "rule_id": "grpc-error-rate-high", "service": "checkout"},
    ])
    events = [{
        "label": "quiet-window", "service": None,
        "expected_rule_ids": ["grpc-error-rate-high"],
        "expect_fire": False, "t_start": 900.0, "t_end": 1100.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=0)
    assert score["per_event"][0]["fired"] is True
    assert score["metrics"]["total_fires_observed"] == 1
    assert score["metrics"]["correct_fires"] == 0
    assert score["metrics"]["precision"] == 0.0


def test_event_does_not_steal_an_alert_from_a_later_event(tmp_path):
    """An alert outside an event's own window must not count as catching it.

    The candidate filter only had a lower bound, so in a multi-event scenario the
    earlier event matched any later alert too. Found scoring the MANDATE-15 EKS
    set: the payment case, for which the detector stayed silent, was reported as
    caught with lead_time=1166s because it grabbed the cart case's alert from 19
    minutes later. Matters most for the masking scenario, which is multi-event by
    construction.
    """
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 3000.0, "rule_id": "grpc-error-rate-high", "service": "checkout"},
    ])
    events = [
        {"label": "earlier-incident", "service": "checkout",
         "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
         "t_start": 1000.0, "t_end": 1100.0},
        {"label": "later-incident", "service": "checkout",
         "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
         "t_start": 2900.0, "t_end": 3100.0},
    ]
    score = ir.score_events(events, str(history), settle_seconds=30)
    earlier, later = score["per_event"]
    assert earlier["fired"] is False, "alert 1900s later is not this event's"
    assert later["fired"] is True
    assert score["metrics"]["recall"] == 0.5


def test_verdict_real_incident_passes_when_fired():
    per_event = [{"label": "incident", "expect_fire": True, "fired": True}]
    ok, _ = ir.verdict_for_type("real", per_event)
    assert ok is True


def test_committed_scenario_files_parse_and_normalize():
    """Every committed labeled-incident-set file must at least be
    well-formed and produce events with the fields score_events() needs.
    (monitored_rule_ids fallback for healthy_load-type scenarios is covered
    once that scenario type is introduced — see MANDATE-15 work.)"""
    # Skip <scenario>.result.json: those are outputs a live run drops next to
    # the scenario it scored, not scenarios, and globbing them in made this
    # test fail the moment anyone actually ran the harness.
    files = [p for p in glob.glob(os.path.join(SCENARIOS_DIR, "*.json"))
             if not p.endswith(".result.json")]
    assert len(files) >= 1
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            scenario = json.load(f)
        assert scenario["type"] in ("real", "masking", "healthy_load")
        events = ir._normalize_events(scenario)
        assert len(events) >= 1
        for ev in events:
            assert "expect_fire" in ev
            assert isinstance(ev.get("expected_rule_ids"), list)
            if ev.get("expect_fire"):
                # An event that must fire needs something to make it fire.
                # Observation-only windows (expect_fire False, e.g. the #7b
                # quiet-window baseline) deliberately carry no inject.
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


def test_self_report_alert_does_not_dilute_precision(tmp_path):
    """`detector-silent-rule` la detector tu bao cao ve CHINH NO, khong phai quan sat
    ve he thong dang duoc do.

    `total_fires = len(observed)` dem MOI alert trong cua so. Khong loc thi mot bao cao
    "rule X dang mu" roi dung vao cua so replay se keo tut precision, trong khi no khong
    noi len dieu gi ve viec detector bat su co chinh xac den dau. Khong lo duoc: co che
    tu bao cao ban dinh ky va cua so replay thi dai hang chuc phut.
    """
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1000.0, "rule_id": "grpc-error-rate-high", "service": "checkout"},
        {"ts": 1010.0, "rule_id": "detector-silent-rule", "service": "kafka-consumer-lag-high"},
    ])
    events = [{
        "label": "incident", "service": "checkout",
        "expected_rule_ids": ["grpc-error-rate-high"], "expect_fire": True,
        "t_start": 980.0, "t_end": 1040.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=10)
    assert score["metrics"]["recall"] == 1.0
    assert score["metrics"]["total_fires_observed"] == 1, (
        "bao cao tu-to-cao khong duoc tinh vao mau so cua precision"
    )
    assert score["metrics"]["precision"] == 1.0


def test_self_report_alert_cannot_satisfy_an_expected_incident(tmp_path):
    """Chan chieu nguoc lai: loc roi thi no cung khong the bi nham la mot phat hien dung."""
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1000.0, "rule_id": "detector-silent-rule", "service": "checkout"},
    ])
    events = [{
        "label": "incident", "service": "checkout",
        "expected_rule_ids": ["detector-silent-rule"], "expect_fire": True,
        "t_start": 980.0, "t_end": 1040.0,
    }]
    score = ir.score_events(events, str(history), settle_seconds=10)
    assert score["per_event"][0]["fired"] is False
    assert score["metrics"]["recall"] == 0.0


# ---------------------------------------------------------------------------
# TF1-104 — cua replay nhan kich ban NGOAI (MANDATE-22 directive #22)
#
# Hai loi duoi day deu duoc phat hien bang cach chay thu voi kich ban dat ngoai repo,
# va ca hai deu chi can vao NGAY CHAM chu khong phai luc phat trien.
# ---------------------------------------------------------------------------
def test_observed_window_is_split_per_event_not_shared(tmp_path):
    """Kich ban NHIEU su kien tu ngoai khong duoc de MOT alert khop cho TAT CA.

    Ban truoc gan cung mot cua so cho moi su kien, nen mot alert duy nhat thoa man
    ca hai -> ca masking bao PASS ke ca khi su co thu hai bi che hoan toan. Da xac
    nhan bang thuc nghiem: hai su kien cung tra ve lead_time=200.9s tu cung mot alert,
    verdict PASS trong khi correct=1/total=2.

    Dac biet nguy hiem vi bo kich ban an cua MANDATE-15 CO ca masking.
    """
    events = [
        {"label": "e1", "service": "checkout", "expected_rule_ids": ["r"],
         "expect_fire": True, "offset_seconds": 0, "duration_seconds": 60},
        {"label": "e2", "service": "checkout", "expected_rule_ids": ["r"],
         "expect_fire": True, "offset_seconds": 600, "duration_seconds": 60},
    ]
    ir._assign_observed_window(events, 1000.0, 1660.0)
    assert events[0]["t_end"] < events[1]["t_start"], (
        "hai su kien phai chiem hai khoang thoi gian ROI NHAU"
    )
    assert events[0]["t_start"] == 1000.0
    assert events[1]["t_end"] == 1660.0


def test_one_alert_cannot_satisfy_two_events_from_external_scenario(tmp_path):
    """Dang chay duoc cua khang dinh tren, qua ca duong cham diem that."""
    history = tmp_path / "alerter_history.jsonl"
    _write_jsonl(history, [
        {"ts": 1030.0, "rule_id": "r", "service": "checkout"},  # chi nam trong e1
    ])
    events = [
        {"label": "e1", "service": "checkout", "expected_rule_ids": ["r"],
         "expect_fire": True, "offset_seconds": 0, "duration_seconds": 60},
        {"label": "e2", "service": "checkout", "expected_rule_ids": ["r"],
         "expect_fire": True, "offset_seconds": 600, "duration_seconds": 60},
    ]
    ir._assign_observed_window(events, 1000.0, 1660.0)
    score = ir.score_events(events, str(history), settle_seconds=0)
    fired = [pe["fired"] for pe in score["per_event"]]
    assert fired == [True, False], f"chi su kien 1 duoc tinh la bat duoc, thuc te {fired}"
    ok, _ = ir.verdict_for_type("masking", score["per_event"])
    assert ok is False, "su co thu hai bi bo sot thi ca masking phai FAIL"


def test_single_event_external_scenario_uses_the_whole_window():
    """Ca mot su kien giu nguyen hanh vi cu — do la ca da chay dung tu truoc."""
    events = [{"label": "e", "service": "checkout", "expected_rule_ids": ["r"],
               "expect_fire": True, "offset_seconds": 0, "duration_seconds": 60}]
    ir._assign_observed_window(events, 1000.0, 1700.0)
    assert (events[0]["t_start"], events[0]["t_end"]) == (1000.0, 1700.0)


def test_identical_offsets_fall_back_to_shared_window_with_a_warning(capsys):
    """Khong tach duoc bang timeline thi phai NOI RA thay vi am tham cham sai."""
    events = [
        {"label": "e1", "expected_rule_ids": ["r"], "offset_seconds": 0, "duration_seconds": 60},
        {"label": "e2", "expected_rule_ids": ["r"], "offset_seconds": 0, "duration_seconds": 60},
    ]
    ir._assign_observed_window(events, 1000.0, 1660.0)
    assert "CANH BAO" in capsys.readouterr().err


def test_unknown_rule_id_in_external_scenario_is_warned_loudly(tmp_path, capsys):
    """Rule id sai khong gay loi gi ca — su kien chi bi cham la 'silent' -> FAIL,
    va khong dau hieu nao noi rang nguyen nhan la go sai ten chu khong phai detector mu.

    Dung lop loi da tra gia hai lan: rule kafka sai ten metric nam cam hang tuan, va
    lan doi ten grpc-error-rate-high -> service-error-rate-high lam 5 scenario cham sai.
    """
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - id: service-error-rate-high\n  - id: latency-p95-high\n",
                     encoding="utf-8")
    events = [{"label": "e", "expected_rule_ids": ["rule-go-sai"], "expect_fire": True}]
    unknown = ir.warn_unknown_rule_ids(events, str(rules))
    assert unknown == ["rule-go-sai"]
    err = capsys.readouterr().err
    assert "CANH BAO" in err and "rule-go-sai" in err


def test_known_rule_ids_are_not_warned(tmp_path, capsys):
    rules = tmp_path / "rules.yaml"
    rules.write_text("rules:\n  - id: service-error-rate-high\n", encoding="utf-8")
    events = [{"label": "e", "expected_rule_ids": ["service-error-rate-high"]}]
    assert ir.warn_unknown_rule_ids(events, str(rules)) == []
    assert "CANH BAO" not in capsys.readouterr().err


def test_missing_rules_yaml_does_not_break_scoring(tmp_path):
    """Kich ban ngoai co the duoc cham o may khong co repo day du — khong duoc no."""
    events = [{"label": "e", "expected_rule_ids": ["bat-ky"]}]
    assert ir.warn_unknown_rule_ids(events, str(tmp_path / "khong-ton-tai.yaml")) == []


def test_the_real_rules_yaml_is_readable_by_the_harness():
    """Bo doc dong don gian phai doc duoc rules.yaml that — neu dinh dang doi thi hong."""
    ids = ir.known_rule_ids()
    assert ids and "service-error-rate-high" in ids, f"doc duoc: {ids}"
