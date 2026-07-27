#!/usr/bin/env python3
# TF1-53 [AIOps-W1-T5] - Build script/tool for error detection & operational alerting.
#
# Loop: poll Prometheus (metric) + OpenSearch (log) + K8s API (status) ->
#       detect errors -> buffer alerts -> flush grouped messages to on-call.
# ONLY detects + alerts. Does NOT auto-remediate (TF1-72). Does NOT touch flagd.
#
# Run:
#   PROM_URL=http://localhost:9090 OPENSEARCH_URL=http://localhost:9200 \
#   AIOPS_SLACK_WEBHOOK_CRITICAL=<webhook> python detector.py
#
#   python detector.py --once      # run one cycle then exit (for test/CI)
#   python detector.py --dry-run   # print alerts to stdout, do not call webhook
#
# [W2] Pipeline: Detect -> Correlate -> Diagnose -> Act
#   This file is the Detect stage.
#   Correlate artifacts (correlation_matrix.json, cooccurrence_matrix.json) are
#   produced by correlate.py and committed as static references.
import os
import sys
import time
import argparse
import logging

import yaml

from sources import PrometheusClient, OpenSearchClient
from alerter import Alerter
from k8s_status import load_k8s_client, find_oom_pods

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("aiops.detector")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _env_url(env_name):
    val = os.environ.get(env_name)
    if not val:
        log.warning("Missing environment variable %s", env_name)
    return val


metric_history = {}

# Bo dem "rule mu": rule_id -> so chu ky LIEN TIEP ma query tra ve 0 series.
# Xoa khoi dict ngay khi query co du lieu tro lai.
#
# Ly do ton tai: PromQL sai ten metric TRA VE CHUOI RONG chu khong nem loi, va vong lap
# duoi day khong chay lan nao khi series rong — khong log, khong dem, khong dau hieu gi.
# Do la cach rule `kafka-consumer-lag-high` nam cam hang tuan (do 26/07, xem
# report/mandate15-eks/report.md muc 4.4). Detector phai tu phat hien duoc rule mu cua
# chinh no, chu khong doi nguoi tinh co nhan ra.
empty_query_streak = {}

# 120 chu ky x poll 30s = 60 phut im lang moi bao mot lan. Ghi de bang `silent_rule_cycles`
# o top-level rules.yaml.
SILENT_RULE_CYCLES = 120


def reset_state():
    """Xoa toan bo state cap module. Dung cho test.

    Ton tai de lan sau them global moi thi co MOT cho duy nhat phai cap nhat — quen clear
    mot global se ro ri theo thu tu test, kieu kho debug nhat.
    """
    metric_history.clear()
    empty_query_streak.clear()


