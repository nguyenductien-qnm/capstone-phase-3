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
def test_live_action_restarts_and_records_success_on_verify_pass(mock_verify):
    mock_verify.return_value = True
    prom, osc, core_v1, alerter = _mocks()
    blast_guard = BlastRadiusGuard(1, 3600)
    breaker = CircuitBreaker(3, 86400)

    remediation.process_oom_policy(POLICY, RULE, CFG, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run=False)

    core_v1.delete_namespaced_pod.assert_called_once()
    assert breaker.is_open("oom-detected:email") is False
    sent_titles = [call.args[2] for call in alerter.send.call_args_list]
    assert any("remediation-verified" in t for t in sent_titles)


@patch("remediation.verify_oom_recovery")
def test_live_action_verify_fail_records_failure_no_rollback_action(mock_verify):
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


def test_no_flagd_or_helm_reference_anywhere_in_remediation_module():
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
