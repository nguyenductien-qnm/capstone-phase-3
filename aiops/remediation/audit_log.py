#!/usr/bin/env python3
# MANDATE-22 (closed-loop mitigation) - "Audit log truy duoc: moi hanh dong tu dong
# ghi lai du de tai dung: ai/cai gi kich hoat, lam gi, ket qua verify, co lui khong."
#
# aiops/detector/alerter_history.jsonl (aiops/detector/alerter.py::_append_history)
# only stores {ts, rule_id, service, severity, fingerprint} for alert dedup/G7
# co-occurrence - it does NOT capture which action was taken, on which target, or
# the verify outcome. This module is the missing structured record, dedicated to
# aiops/remediation/ and written at every state transition in process_oom_policy
# (circuit-breaker-open-skip, error-budget-halt, blast-radius-blocked, dry-run,
# verify-pass, verify-fail-escalate).
import json
import logging
import os
import time

log = logging.getLogger("aiops.remediation.audit")

_DEFAULT_AUDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_log.jsonl")


def _audit_log_path():
    return os.environ.get("REMEDIATION_AUDIT_LOG_FILE", _DEFAULT_AUDIT_LOG)


def record(
    *,
    dedup_key,
    rule_id,
    service,
    namespace,
    outcome,
    dry_run=None,
    blast_radius_ok=None,
    error_budget_ok=None,
    circuit_breaker_open=None,
    action_type=None,
    action_target=None,
    verify_result=None,
    verify_duration_seconds=None,
    rollback_or_escalate=None,
    detail=None,
    ts=None,
):
    """Append one structured audit record and return it.

    Best-effort write, same contract as alerter._append_history: a logging
    failure must never break the remediation loop.

    outcome: one of "circuit_breaker_open_skip" | "error_budget_halt" |
        "blast_radius_blocked" | "dry_run" | "action_failed" |
        "verified_pass" | "verified_fail".
    rollback_or_escalate: "escalate" | "circuit_breaker_opened" | None.
    """
    entry = {
        "ts": ts if ts is not None else time.time(),
        "dedup_key": dedup_key,
        "trigger": {"rule_id": rule_id, "service": service, "namespace": namespace},
        "safety_check": {
            "dry_run": dry_run,
            "blast_radius_ok": blast_radius_ok,
            "error_budget_ok": error_budget_ok,
            "circuit_breaker_open": circuit_breaker_open,
        },
        "action": {"type": action_type, "target": action_target} if action_type else None,
        "verify": (
            {"result": verify_result, "duration_seconds": verify_duration_seconds}
            if verify_result is not None else None
        ),
        "rollback_or_escalate": rollback_or_escalate,
        "outcome": outcome,
        "detail": detail,
    }
    try:
        with open(_audit_log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("could not write remediation audit log: %s", exc)
    return entry