def eval_metric_rule(rule, prom):
    """
    Return list of (dedup_key, headline, fields) for each series that breaches
    threshold or trips the dynamic 3-sigma detector.

    headline: uses summary (SLO breach) or summary_dynamic (baseline deviation only).
    fields:   structured list of (name, value, inline) for Discord embed.
    """
    alerts = []
    op = rule.get("op", "gt")
    # Chi chap nhan dung 2 gia tri. Truoc day dong so sanh o duoi la
    #     value > threshold if op == "gt" else value < threshold
    # nghia la MOI gia tri go sai ("GT", ">", "greater") deu roi vao nhanh else va chay
    # thanh `lt`: rule bi DAO CHIEU ma khong co mot dau hieu nao. Khi chua rule nao dung
    # lt thi loi do vo hai; tu khi co rule silent-failure dung lt that thi khong con vo hai.
    # Bo qua rule (fail-closed) chu khong doan sang "gt" — doan la cach de mot rule chay
    # sai trong im lang, con ERROR moi chu ky thi khong the bo qua.
    if op not in ("gt", "lt"):
        log.error("rule %s co op khong hop le: %r (chi nhan 'gt' hoac 'lt') - bo qua rule",
                  rule["id"], op)
        return alerts

    try:
        series = prom.query(rule["query"])
    except Exception as exc:  # noqa: BLE001
        log.error("Prometheus query error (rule=%s): %s", rule["id"], exc)
        # CO Y khong dung vao empty_query_streak: goi Prometheus that bai la su co ha tang,
        # khong phai bang chung rule mu. Dem no vao se bao "query sai ten metric" moi khi
        # Prometheus sap - dung luc on-call can tin cay nhat.
        return alerts

    if series:
        empty_query_streak.pop(rule["id"], None)
    else:
        empty_query_streak[rule["id"]] = empty_query_streak.get(rule["id"], 0) + 1

    threshold = rule["threshold"]
    # Cong SLO cho tang dong (backtest 12h tren cum EKS, 26-27/07 — xem addendum
    # ADR-012). Tang 3-sigma keu vi bat thuong THONG KE, khong phai vi co y nghia
    # VAN HANH: cart p95 di tu 5ms len 20ms la vuot 3-sigma, trong khi SLO la 1000ms
    # — cao gap 28 lan gia tri lon nhat tung quan sat. Cong nay chi cho tang dong keu
    # khi gia tri DA TIEN GAN nguong tinh, dung voi muc dich goc cua no ("canh bao som
    # truoc khi vi pham SLO").
    #
    # So do that tren 2 tin hieu, 12h: 34 -> 8 alert (giam 76%), KHONG mat phat hien nao.
    # None = khong khai bao = hanh vi y het truoc day. Co y KHONG dat mac dinh khac
    # None de tranh doi ngam hanh vi cua ca 11 rule metric cung luc.
    dynamic_min_fraction = rule.get("dynamic_min_fraction")

    # Tat han tang dong theo tung rule. Mac dinh True = hanh vi y het truoc day (16 rule
    # hien co khong khai bao truong nay).
    #
    # Ly do ton tai: rule "san thong luong" (op=lt tren mot ti le) chay tren chuoi quanh
    # quan 1.0 voi phuong sai rat nho — mot nhip xuong 0.7 vo nghia ve van hanh van vuot
    # mean-3sigma. Va cong SLO (dynamic_min_fraction) KHONG ap cho nhanh lt nen khong cuu
    # duoc. Tat luon ca viec ghi metric_history: khong co baseline thi khong co baseline
    # nhiem doc sau su co (chuoi 0 cua luc chet keo mean xuong), va khong ton bo nho cho
    # chuoi khong bao gio dung den.
    dynamic_enabled = rule.get("dynamic_enabled", True)

    for value, labels in series:
        svc = labels.get("service_name", "unknown")
        history_key = f"{rule['id']}:{svc}"

        # --- Layer 1: static threshold ---
        static_fired = value > threshold if op == "gt" else value < threshold

        # --- Layer 2: dynamic 3-sigma ---
        dynamic_fired = False
        dynamic_threshold = 0.0
        mean = 0.0
        std_dev = 0.0

        if dynamic_enabled:
            if history_key not in metric_history:
                metric_history[history_key] = []

            history = metric_history[history_key]

            if len(history) >= 5:
                mean = sum(history) / len(history)
                variance = sum((x - mean) ** 2 for x in history) / len(history)
                std_dev = variance ** 0.5
                # Nguong dong theo CHIEU cua rule. Truoc day bien nay luon la mean+3sigma
                # ke ca khi op=lt: nhanh lt so sanh voi mean-3sigma nhung dong hien thi lai
                # in ra bien nay, tuc in CAN TREN cho mot vi pham huong XUONG.
                dynamic_threshold = (mean + 3 * std_dev) if op == "gt" else (mean - 3 * std_dev)
                # Cong chi ap cho op=gt. Voi op=lt ("gia tri TUT xuong bat thuong") thi
                # "da tien gan nguong" khong dien dat duoc bang mot ti le cua threshold theo
                # cung cong thuc. Rule op=lt duy nhat hien nay (service-traffic-collapse)
                # tat han tang dong bang dynamic_enabled: false, nen cong o nhanh do la
                # van de chua can giai — dung doan mot ngu nghia chua ai can den.
                gate_ok = (
                    dynamic_min_fraction is None
                    or value >= dynamic_min_fraction * threshold
                )
                if op == "gt" and value > dynamic_threshold and (value - mean) > 0.001 and gate_ok:
                    dynamic_fired = True
                elif op == "lt" and value < dynamic_threshold and (mean - value) > 0.001:
                    dynamic_fired = True

            # Keep rolling window of 30 samples
            history.append(value)
            if len(history) > 30:
                history.pop(0)

        if static_fired or dynamic_fired:
            dedup_key = f"{rule['id']}:{svc}"
            # Voi op=gt (moi rule truoc day) chuoi in ra giong het tung byte nhu cu.
            op_symbol = ">" if op == "gt" else "<"
            method_parts = []
            if static_fired:
                method_parts.append(f"Static (val={value:.4f} {op_symbol} th={threshold})")
            if dynamic_fired:
                method_parts.append(
                    f"3-Sigma (val={value:.4f} {op_symbol} th_dev={dynamic_threshold:.4f}, "
                    f"mean={mean:.4f})"
                )

            # Headline: static breach uses SLO summary; 3-sigma-only uses dynamic summary
            # (review 16/07: cart at 6ms was showing "p95 > 1s" headline misleadingly).
            if static_fired:
                headline = rule["summary"]
            else:
                headline = rule.get(
                    "summary_dynamic",
                    f"Baseline deviation detected (not yet at threshold {threshold})",
                )

            # Structured fields for Discord embed (review 17/07)
            fields = [("\U0001F3AF Service", svc, True)]
            if static_fired:
                fields.append(("\U0001F4CF Value / SLO threshold", f"{value:.4f} / {threshold}", True))
            else:
                fields.append((
                    "\U0001F4CF Value / Baseline (mean \u00b1 3\u03c3)",
                    f"{value:.4f} / {mean:.4f} \u00b1 {3 * std_dev:.4f}",
                    True,
                ))
            fields.append(("\U0001F50D Detection method", ", ".join(method_parts), False))

            alerts.append((dedup_key, headline, fields))

    return alerts


