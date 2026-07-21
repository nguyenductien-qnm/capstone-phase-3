#!/usr/bin/env python3
# TF1-53 [AIOps-W1-T5] - Xay dung script/tool phat hien loi & canh bao van hanh.
#
# Vong lap: poll Prometheus (metric) + OpenSearch (log) -> phat hien loi -> ban alert on-call.
# CHI phat hien + canh bao. KHONG tu khac phuc (do la TF1-50). KHONG dung/doi flagd.
#
# Chay:
#   PROM_URL=http://localhost:9090 OPENSEARCH_URL=http://localhost:9200 \
#   ALERT_WEBHOOK_URL=<slack-or-discord-webhook> python detector.py
#
#   python detector.py --once      # chay 1 vong roi thoat (dung cho test/CI)
#   python detector.py --dry-run   # in alert ra stdout thay vi goi webhook
import os
import sys
import time
import argparse
import logging

import yaml
import pandas as pd
import numpy as np

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
        log.warning("Thieu bien moi truong %s", env_name)
    return val


metric_history = {}

def eval_metric_rule(rule, prom):
    """Tra ve list cac alert (dedup_key, message, fields) cho tung series vuot nguong hoac bat thuong dynamic 3-sigma."""
    alerts = []
    try:
        series = prom.query(rule["query"])
    except Exception as exc:  # noqa: BLE001
        log.error("query Prometheus loi (rule=%s): %s", rule["id"], exc)
        return alerts

    op = rule.get("op", "gt")
    threshold = rule["threshold"]
    for value, labels in series:
        svc = labels.get("service_name", "unknown")
        history_key = f"{rule['id']}:{svc}"
        
        # 1. Static threshold evaluation
        static_fired = value > threshold if op == "gt" else value < threshold
        
        # 2. Dynamic anomaly detection (STL + 3-sigma)
        dynamic_fired = False
        dynamic_threshold = 0.0
        
        if history_key not in metric_history:
            metric_history[history_key] = []
            
        history = metric_history[history_key]
        
        # Append current metric value to history (cap at 30 values)
        history.append(value)
        if len(history) > 30:
            history.pop(0)

        # 2. Dynamic anomaly detection (EWMA)
        dynamic_fired = False
        dynamic_threshold = 0.0
        ewma_mean = 0.0
        
        if len(history) >= 5:
            # Calculate EWMA on history excluding current point (t-1)
            # to prevent a current spike from inflating the std_dev and masking the anomaly.
            series = pd.Series(history[:-1])
            alpha = 0.2
            
            # Use pandas EWM to calculate mean and std according to spec
            ewma_mean = series.ewm(alpha=alpha, adjust=False).mean().iloc[-1]
            ewma_std = series.ewm(alpha=alpha, adjust=False).std().replace(0, 1e-10).iloc[-1]
            
            dynamic_threshold = ewma_mean + 3 * ewma_std
            
            # Dynamic alert when value exceeds 3-sigma threshold and variance is non-negligible
            if op == "gt" and value > dynamic_threshold and (value - ewma_mean) > 0.001:
                dynamic_fired = True
            elif op == "lt" and value < (ewma_mean - 3 * ewma_std) and (ewma_mean - value) > 0.001:
                dynamic_fired = True

        # Trigger alert if either threshold is breached
        if static_fired or dynamic_fired:
            dedup_key = f"{rule['id']}:{svc}"
            method_str = []
            if static_fired:
                method_str.append(f"Static (val={value:.4f} > th={threshold})")
            if dynamic_fired:
                method_str.append(f"EWMA 3-Sigma (val={value:.4f} > th_dev={dynamic_threshold:.4f}, mean={ewma_mean:.4f})")

            # Headline theo LOP phat hien (review 16/07: alert cart 6ms tung mang
            # headline "p95 > 1s" cua lop static du chi lop 3-sigma keu -> gay hieu nham).
            # - static keu (co/khong kem 3-sigma): dung summary (vi pham nguong SLO that)
            # - CHI 3-sigma keu: dung summary_dynamic (lech baseline, CHUA cham nguong)
            if static_fired:
                headline = rule["summary"]
            else:
                headline = rule.get(
                    "summary_dynamic",
                    f"Lệch bất thường so với baseline của chính service (CHƯA chạm ngưỡng {threshold})",
                )

            # Review 17/07: tach du lieu that (service/gia tri/phuong phap) thanh field
            # rieng cho Discord embed, thay vi nhoi het vao 1 cau van dai.
            fields = [("🎯 Dịch vụ", svc, True)]
            if static_fired:
                fields.append(("📊 Giá trị đo / Ngưỡng SLO", f"{value:.4f} / {threshold}", True))
            else:
                # dynamic_fired-only => nhanh `len(history) >= 5` chac chan da chay,
                # nen mean/std_dev da duoc gan o tren.
                fields.append((
                    "📊 Giá trị đo / Baseline (mean ± 3σ)",
                    f"{value:.4f} / {mean:.4f} ± {3 * std_dev:.4f}",
                    True,
                ))
            fields.append(("🔍 Phương pháp phát hiện", ", ".join(method_str), False))

            alerts.append((dedup_key, headline, fields))

    return alerts



