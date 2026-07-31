import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from blast_radius import BlastRadiusGuard
from circuit_breaker import CircuitBreaker
import remediation


# ---------- Helpers de gia lap object cua Kubernetes python client ----------

def make_pod(name, labels, oomkilled=False, ready=True, finished_at=None):
    container_status = SimpleNamespace(
        name="main",
        last_state=SimpleNamespace(
            terminated=SimpleNamespace(reason="OOMKilled", finished_at=finished_at or SimpleNamespace(timestamp=lambda: time.time()))
            if oomkilled else None
        ),
    )
    condition = SimpleNamespace(type="Ready", status="True" if ready else "False")
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, labels=labels),
        status=SimpleNamespace(container_statuses=[container_status], conditions=[condition]),
    )


def pod_list(pods):
    return SimpleNamespace(items=pods)


# ---------- Unit test: BlastRadiusGuard doc lap ----------

def test_blast_radius_allows_first_blocks_second_same_scope():
    guard = BlastRadiusGuard(max_actions=1, time_window_seconds=3600)
    assert guard.allow("techx-tf1") is True
    guard.record("techx-tf1")
    assert guard.allow("techx-tf1") is False


def test_blast_radius_different_scope_independent():
    guard = BlastRadiusGuard(max_actions=1, time_window_seconds=3600)
    guard.record("ns-a")
    assert guard.allow("ns-a") is False
    assert guard.allow("ns-b") is True


def test_blast_radius_window_expires():
    guard = BlastRadiusGuard(max_actions=1, time_window_seconds=1)
    guard.record("techx-tf1")
    assert guard.allow("techx-tf1") is False
    time.sleep(1.1)
    assert guard.allow("techx-tf1") is True


# ---------- Unit test: CircuitBreaker doc lap ----------

def test_circuit_breaker_opens_after_max_consecutive_failures():
    cb = CircuitBreaker(max_consecutive_failures=3, reset_timeout_seconds=86400)
    assert cb.is_open("svc") is False
    assert cb.record_failure("svc") is False  # 1
    assert cb.record_failure("svc") is False  # 2
    just_opened = cb.record_failure("svc")    # 3 -> mo
    assert just_opened is True
    assert cb.is_open("svc") is True


def test_circuit_breaker_success_resets_failure_count():
    cb = CircuitBreaker(max_consecutive_failures=3, reset_timeout_seconds=86400)
    cb.record_failure("svc")
    cb.record_failure("svc")
    cb.record_success("svc")
    cb.record_failure("svc")
    cb.record_failure("svc")
    assert cb.is_open("svc") is False  # chi 2 fail lien tiep sau khi reset, chua toi 3


def test_circuit_breaker_reopens_after_reset_timeout():
    cb = CircuitBreaker(max_consecutive_failures=1, reset_timeout_seconds=1)
    cb.record_failure("svc")
    assert cb.is_open("svc") is True
    time.sleep(1.1)
    assert cb.is_open("svc") is False  # tu dong dong lai sau reset_timeout


# ---------- Integration test: process_oom_policy voi K8s/Prometheus/OpenSearch mock ----------

RULE = {
    "id": "oom-detected",
    "type": "log",
    "match_phrases": ["OutOfMemory", "OOMKilled"],
    "window_minutes": 5,
    "min_count": 1,
}

POLICY = {
    "rule_id": "oom-detected",
    "trigger": {"type": "k8s_pod_status", "lookback_seconds": 300},
    "action": {"type": "k8s_restart_pod", "grace_period_seconds": 30, "require_readiness_gate": True},
    "safety_boundaries": {
        "dry_run": True,
        "error_budget_check": {"enabled": True, "query": "dummy", "max_ratio": 0.005},
        "blast_radius": {"max_actions": 1, "time_window_seconds": 3600, "scope": "namespace"},
        "verify": {"duration_seconds": 1, "poll_interval_seconds": 1},
        "circuit_breaker": {"max_consecutive_failures": 3, "reset_timeout_seconds": 86400},
    },
}

CFG = {"k8s": {"namespace": "techx-tf1", "service_label_key": "opentelemetry.io/name"}}


def _mocks(oom_pods_found=True, error_budget_ok=True):
    prom = MagicMock()
    prom.query.return_value = [] if error_budget_ok else [(0.9, {})]
    osc = MagicMock()
    osc.count_matches.return_value = (2, "OOMKilled sample log")
    core_v1 = MagicMock()
    pods = [make_pod("email-abc123", {"opentelemetry.io/name": "email"}, oomkilled=True)] if oom_pods_found else []
    core_v1.list_namespaced_pod.return_value = pod_list(pods)
    alerter = MagicMock()
    alerter.send.return_value = True
    return prom, osc, core_v1, alerter