def eval_log_rule(rule, osc):
    alerts = []
    phrases = rule.get("match_phrases") or rule.get("match_phrase")
    try:
        count, sample = osc.count_matches(phrases, rule.get("window_minutes", 5))
    except Exception as exc:  # noqa: BLE001
        log.error("OpenSearch query error (rule=%s): %s", rule["id"], exc)
        return alerts

    if count >= rule.get("min_count", 1):
        dedup_key = f"{rule['id']}:log"
        window_minutes = rule.get("window_minutes", 5)
        fields = [("\U0001F4E2 Log matches / window", f"{count} / {window_minutes}m", True)]
        if sample:
            fields.append(("\U0001F50D Sample log", f"```{str(sample)[:200]}```", False))
        alerts.append((dedup_key, rule["summary"], fields))
    return alerts


def eval_k8s_status_rule(rule, core_v1):
    """
    Read real pod state from K8s API (not via logs).
    Supplements log-based OOM detection: kernel SIGKILL kills the container
    before it can write its own death log, so log rules never match.
    Confirmed via chaos test 2026-07-17 (ADR-012 addendum).
    """
    alerts = []
    namespace = rule.get("k8s_namespace", "techx-tf1")
    service_label_key = rule.get("service_label_key", "opentelemetry.io/name")
    lookback = rule.get("lookback_seconds", 300)
    try:
        oom_pods = find_oom_pods(core_v1, namespace, service_label_key,
                                 since_seconds=lookback)
    except Exception as exc:  # noqa: BLE001
        log.error("K8s API query error (rule=%s): %s", rule["id"], exc)
        return alerts

    for oom in oom_pods:
        svc = oom["service_label"]
        dedup_key = f"{rule['id']}:{svc}"
        fields = [
            ("\U0001F3AF Service", svc, True),
            ("\U0001F4E6 Pod", oom["pod_name"], True),
            ("\U0001F50D Container", oom["container_name"], False),
        ]
        alerts.append((dedup_key, rule["summary"], fields))
    return alerts


def silent_rule_note(rule, silent_after):
    """Tra ve canh bao LAN DAU TIEN mot metric rule cham nguong im lang, nguoc lai None.

    So sanh `!=` (chi ban khi streak DUNG BANG nguong) chu khong phai `>=`. Viet `>=` la
    phan xa tu nhien va no SAI: canh bao se ban lai moi chu ky cho toi het doi rule.
    Streak chi ve 0 khi query co du lieu tro lai, nen chu ky "mu -> song -> mu" tu dong
    len dan mot lan nua. Pod cung restart moi lan CI bump image tag (moi merge vao
    develop) -> do la nhip nhac lai tren thuc te.
    """
    # Rule rong-khi-khoe la binh thuong (vd burn-rate co menh de `and`, hay absent() cua
    # mot service dang song). Khong opt-out thi sau 1 gio binh yen chung se tu to cao
    # chinh minh la mu.
    if not rule.get("expect_series", True):
        return None
    if not silent_after or silent_after < 1:
        return None
    if empty_query_streak.get(rule["id"], 0) != silent_after:
        return None
    return (
        f"Rule '{rule['id']}' tra ve 0 series suot {silent_after} chu ky lien tiep — "
        f"query nhieu kha nang sai ten metric/label; rule dang MU, khong the keu."
    )


