"""
test_validate_rules.py — Unit tests cho validate_rules.py.

Moi test o day ung voi mot LOI THAT da xay ra hoac mot lop loi da do duoc, khong
phai bai tap schema chung chung. Test quan trong nhat la
`test_the_real_rules_yaml_is_valid`: no bien rules.yaml dang chay thanh mot phan
cua bo test, viec chua tung co truoc day.

Run:
    pytest test_validate_rules.py -v
"""
import shutil

import pytest
import yaml

import validate_rules as vr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _metric_rule(**over):
    """Mot metric rule hop le toi thieu; ghi de bang keyword."""
    rule = {
        "id": "test-rule",
        "type": "metric",
        "severity": "warning",
        "summary": "test",
        "query": "up",
        "threshold": 1.0,
    }
    rule.update(over)
    return rule


def _config(*rules):
    """Bao cac rule vao mot cfg top-level hop le."""
    return {
        "poll_interval_seconds": 30,
        "sources": {"prometheus_url_env": "PROM_URL"},
        "alert": {"provider": "stdout"},
        "rules": list(rules),
    }


def _run(cfg):
    """Chay validate_config, tra ve (errors, warnings)."""
    errors, warnings = [], []
    vr.validate_config(cfg, errors, warnings)
    return errors, warnings


def _joined(items):
    return " | ".join(items)


# ---------------------------------------------------------------------------
# Truong go sai — ly do chinh cua ca script
# ---------------------------------------------------------------------------
def test_typo_in_field_name_is_an_error():
    """`dynamic_min_fration` thieu chu 'c'.

    Day dung la lop loi nguy hiem nhat: `rule.get("dynamic_min_fraction")` tra None,
    cong SLO khong bao gio ap, va rule van chay binh thuong — khong log, khong bao,
    khong dau hieu gi cho thay cau hinh vua viet ra da chet.
    """
    errors, _ = _run(_config(_metric_rule(dynamic_min_fration=0.5)))
    assert any("dynamic_min_fration" in e for e in errors), _joined(errors)


def test_field_valid_for_another_type_is_a_warning_not_an_error():
    """`match_phrases` tren rule k8s_status.

    Rule `oom-detected` that lam dung the nay va CO Y: doi tu log-based sang
    k8s_status roi giu lai match_phrases lam tai lieu, co ghi ly do trong comment
    (rules.yaml). Bao loi o day se bat nguoi ta xoa mot ghi chu co ich.
    """
    rule = {
        "id": "oom-like",
        "type": "k8s_status",
        "severity": "critical",
        "summary": "test",
        "match_phrases": ["OOMKilled"],
    }
    errors, warnings = _run(_config(rule))
    assert errors == []
    assert any("match_phrases" in w for w in warnings), _joined(warnings)


def test_strict_mode_turns_that_warning_into_an_error():
    """--strict cho ai muon xiet; mac dinh thi khong."""
    rule = {
        "id": "oom-like",
        "type": "k8s_status",
        "severity": "critical",
        "summary": "test",
        "match_phrases": ["OOMKilled"],
    }
    errors, warnings = _run(_config(rule))
    assert errors == [] and warnings != []


# ---------------------------------------------------------------------------
# op — nhanh else am tham dao chieu rule
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_op", ["GT", ">", "greater", "gte"])
def test_invalid_op_is_an_error(bad_op):
    """detector.py:87 la `value > threshold if op == "gt" else value < threshold`.

    Nghia la MOI gia tri khac dung chuoi "gt" deu roi vao nhanh else va chay thanh
    "lt" — rule bi dao chieu hoan toan ma khong bao gi.
    """
    errors, _ = _run(_config(_metric_rule(op=bad_op)))
    assert any("op" in e for e in errors), _joined(errors)


def test_valid_ops_pass():
    for op in ("gt", "lt"):
        errors, _ = _run(_config(_metric_rule(op=op)))
        assert errors == [], f"op={op}: {_joined(errors)}"


def test_op_defaults_to_gt_when_absent():
    errors, _ = _run(_config(_metric_rule()))
    assert errors == [], _joined(errors)


def test_lt_with_dynamic_min_fraction_is_an_error():
    """Cong SLO CHI ap cho nhanh gt (detector.py:109-115).

    Dat dynamic_min_fraction tren mot rule op=lt khong sai cu phap, no chi khong co
    tac dung nao — dung kieu cau hinh chet im lang ma script nay sinh ra de chan.
    """
    errors, _ = _run(_config(_metric_rule(op="lt", dynamic_min_fraction=0.2)))
    assert any("dynamic_min_fraction" in e for e in errors), _joined(errors)


# ---------------------------------------------------------------------------
# id trung — dung chung baseline va cooldown
# ---------------------------------------------------------------------------
def test_duplicate_rule_id_is_an_error():
    """`history_key` va `dedup_key` deu la f"{rule['id']}:{svc}".

    Hai rule trung id se dung chung cua so 3-sigma va dung chung cooldown 600s:
    rule sau nuot bao dong cua rule truoc.
    """
    errors, _ = _run(_config(_metric_rule(), _metric_rule(query="up{job='x'}")))
    assert any("trung" in e for e in errors), _joined(errors)


