#!/usr/bin/env python3
# TF1-72 [AIOps-W2] - Vong khep kin auto-remediation: phat hien (tai dung rule cua
# detector) -> kiem tra an toan (error-budget, blast-radius, dry-run) -> hanh dong
# (restart pod) -> verify qua telemetry -> rollback/circuit-breaker.
#
# THIET KE: component TACH RIENG khoi aiops/detector/ (khong sua detector.py/alerter.py -
# tranh dung vao PR dang mo, giu nguyen ranh gioi "detector = detect-only, 0 quyen K8s"
# da document khap repo). Tu poll OpenSearch rieng, tai dung PrometheusClient/
# OpenSearchClient/Alerter (import truc tiep tu aiops/detector/, khong duplicate code).
#
# RANG BUOC SINH TU (RULES.md Sec8): KHONG BAO GIO doc co flagd o bat ky dau trong
# module nay de quyet dinh hanh vi (bai hoc tu circuit-breaker LLM tung vi pham luat).
# Chi dung ket qua verify THAT (K8s pod status + Prometheus) - xem verifier.py.
#
# Chay:
#   PROM_URL=... OPENSEARCH_URL=... REMEDIATION_DRY_RUN=false python remediation.py
#   python remediation.py --once      # 1 vong roi thoat (test/CI)
#   python remediation.py --dry-run   # ep dry-run bat ke config/env (an toan tuyet doi)
import argparse
import logging
import os
import sys
import time

import yaml

# Dev/test layout: sources.py/alerter.py nam o thu muc anh em ../detector/.
# Container layout (xem Dockerfile): da COPY phang vao cung /app voi remediation.py,
# nen import truc tiep se thanh cong truoc khi can dung sys.path fallback.
_DETECTOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector")
sys.path.insert(0, os.path.abspath(_DETECTOR_DIR))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import PrometheusClient, OpenSearchClient  # noqa: E402
from alerter import Alerter  # noqa: E402

from blast_radius import BlastRadiusGuard  # noqa: E402
from circuit_breaker import CircuitBreaker  # noqa: E402
from k8s_actions import find_oom_pods, restart_pod, load_k8s_client  # noqa: E402
from verifier import verify_oom_recovery  # noqa: E402

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("aiops.remediation")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rule_by_id(rules_cfg, rule_id):
    for rule in rules_cfg["rules"]:
        if rule["id"] == rule_id:
            return rule
    return None


def _env_url(env_name):
    val = os.environ.get(env_name)
    if not val:
        log.warning("Thieu bien moi truong %s", env_name)
    return val


def check_error_budget_ok(prom, eb_cfg):
    """Spec Sec4.2: truoc khi hanh dong PHAI kiem Error Budget. Neu vuot nguong
    (budget can) -> tra ve False, remediation phai Halt & Page Human."""
    if not eb_cfg.get("enabled", True):
        return True
    try:
        series = prom.query(eb_cfg["query"])
    except Exception as exc:  # noqa: BLE001
        log.error("khong query duoc error-budget, coi nhu KHONG an toan de tranh hanh dong mu: %s", exc)
        return False
    max_ratio = eb_cfg["max_ratio"]
    for value, _labels in series:
        if value > max_ratio:
            return False
    return True