def run_cycle(cfg, prom, osc, core_v1, alerter, silent_after=None) -> int:
    """
    One detection cycle: evaluate all rules, buffer alerts, flush grouped messages.
    Returns the number of grouped alert messages dispatched.
    """
    if silent_after is None:
        silent_after = cfg.get("silent_rule_cycles", SILENT_RULE_CYCLES)

    for rule in cfg["rules"]:
        if rule["type"] == "metric":
            results = eval_metric_rule(rule, prom)
        elif rule["type"] == "log":
            results = eval_log_rule(rule, osc)
        elif rule["type"] == "k8s_status":
            results = eval_k8s_status_rule(rule, core_v1)
        else:
            log.warning("rule %s has unknown type: %s", rule.get("id"), rule.get("type"))
            continue

        for dedup_key, message, fields in results:
            # send() buffers — does NOT dispatch immediately (K3 fingerprint dedup)
            alerter.send(dedup_key, rule["severity"], rule["id"], message, fields=fields)

        # Detector tu to cao rule mu cua chinh no. CHI cho metric rule: eval_log_rule tra
        # ve count=0 hop le suot ngay, con k8s_status khong co khai niem "chuoi rong".
        if rule["type"] == "metric":
            note = silent_rule_note(rule, silent_after)
            if note:
                log.warning("%s", note)
                # severity="info" co chu dich, DU hien tai AIOPS_SLACK_WEBHOOK_INFO chua
                # duoc set nen moi severity van don ve kenh critical (alerter.py). Day la
                # ly do cu the de set bien do — mot dong cau hinh cum, khong dung den code.
                #
                # dedup_key mang rule_id o o "service" vi alerter tach service tu dedup_key:
                # moi rule mu thanh mot nhom rieng. Dung key chung "detector-silent-rule:detector"
                # se gon hon nhung cooldown se nuot rule mu thu hai tro di ngay trong cung chu ky.
                alerter.send(
                    f"detector-silent-rule:{rule['id']}",
                    "info",
                    "detector-silent-rule",
                    note,
                    fields=[
                        ("\U0001F4A4 Rule mu", rule["id"], True),
                        ("\U0001F501 Chu ky rong lien tiep", str(silent_after), True),
                        ("\U0001F50D Query", f"```{str(rule.get('query'))[:300]}```", False),
                    ],
                )

    # K3: flush all buffered alerts as grouped messages (1 per fingerprint)
    dispatched = alerter.flush()
    if dispatched:
        log.info("cycle complete: %d grouped alert message(s) dispatched", dispatched)
    return dispatched


def main():
    parser = argparse.ArgumentParser(description="TF1-53 AIOps error-detection & alerting")
    default_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
    parser.add_argument("--config", default=default_cfg)
    parser.add_argument("--once", action="store_true", help="run one cycle then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="print alerts to stdout, do not call webhook")
    args = parser.parse_args()

    cfg = load_config(args.config)
    src = cfg["sources"]

    prom = PrometheusClient(
        _env_url(src["prometheus_url_env"]) or "http://localhost:9090",
        timeout=src.get("http_timeout_seconds", 5),
    )
    osc = OpenSearchClient(
        _env_url(src["opensearch_url_env"]) or "http://localhost:9200",
        index=src.get("opensearch_index", "otel-logs-*"),
        message_field=src.get("opensearch_message_field", "body"),
        time_field=src.get("opensearch_time_field", "observedTimestamp"),
        timeout=src.get("http_timeout_seconds", 5),
    )
    core_v1 = load_k8s_client()

    if args.dry_run:
        os.environ["AIOPS_SLACK_WEBHOOK_CRITICAL"] = ""
        os.environ["AIOPS_SLACK_WEBHOOK_INFO"] = ""

    provider = "stdout" if args.dry_run else cfg["alert"].get("provider", "auto")
    alerter = Alerter(
        provider=provider,
        cooldown_seconds=cfg["alert"]["cooldown_seconds"],
    )

    log.info(
        "AIOps detector starting | provider=%s | %d rules | poll=%ss",
        alerter.provider, len(cfg["rules"]), cfg["poll_interval_seconds"],
    )

    if args.once:
        # --once la smoke test / LINTER, khong phai mot nhip cua vong lap: voi
        # silent_after=1, MOT chu ky du de goi ten moi metric rule tra ve 0 series.
        # `python detector.py --once --dry-run` tren Prometheus port-forward sau khi sua
        # rules.yaml se noi ngay rule nao go sai ten metric — dung cai da chet am tham
        # hang tuan. Ngu nghia khac che do chay lien tuc (60 phut) la CO Y.
        dispatched = run_cycle(cfg, prom, osc, core_v1, alerter, silent_after=1)
        log.info("single cycle complete, %d grouped alert(s) dispatched", dispatched)
        return

    while True:
        try:
            run_cycle(cfg, prom, osc, core_v1, alerter)
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            log.error("error in main loop: %s", exc)
        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