# ---------------------------------------------------------------------------
# Truong bat buoc / kieu du lieu
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["id", "type", "severity", "summary"])
def test_missing_common_required_field_is_an_error(missing):
    rule = _metric_rule()
    del rule[missing]
    errors, _ = _run(_config(rule))
    assert any(missing in e for e in errors), _joined(errors)


@pytest.mark.parametrize("missing", ["query", "threshold"])
def test_metric_rule_missing_its_own_required_field_is_an_error(missing):
    rule = _metric_rule()
    del rule[missing]
    errors, _ = _run(_config(rule))
    assert any(missing in e for e in errors), _joined(errors)


def test_threshold_must_be_a_number():
    errors, _ = _run(_config(_metric_rule(threshold="1.0")))
    assert any("threshold" in e for e in errors), _joined(errors)


def test_unknown_rule_type_is_an_error():
    """run_cycle chi log warning roi continue — rule bi bo qua hoan toan, im lang."""
    errors, _ = _run(_config(_metric_rule(type="metrics")))
    assert any("metrics" in e for e in errors), _joined(errors)


def test_log_rule_without_match_phrases_is_an_error():
    rule = {"id": "l", "type": "log", "severity": "warning", "summary": "s"}
    errors, _ = _run(_config(rule))
    assert any("match_phrase" in e for e in errors), _joined(errors)


def test_log_rule_with_match_phrase_singular_passes():
    """detector.py:163 doc `match_phrases` HOAC `match_phrase` — chap nhan ca hai."""
    rule = {
        "id": "l",
        "type": "log",
        "severity": "warning",
        "summary": "s",
        "match_phrase": "boom",
    }
    errors, _ = _run(_config(rule))
    assert errors == [], _joined(errors)


@pytest.mark.parametrize("frac,reason", [(0, "cong luon mo"), (-1, "am"), (1.5, "> 1")])
def test_dynamic_min_fraction_out_of_range_is_an_error(frac, reason):
    errors, _ = _run(_config(_metric_rule(dynamic_min_fraction=frac)))
    assert any("dynamic_min_fraction" in e for e in errors), f"{reason}: {_joined(errors)}"


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def test_missing_rules_key_is_an_error():
    cfg = _config()
    del cfg["rules"]
    errors, _ = _run(cfg)
    assert any("rules" in e for e in errors), _joined(errors)


def test_empty_rules_list_is_an_error():
    """Detector chay binh thuong voi 0 rule va khong canh gi ca — im lang tuyet doi."""
    errors, _ = _run(_config())
    assert any("rong" in e for e in errors), _joined(errors)


@pytest.mark.parametrize("bad", [0, -5, "30"])
def test_bad_poll_interval_is_an_error(bad):
    cfg = _config(_metric_rule())
    cfg["poll_interval_seconds"] = bad
    errors, _ = _run(cfg)
    assert any("poll_interval_seconds" in e for e in errors), _joined(errors)


def test_valid_minimal_config_is_clean():
    errors, warnings = _run(_config(_metric_rule()))
    assert errors == [] and warnings == []


# ---------------------------------------------------------------------------
# PromQL — can promtool
# ---------------------------------------------------------------------------
requires_promtool = pytest.mark.skipif(
    shutil.which("promtool") is None, reason="can promtool tren PATH"
)


@requires_promtool
def test_broken_promql_is_an_error():
    errors = []
    vr.check_promql([("bad-rule", "sum by (service_name) (rate(")], errors)
    assert any("bad-rule" in e for e in errors), _joined(errors)


@requires_promtool
def test_valid_promql_passes():
    errors = []
    ok = vr.check_promql(
        [("good", 'sum by (service_name) (rate(http_requests_total{job="x"}[5m]))')],
        errors,
    )
    assert ok and errors == [], _joined(errors)


@requires_promtool
def test_wrong_metric_name_is_NOT_caught():
    """Gioi han cua script, khang dinh bang test chu khong chi bang tai lieu.

    `kafka_consumer_group_lag` la PromQL hop le hoan toan — no chi tinh co khong khop
    chuoi nao tren cum. Chinh vi the rule kafka nam cam hang tuan ma khong ai biet.
    Bat duoc no can Prometheus that, viec cua `detector.py --once` va co che detector
    tu to cao rule cam. Test nay ton tai de khong ai tuong script nay lam duoc dieu do.
    """
    errors = []
    vr.check_promql(
        [("kafka", 'max by (group) (avg_over_time(kafka_consumer_group_lag{namespace="techx-tf1"}[10m]))')],
        errors,
    )
    assert errors == []


# ---------------------------------------------------------------------------
# File that dang chay
# ---------------------------------------------------------------------------
def test_the_real_rules_yaml_is_valid():
    """rules.yaml dang chay tren cum phai pass.

    Truoc day KHONG mot test nao load rules.yaml (`load_config` chua tung duoc test
    cham toi), nen mot loi go trong file di thang ra production. Test nay dong lo do.
    """
    with open(vr.DEFAULT_RULES, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    errors, _ = _run(cfg)
    assert errors == [], _joined(errors)


@requires_promtool
def test_every_query_in_the_real_rules_yaml_parses():
    with open(vr.DEFAULT_RULES, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    errors, warnings = [], []
    queries = vr.validate_config(cfg, errors, warnings)
    assert queries, "khong tim thay metric rule nao — validate_config co the da hong"
    promql_errors = []
    vr.check_promql(queries, promql_errors)
    assert promql_errors == [], _joined(promql_errors)