def process_oom_policy(policy, rule, cfg, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run):
    k8s_cfg = cfg["k8s"]
    namespace = k8s_cfg["namespace"]
    service_label_key = k8s_cfg["service_label_key"]
    sb = policy["safety_boundaries"]

    # 1. Phat hien: tai dung dung match_phrases cua rule trong detector/rules.yaml,
    # KHONG dinh nghia lai nguong o day (single source of truth).
    phrases = rule.get("match_phrases") or rule.get("match_phrase")
    window_minutes = rule.get("window_minutes", 5)
    try:
        count, _sample = osc.count_matches(phrases, window_minutes)
    except Exception as exc:  # noqa: BLE001
        log.error("query OpenSearch loi (rule=%s): %s", rule["id"], exc)
        return
    if count < rule.get("min_count", 1):
        return  # chua co dau hieu OOM, khong lam gi

    # Xac dinh CHINH XAC pod nao dang OOM that qua K8s API (dang tin cay hon parse
    # text log - xem k8s_actions.find_oom_pods). Neu log rule keu nhung K8s khong
    # thay pod OOM nao gan day (vd da tu hoi phuc) -> khong hanh dong.
    oom_pods = find_oom_pods(core_v1, namespace, service_label_key)
    if not oom_pods:
        log.info("rule %s keu (count=%d) nhung khong tim thay pod OOMKilled that qua K8s API, bo qua", rule["id"], count)
        return

    for oom in oom_pods:
        pod_name = oom["pod_name"]
        service_label = oom["service_label"]
        scope_key = namespace if sb["blast_radius"]["scope"] == "namespace" else f"{namespace}:{service_label}"
        dedup_key = f"{rule['id']}:{service_label}"

        if breaker.is_open(dedup_key):
            log.warning("circuit breaker DANG MO cho %s - tu choi hanh dong, chi escalate", dedup_key)
            alerter.send(
                f"remediation-cb-open:{dedup_key}", "critical", f"remediation-circuit-breaker-open:{rule['id']}",
                f"Circuit breaker đang MỞ cho {service_label} (namespace={namespace}) — đã fail liên tiếp quá "
                f"{breaker.max_consecutive_failures} lần, từ chối tự động remediate. CẦN người can thiệp thủ công.",
            )
            continue

        # 2. Error-budget guard (spec Sec4.2)
        if not check_error_budget_ok(prom, sb["error_budget_check"]):
            log.warning("error budget can/khong an toan - Halt Automation & Page Human")
            alerter.send(
                f"remediation-budget-halt:{dedup_key}", "critical", f"remediation-halt-error-budget:{rule['id']}",
                f"Error budget đã cạn — TẠM DỪNG auto-remediation cho {service_label}, cần người xử lý thủ công.",
            )
            continue

        # 3. Blast-radius guard (spec Sec4.3)
        if not blast_guard.allow(scope_key):
            log.warning("blast-radius vuot gioi han cho scope=%s - tu choi + escalate", scope_key)
            alerter.send(
                f"remediation-blast-radius:{dedup_key}", "critical", f"remediation-blast-radius-exceeded:{rule['id']}",
                f"Đã vượt giới hạn blast-radius ({sb['blast_radius']['max_actions']} action / "
                f"{sb['blast_radius']['time_window_seconds']}s / {sb['blast_radius']['scope']}) cho {scope_key} — "
                f"từ chối restart thêm, cần người kiểm tra.",
            )
            continue

        # 4. Dry-run gate (spec Sec4.1) - KHONG goi K8s API that neu dry_run.
        if dry_run:
            log.info("[DRY-RUN] se restart pod %s/%s (service=%s) - khong goi K8s API that",
                      namespace, pod_name, service_label)
            alerter.send(
                f"remediation-dryrun:{dedup_key}", "info", f"remediation-dry-run:{rule['id']}",
                f"[DRY-RUN] Sẽ restart pod {pod_name} (service={service_label}, namespace={namespace}) — "
                f"chưa thực thi thật, đang ở chế độ mô phỏng.",
            )
            continue

        # 5. Hanh dong that: restart pod (action duy nhat trong scope).
        blast_guard.record(scope_key)
        try:
            restart_pod(core_v1, namespace, pod_name, policy["action"]["grace_period_seconds"])
        except Exception as exc:  # noqa: BLE001
            log.error("restart_pod that bai: %s", exc)
            continue

        # 6. Verify (spec Sec4.4)
        verify_cfg = sb["verify"]
        ok = verify_oom_recovery(
            core_v1, namespace, service_label_key, service_label, pod_name,
            duration_seconds=verify_cfg["duration_seconds"],
            poll_interval_seconds=verify_cfg["poll_interval_seconds"],
        )

        if ok:
            breaker.record_success(dedup_key)
            alerter.send(
                f"remediation-success:{dedup_key}", "info", f"remediation-verified:{rule['id']}",
                f"Đã restart pod {pod_name} (service={service_label}) — verify PASS, service đã hồi phục.",
            )
        else:
            # 7. "Rollback": action restart-pod khong doi config gi de ma rollback ve -
            # dung lai + tang circuit breaker + escalate (quyet dinh da chot voi user,
            # trung thuc voi nang luc that, khong bia hanh dong helm rollback gia).
            just_opened = breaker.record_failure(dedup_key)
            severity = "critical" if just_opened else "warning"
            suffix = " — CIRCUIT BREAKER VỪA MỞ, dừng tự động remediate cho tới khi người xử lý." if just_opened else ""
            alerter.send(
                f"remediation-verify-failed:{dedup_key}:{time.time()}", severity, f"remediation-verify-failed:{rule['id']}",
                f"Restart pod {pod_name} (service={service_label}) KHÔNG khắc phục được — verify FAIL.{suffix}",
            )