def eval_log_rule(rule, osc):
    alerts = []
    phrases = rule.get("match_phrases") or rule.get("match_phrase")
    try:
        count, sample = osc.count_matches(phrases, rule.get("window_minutes", 5))
    except Exception as exc:  # noqa: BLE001
        log.error("query OpenSearch loi (rule=%s): %s", rule["id"], exc)
        return alerts

    if count >= rule.get("min_count", 1):
        dedup_key = rule["id"]
        window_minutes = rule.get("window_minutes", 5)
        # Review 17/07: tach so dem/log mau thanh field rieng cho Discord embed
        # (xem alerter.py) thay vi nhoi vao 1 doan text dai.
        fields = [("🔢 Số log khớp / Cửa sổ", f"{count} / {window_minutes}m", True)]
        if sample:
            fields.append(("📝 Bằng chứng (log mẫu)", f"```{str(sample)[:200]}```", False))
        alerts.append((dedup_key, rule["summary"], fields))
    return alerts


def eval_k8s_status_rule(rule, core_v1):
    """Doc trang thai pod THAT tu K8s API (khong qua log). Bo sung cho rule kieu
    OOMKilled: kernel SIGKILL container truoc khi no kip ghi log ve cai chet cua chinh
    no, nen rule log-based khong bao gio khop (xac nhan qua chaos test that 17/07,
    xem ADR-012 addendum)."""
    alerts = []
    namespace = rule.get("k8s_namespace", "techx-tf1")
    service_label_key = rule.get("service_label_key", "opentelemetry.io/name")
    lookback = rule.get("lookback_seconds", 300)
    try:
        oom_pods = find_oom_pods(core_v1, namespace, service_label_key, since_seconds=lookback)
    except Exception as exc:  # noqa: BLE001
        log.error("query K8s API loi (rule=%s): %s", rule["id"], exc)
        return alerts

    for oom in oom_pods:
        svc = oom["service_label"]
        dedup_key = f"{rule['id']}:{svc}"
        fields = [
            ("🎯 Dịch vụ", svc, True),
            ("📦 Pod", oom["pod_name"], True),
            ("🔍 Container", oom["container_name"], False),
        ]
        alerts.append((dedup_key, rule["summary"], fields))
    return alerts


def run_cycle(cfg, prom, osc, core_v1, alerter):
    fired = 0
    for rule in cfg["rules"]:
        if rule["type"] == "metric":
            results = eval_metric_rule(rule, prom)
        elif rule["type"] == "log":
            results = eval_log_rule(rule, osc)
        elif rule["type"] == "k8s_status":
            results = eval_k8s_status_rule(rule, core_v1)
        else:
            log.warning("rule %s co type khong hop le: %s", rule.get("id"), rule.get("type"))
            continue
        for dedup_key, message, fields in results:
            if alerter.send(dedup_key, rule["severity"], rule["id"], message, fields=fields):
                fired += 1
    return fired


def main():
    parser = argparse.ArgumentParser(description="TF1-53 AIOps error-detection & alerting")
    default_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
    parser.add_argument("--config", default=default_cfg)
    parser.add_argument("--once", action="store_true", help="chay 1 vong roi thoat")
    parser.add_argument("--dry-run", action="store_true", help="in alert ra stdout, khong goi webhook")
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

    webhook = None if args.dry_run else os.environ.get(cfg["alert"]["webhook_env"]) # Deprecated in favor of direct env lookup in Alerter
    provider = "stdout" if args.dry_run else cfg["alert"].get("provider", "auto")
    
    # If not dry-run, Alerter will automatically pull AIOPS_SLACK_WEBHOOK_CRITICAL and INFO from os.environ
    if args.dry_run:
        os.environ["AIOPS_SLACK_WEBHOOK_CRITICAL"] = ""
        os.environ["AIOPS_SLACK_WEBHOOK_INFO"] = ""

    alerter = Alerter(provider=provider, cooldown_seconds=cfg["alert"]["cooldown_seconds"])

    log.info("AIOps detector khoi dong | provider=%s | %d rule | poll=%ss",
             alerter.provider, len(cfg["rules"]), cfg["poll_interval_seconds"])

    if args.once:
        fired = run_cycle(cfg, prom, osc, core_v1, alerter)
        log.info("vong don hoan tat, da ban %d alert", fired)
        return

    while True:
        try:
            run_cycle(cfg, prom, osc, core_v1, alerter)
        except Exception as exc:  # noqa: BLE001 - giu vong lap song
            log.error("loi trong vong lap: %s", exc)
        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
