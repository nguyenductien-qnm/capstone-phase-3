# TF1-112 [MANDATE-22] - Audit log co cau truc cho vong tu dap.
#
# VI SAO CAN FILE NAY
# Truoc day remediation khong ghi lai gi ca. Dau vet duy nhat cua mot hanh dong la
# (a) alert Slack/Discord va (b) stdout cua pod — ma stdout MAT SACH khi pod restart.
# Voi mot vong tu dong co quyen `delete pods` tren cum that thi do khong phai audit
# trail: khong tra lai duoc "luc 3 gio sang no da xoa pod nao, vi sao, va co qua het
# cac cong an toan khong".
#
# Nang hon: `incident_replay.py` DA mong doi file nay tu truoc (DEFAULT_AUDIT_LOG,
# check_remediation(), co --check-remediation) nhung khong module nao ghi ra no. Tuc
# ca duong cham diem remediation cua harness chua bao gio chay tren du lieu that.
#
# GHI TUNG QUYET DINH CUA TUNG CONG, khong chi ket qua cuoi. Ly do: khi vong tu dap
# KHONG hanh dong, cau hoi dat ra luon la "no bi chan o cong nao" — circuit breaker,
# error budget, blast radius, hay dry-run. Chi ghi ket qua cuoi thi khong tra loi duoc.
#
# GHI HONG KHONG DUOC LAM CHET VONG LAP. Audit la thu yeu so voi viec dap su co; neu
# dia day hay mount read-only thi log mot warning roi di tiep, dung nem exception lam
# sap ca tien trinh remediation.
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

log = logging.getLogger("aiops.remediation.audit")

# Mac dinh nam canh module. Tren EKS rootfs la read-only (MANDATE-05, khong duoc lui)
# nen deployment tro bien nay sang emptyDir writable — dung mau ALERTER_HISTORY_FILE
# ma detector da dung.
_DEFAULT_AUDIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_log.jsonl")

# Cac cong theo dung thu tu trong process_oom_policy(). Dung hang so thay vi chuoi roi
# de khong ai go sai ten stage roi query mai khong ra.
STAGE_DETECT = "detect"
STAGE_CIRCUIT_BREAKER = "circuit_breaker"
STAGE_ERROR_BUDGET = "error_budget"
STAGE_BLAST_RADIUS = "blast_radius"
STAGE_DRY_RUN = "dry_run"
STAGE_ACTION = "action"
STAGE_VERIFY = "verify"
STAGE_ROLLBACK = "rollback"
STAGE_ESCALATE = "escalate"

SCHEMA_VERSION = 1


def audit_path():
    return os.environ.get("REMEDIATION_AUDIT_FILE", _DEFAULT_AUDIT)


def new_remediation_id():
    """Return one correlation id for a complete trigger->terminal-decision attempt."""
    return f"rem-{uuid.uuid4().hex}"


def record(stage, decision, rule_id, service=None, pod=None, dry_run=None,
           remediation_id=None, **detail):
    """Ghi mot dong JSONL vao audit log.

    stage    — cong nao (dung hang so STAGE_* o tren)
    decision — "allow" | "deny" | "acted" | "pass" | "fail" | "skipped"
    remediation_id — khoa noi TAT CA quyet dinh cua cung mot lan remediation
    detail   — moi truong phu khac, vd threshold da dung, gia tri do duoc, loi gap phai

    Tra ve dict da ghi (de test doc duoc), hoac None neu ghi hong.
    """
    ts = time.time()
    rec = {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"evt-{uuid.uuid4().hex}",
        # Khong tu tao ID o day: caller quen truyen thi de None de correlation gap
        # hien ro trong audit, thay vi im lang bia mot attempt moi cho tung record.
        "remediation_id": remediation_id,
        "ts": ts,
        "ts_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "stage": stage,
        "decision": decision,
        "rule_id": rule_id,
        "service": service,
        "pod": pod,
        "dry_run": dry_run,
    }
    rec.update(detail)
    if remediation_id is None:
        log.warning("audit record thieu remediation_id (stage=%s, rule=%s)", stage, rule_id)
    try:
        with open(audit_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        return rec
    except Exception as exc:  # noqa: BLE001
        # Xem ghi chu dau file: audit hong KHONG duoc lam chet vong lap remediation.
        log.warning("khong ghi duoc audit log (%s): %s", audit_path(), exc)
        return None