def test_dry_run_never_calls_k8s_delete():
    prom, osc, core_v1, alerter = _mocks()
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=True)

    core_v1.delete_namespaced_pod.assert_not_called()
    assert alerter.send.called
    # Alert dry-run phai duoc gui voi title "remediation-dry-run:..."
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("dry-run" in t for t in sent_titles)


def test_k8s_pod_status_trigger_acts_even_with_zero_log_matches():
    """Tai hien DUNG phat hien chaos test that 17/07: OOM dot ngot khien app bi
    SIGKILL truoc khi kip ghi log ve cai chet cua chinh no -> OpenSearch tra ve 0 hit
    (giong het thuc te), nhung K8s API van xac nhan OOMKilled that -> voi
    trigger.type=k8s_pod_status, remediation VAN PHAI hanh dong (dry-run o day, chi
    can xac nhan KHONG bi chan boi log rong)."""
    prom, osc, core_v1, alerter = _mocks()
    osc.count_matches.return_value = (0, None)  # dung nhu thuc te - khong co log nao
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=True)

    assert alerter.send.called, "phai van hanh dong (dry-run alert) du log_count=0"
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("dry-run" in t for t in sent_titles)


def test_opensearch_log_trigger_still_gates_on_log_count():
    """Doi chung: policy dung trigger.type=opensearch_log (mac dinh/hanh vi cu) thi
    log_count=0 PHAI chan hanh dong - khong pha vo rule nao khac dang dung kieu cu."""
    prom, osc, core_v1, alerter = _mocks()
    osc.count_matches.return_value = (0, None)
    policy_log_trigger = {**POLICY, "trigger": {"type": "opensearch_log"}}
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(policy_log_trigger, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=True)

    alerter.send.assert_not_called()
    core_v1.delete_namespaced_pod.assert_not_called()


def test_no_action_when_no_real_oom_pod_found():
    """Rule OpenSearch keu (count>=min_count) nhung K8s khong xac nhan pod OOM that ->
    khong lam gi (tranh hanh dong dua tren log da cu/sai)."""
    prom, osc, core_v1, alerter = _mocks(oom_pods_found=False)
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_not_called()
    alerter.send.assert_not_called()


def test_blast_radius_blocks_when_already_consumed():
    prom, osc, core_v1, alerter = _mocks()
    blast_guard = BlastRadiusGuard(1, 3600)
    blast_guard.record("techx-tf1")  # da dung het quota
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_not_called()
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("blast-radius" in t for t in sent_titles)


def test_error_budget_depleted_halts_automation():
    prom, osc, core_v1, alerter = _mocks(error_budget_ok=False)
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_not_called()
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("halt-error-budget" in t for t in sent_titles)


def test_circuit_breaker_already_open_skips_and_escalates():
    prom, osc, core_v1, alerter = _mocks()
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(1, 86400)
    breaker.record_failure("oom-detected:email")  # 1 fail = mo (max_consecutive_failures=1)
    assert breaker.is_open("oom-detected:email") is True

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_not_called()
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("circuit-breaker-open" in t for t in sent_titles)


@patch("remediation.verify_oom_recovery")
def test_verify_pass_audit(mock_verify, audit_file):
    mock_verify.return_value = True
    prom, osc, core_v1, alerter = _mocks()
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_called_once()
    assert breaker.is_open("oom-detected:email") is False
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("remediation-verified" in t for t in sent_titles)
    records = _read_audit(audit_file)
    verified = [r for r in records if r["stage"] == audit.STAGE_VERIFY]
    rollback = [r for r in records if r["stage"] == audit.STAGE_ROLLBACK]
    assert len(verified) == 1
    assert verified[0]["decision"] == "pass"
    assert len(rollback) == 1
    assert rollback[0]["decision"] == "not_required"
    assert rollback[0]["rollback_performed"] is False


@patch("remediation.verify_oom_recovery")
def test_verify_failure_has_no_fake_rollback(mock_verify):
    """Verify fail -> chi tang circuit breaker + escalate, KHONG co lenh K8s/flagd/helm
    nao khac duoc goi ngoai restart_pod ban dau (rollback = dung lai, khong phai hanh
    dong hoan tac gia)."""
    mock_verify.return_value = False
    prom, osc, core_v1, alerter = _mocks()
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_called_once()  # chi 1 lan restart, khong retry tu dong
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("verify-failed" in t for t in sent_titles)
    # Khong co method nao cua core_v1 khac ngoai list_namespaced_pod/delete_namespaced_pod
    # duoc goi (vd khong co "patch"/"replace" nao gia lam rollback).
    called_methods = {c[0] for c in core_v1.method_calls}
    assert called_methods <= {"list_namespaced_pod", "delete_namespaced_pod"}