def run_cycle(cfg, rules_cfg, prom, osc, core_v1, alerter, policy_state, dry_run):
    """policy_state: dict rule_id -> (BlastRadiusGuard, CircuitBreaker) rieng cho tung policy."""
    for policy in cfg["policies"]:
        rule = load_rule_by_id(rules_cfg, policy["rule_id"])
        if rule is None:
            log.error("policy tham chieu rule_id=%s nhung khong tim thay trong detector/rules.yaml", policy["rule_id"])
            continue
        blast_guard, breaker = policy_state[policy["rule_id"]]
        if policy["action"]["type"] == "k8s_restart_pod":
            process_oom_policy(policy, rule, cfg, prom, osc, core_v1, alerter, blast_guard, breaker, dry_run)
        else:
            log.warning("action type %s chua duoc ho tro (scope MVP chi co k8s_restart_pod)", policy["action"]["type"])


def main():
    parser = argparse.ArgumentParser(description="TF1-72 AIOps closed-loop remediation")
    default_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remediation_policy.yaml")
    default_rules = os.path.join(os.path.abspath(_DETECTOR_DIR), "rules.yaml")
    parser.add_argument("--config", default=default_cfg)
    parser.add_argument("--rules", default=default_rules)
    parser.add_argument("--once", action="store_true", help="chay 1 vong roi thoat")
    parser.add_argument("--dry-run", action="store_true", help="ep dry-run tuyet doi, bo qua config/env")
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    rules_cfg = load_yaml(args.rules)

    prom = PrometheusClient(
        _env_url(cfg["sources"]["prometheus_url_env"]) or "http://localhost:9090",
        timeout=cfg["sources"].get("http_timeout_seconds", 5),
    )
    osc = OpenSearchClient(
        _env_url(cfg["sources"]["opensearch_url_env"]) or "http://localhost:9200",
        index=cfg["sources"].get("opensearch_index", "otel-logs-*"),
        message_field=cfg["sources"].get("opensearch_message_field", "body"),
        time_field=cfg["sources"].get("opensearch_time_field", "observedTimestamp"),
        timeout=cfg["sources"].get("http_timeout_seconds", 5),
    )
    core_v1 = load_k8s_client()
    alerter = Alerter(provider=cfg["alert"].get("provider", "auto"), cooldown_seconds=cfg["alert"]["cooldown_seconds"])

    # Dry-run: --dry-run (CLI) HOAC REMEDIATION_DRY_RUN=false phai duoc set RO RANG
    # moi tat dry-run. Mac dinh AN TOAN tuyet doi (spec Sec4.1).
    env_dry_run = os.environ.get("REMEDIATION_DRY_RUN", "true").strip().lower()
    dry_run = args.dry_run or env_dry_run != "false"

    # Moi policy co blast-radius/circuit-breaker RIENG theo cau hinh cua no (khong
    # dung chung 1 instance cho nhieu policy khac nhau).
    policy_state = {}
    for policy in cfg["policies"]:
        sb = policy["safety_boundaries"]
        policy_state[policy["rule_id"]] = (
            BlastRadiusGuard(sb["blast_radius"]["max_actions"], sb["blast_radius"]["time_window_seconds"]),
            CircuitBreaker(sb["circuit_breaker"]["max_consecutive_failures"], sb["circuit_breaker"]["reset_timeout_seconds"]),
        )

    log.info("AIOps remediation engine khoi dong | dry_run=%s | %d policy | poll=%ss",
             dry_run, len(cfg["policies"]), cfg["poll_interval_seconds"])

    if args.once:
        run_cycle(cfg, rules_cfg, prom, osc, core_v1, alerter, policy_state, dry_run)
        log.info("vong don hoan tat")
        return

    while True:
        try:
            run_cycle(cfg, rules_cfg, prom, osc, core_v1, alerter, policy_state, dry_run)
        except Exception as exc:  # noqa: BLE001 - giu vong lap song
            log.error("loi trong vong lap: %s", exc)
        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