def test_remediation_excludes_flagd_and_helm():
    """Guard test tuong minh (bai hoc RULES.md Sec8): khong CODE nao (loai tru comment
    giai thich ly do tranh) trong aiops/remediation/ duoc phep doc/goi flagd hay helm
    rollback."""
    import pathlib
    remediation_dir = pathlib.Path(__file__).parent
    for py_file in remediation_dir.glob("*.py"):
        if py_file.name == "test_remediation.py":
            continue
        code_lines = [
            line for line in py_file.read_text(encoding="utf-8").lower().splitlines()
            if not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        assert "flagd" not in code_only, f"{py_file.name}: co code (khong phai comment) nhac flagd"
        assert "helm rollback" not in code_only, f"{py_file.name}: co code goi helm rollback"


# ---------------------------------------------------------------------------
# Audit log (TF1-112 / MANDATE-22)
#
# DoD cua MANDATE-22 doi "audit log lan do". Truoc TF1-112 remediation KHONG ghi
# lai gi: dau vet duy nhat la alert Slack + stdout cua pod, ma stdout mat sach khi
# pod restart. Nang hon, incident_replay.py DA mong doi aiops/remediation/audit_log.jsonl
# (DEFAULT_AUDIT_LOG, check_remediation()) nhung khong module nao ghi ra no.
# ---------------------------------------------------------------------------
import json as _json

import audit
import audit_report


@pytest.fixture(autouse=True)
def audit_file(tmp_path, monkeypatch):
    """Tro audit log sang tmp cho MOI test.

    autouse vi cac test cu cung goi process_oom_policy, ma ham do gio co ghi audit —
    khong co fixture nay thi chay bo test se ghi ban aiops/remediation/audit_log.jsonl
    vao repo.
    """
    path = tmp_path / "audit_log.jsonl"
    monkeypatch.setenv("REMEDIATION_AUDIT_FILE", str(path))
    return path


def _read_audit(path):
    if not path.exists():
        return []
    return [_json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_audit_records_all_gates(audit_file):
    """Khi vong tu dap KHONG hanh dong, cau hoi luon la "no bi chan o cong nao".
    Chi ghi ket qua cuoi thi khong tra loi duoc."""
    prom, osc, core_v1, alerter = _mocks()
    remediation.process_oom_policy(
        POLICY, RULE, CFG, prom, osc, core_v1, alerter,
        BlastRadiusGuard(1, 3600), CircuitBreaker(3, 86400), dry_run=True,
    )
    records = _read_audit(audit_file)
    stages = [r["stage"] for r in records]
    # Di het cac cong truoc do roi dung o dry-run.
    assert stages == [
        audit.STAGE_DETECT,
        audit.STAGE_CIRCUIT_BREAKER,
        audit.STAGE_ERROR_BUDGET,
        audit.STAGE_BLAST_RADIUS,
        audit.STAGE_DRY_RUN,
    ], stages
    # TF1-103: moi quyet dinh phai noi duoc ve CUNG mot lan remediation.
    assert len({r["remediation_id"] for r in records}) == 1
    assert len({r["event_id"] for r in records}) == len(records)
    assert all(r["schema_version"] == audit.SCHEMA_VERSION for r in records)
    assert all(r["ts_utc"].endswith("+00:00") for r in records)


def test_audit_records_blocking_gate(audit_file):
    """Blast radius het han muc -> phai truy duoc chinh xac cong do tu choi."""
    prom, osc, core_v1, alerter = _mocks()
    guard = BlastRadiusGuard(1, 3600)
    guard.record("techx-tf1")  # tieu het han muc truoc
    remediation.process_oom_policy(
        POLICY, RULE, CFG, prom, osc, core_v1, alerter,
        guard, CircuitBreaker(3, 86400), dry_run=False,
    )
    records = _read_audit(audit_file)
    denied = [r for r in records if r["decision"] == "deny"]
    assert len(denied) == 1
    assert denied[0]["stage"] == audit.STAGE_BLAST_RADIUS
    assert denied[0]["max_actions"] == 1
    assert denied[0]["scope_key"] == "techx-tf1"
    # Khong duoc di tiep sang hanh dong.
    assert not [r for r in records if r["stage"] == audit.STAGE_ACTION]


@patch("remediation.verify_oom_recovery", return_value=False)
def test_verify_failure_audit(_mock_verify, audit_file):
    prom, osc, core_v1, alerter = _mocks()
    remediation.process_oom_policy(
        POLICY, RULE, CFG, prom, osc, core_v1, alerter,
        BlastRadiusGuard(1, 3600), CircuitBreaker(3, 86400), dry_run=False,
    )
    records = _read_audit(audit_file)
    acted = [r for r in records if r["stage"] == audit.STAGE_ACTION]
    assert len(acted) == 1
    assert acted[0]["decision"] == "acted"
    assert acted[0]["action"] == "k8s_restart_pod"
    assert acted[0]["dry_run"] is False
    assert acted[0]["pod"] == "email-abc123"

    verified = [r for r in records if r["stage"] == audit.STAGE_VERIFY]
    assert len(verified) == 1
    assert verified[0]["decision"] == "fail"
    assert "elapsed_seconds" in verified[0]

    rollback = [r for r in records if r["stage"] == audit.STAGE_ROLLBACK]
    assert len(rollback) == 1
    assert rollback[0]["decision"] == "not_available"
    assert rollback[0]["rollback_performed"] is False

    escalated = [r for r in records if r["stage"] == audit.STAGE_ESCALATE]
    assert len(escalated) == 1
    assert escalated[0]["decision"] == "sent"

    # Trigger -> action -> verify -> rollback/escalate phai la MOT chuoi truy duoc.
    assert len({r["remediation_id"] for r in records}) == 1


@patch("remediation.verify_oom_recovery", return_value=False)
def test_audit_records_open_breaker(_mock_verify, audit_file):
    """Vet quan trong nhat cua ca "rollback": breaker mo -> tu choi tu dong tu do."""
    prom, osc, core_v1, alerter = _mocks()
    breaker = CircuitBreaker(1, 86400)  # mo ngay sau 1 fail cho gon test
    remediation.process_oom_policy(
        POLICY, RULE, CFG, prom, osc, core_v1, alerter,
        BlastRadiusGuard(5, 3600), breaker, dry_run=False,
    )
    opened = [r for r in _read_audit(audit_file) if r["decision"] == "opened"]
    assert len(opened) == 1
    assert opened[0]["stage"] == audit.STAGE_CIRCUIT_BREAKER
    assert opened[0]["reset_timeout_seconds"] == 86400


def test_audit_failure_keeps_loop_running(monkeypatch, capsys):
    """Audit la thu yeu so voi viec dap su co. Dia day / mount read-only thi log
    warning roi di tiep, KHONG duoc nem exception lam sap tien trinh remediation."""
    monkeypatch.setenv("REMEDIATION_AUDIT_FILE", "/khong/ton/tai/audit.jsonl")
    assert audit.record(audit.STAGE_ACTION, "acted", "oom-detected", "email", "pod-1", False) is None

    prom, osc, core_v1, alerter = _mocks()
    # Khong duoc nem exception du audit ghi hong.
    remediation.process_oom_policy(
        POLICY, RULE, CFG, prom, osc, core_v1, alerter,
        BlastRadiusGuard(1, 3600), CircuitBreaker(3, 86400), dry_run=True,
    )
    alerter.send.assert_called()  # van chay het duong di binh thuong


def test_audit_path_matches_replay(monkeypatch):
    """incident_replay.py da tro san vao aiops/remediation/audit_log.jsonl tu truoc.
    Neu doi ten mac dinh o day thi ca duong cham diem remediation cua harness chet im."""
    import pathlib
    monkeypatch.delenv("REMEDIATION_AUDIT_FILE", raising=False)
    expected = pathlib.Path(__file__).parent / "audit_log.jsonl"
    assert pathlib.Path(audit.audit_path()) == expected


def test_report_shows_no_rollback():
    records = [
        {
            "schema_version": 1, "event_id": "evt-1", "remediation_id": "rem-1",
            "ts": 1.0, "ts_utc": "2026-07-31T00:00:01+00:00",
            "stage": "detect", "decision": "detected", "rule_id": "oom-detected",
            "service": "email", "pod": "email-1", "dry_run": False,
        },
        {
            "schema_version": 1, "event_id": "evt-2", "remediation_id": "rem-1",
            "ts": 2.0, "ts_utc": "2026-07-31T00:00:02+00:00",
            "stage": "action", "decision": "acted", "rule_id": "oom-detected",
            "service": "email", "pod": "email-1", "dry_run": False,
            "action": "k8s_restart_pod",
        },
        {
            "schema_version": 1, "event_id": "evt-3", "remediation_id": "rem-1",
            "ts": 3.0, "ts_utc": "2026-07-31T00:00:03+00:00",
            "stage": "verify", "decision": "fail", "rule_id": "oom-detected",
            "service": "email", "pod": "email-1", "dry_run": False,
        },
        {
            "schema_version": 1, "event_id": "evt-4", "remediation_id": "rem-1",
            "ts": 4.0, "ts_utc": "2026-07-31T00:00:04+00:00",
            "stage": "rollback", "decision": "not_available", "rule_id": "oom-detected",
            "service": "email", "pod": "email-1", "dry_run": False,
            "rollback_performed": False,
        },
        {
            "schema_version": 1, "event_id": "evt-5", "remediation_id": "rem-1",
            "ts": 5.0, "ts_utc": "2026-07-31T00:00:05+00:00",
            "stage": "escalate", "decision": "sent", "rule_id": "oom-detected",
            "service": "email", "pod": "email-1", "dry_run": False,
        },
    ]
    report = audit_report.render_markdown(
        records,
        source="test.jsonl",
        generated_at="2026-07-31T00:01:00+00:00",
    )
    assert "verify failed; escalated" in report
    assert "not performed (not_available)" in report
    assert "Attempt `rem-1`" in report
    assert "| `rollback` | `not_available` |" in report


def test_report_reads_legacy_audit():
    legacy = [
        {
            "ts": 1.0, "stage": "detect", "decision": "detected",
            "rule_id": "oom-detected", "service": "email", "pod": "email-1",
        },
        {
            "ts": 2.0, "stage": "dry_run", "decision": "skipped",
            "rule_id": "oom-detected", "service": "email", "pod": "email-1",
        },
    ]
    groups = audit_report.group_attempts(legacy)
    assert list(groups) == ["legacy-1"]
    assert audit_report.attempt_outcome(groups["legacy-1"]) == "dry-run only"


def test_audit_marks_failed_escalation(audit_file):
    prom, osc, core_v1, alerter = _mocks()
    alerter.send.return_value = False
    guard = BlastRadiusGuard(1, 3600)
    guard.record("techx-tf1")

    remediation.process_oom_policy(
        POLICY, RULE, CFG, prom, osc, core_v1, alerter,
        guard, CircuitBreaker(3, 86400), dry_run=False,
    )

    escalated = [
        record for record in _read_audit(audit_file)
        if record["stage"] == audit.STAGE_ESCALATE
    ]
    assert len(escalated) == 1
    assert escalated[0]["decision"] == "failed"


def test_report_rejects_invalid_jsonl(tmp_path):
    source = tmp_path / "broken.jsonl"
    source.write_text('{"stage":"detect"}\nnot-json\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"broken\.jsonl:2: invalid JSONL"):
        audit_report.load_jsonl(source)


def test_dockerfile_copies_all_modules():
    """Dockerfile liet ke TUNG FILE thay vi COPY ca thu muc.

    Loi that 28/07 (TF1-112): them audit.py vao remediation/ nhung quen them vao
    Dockerfile -> image thieu file -> pod CrashLoopBackOff voi "ModuleNotFoundError:
    No module named 'audit'" NGAY tren cum. CI khong bat duoc vi test chay tren
    source tree, con image lai thieu file.

    Test nay dong lo do: moi file .py trong remediation/ (tru test) phai xuat hien
    trong Dockerfile.
    """
    import pathlib
    here = pathlib.Path(__file__).parent

    # Chi doc cac dong COPY, KHONG doc ca file: comment trong Dockerfile co nhac ten
    # file (vd giai thich chinh su co nay) se lam phep kiem "ten co trong file khong"
    # luon dung -> test vo dung. Da dinh dung bay do luc viet test nay.
    copy_lines = []
    continuation = False
    for raw in (here / "Dockerfile").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continuation = False
            continue
        if line.upper().startswith("COPY ") or continuation:
            copy_lines.append(line)
            continuation = line.endswith("\\")
        else:
            continuation = False
    copied = "\n".join(copy_lines)

    missing = [
        py.name for py in sorted(here.glob("*.py"))
        if py.name != "test_remediation.py" and py.name not in copied
    ]
    assert not missing, (
        "module co trong remediation/ nhung KHONG duoc COPY trong Dockerfile -> "
        "pod se CrashLoopBackOff voi ModuleNotFoundError: " + ", ".join(missing)
    )
