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

from sources import PrometheusClient, OpenSearchClient
from alerter import Alerter

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


def eval_metric_rule(rule, prom):
    """Tra ve list cac alert (dedup_key, message) cho tung series vuot nguong."""
    alerts = []
    try:
        series = prom.query(rule["query"])
    except Exception as exc:  # noqa: BLE001
        log.error("query Prometheus loi (rule=%s): %s", rule["id"], exc)
        return alerts

    op = rule.get("op", "gt")
    threshold = rule["threshold"]
    for value, labels in series:
        fired = value > threshold if op == "gt" else value < threshold
        if not fired:
            continue
        svc = labels.get("service_name", "unknown")
        dedup_key = f"{rule['id']}:{svc}"
        msg = f"{rule['summary']} | service={svc} gia_tri={value:.4f} nguong={threshold}"
        alerts.append((dedup_key, msg))
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
        msg = f"{rule['summary']} | so log khop={count} trong {rule.get('window_minutes', 5)}m"
        if sample:
            msg += f"\n  vi du log: {str(sample)[:200]}"
        alerts.append((dedup_key, msg))
    return alerts


def run_cycle(cfg, prom, osc, alerter):
    fired = 0
    for rule in cfg["rules"]:
        if rule["type"] == "metric":
            results = eval_metric_rule(rule, prom)
        elif rule["type"] == "log":
            results = eval_log_rule(rule, osc)
        else:
            log.warning("rule %s co type khong hop le: %s", rule.get("id"), rule.get("type"))
            continue
        for dedup_key, message in results:
            if alerter.send(dedup_key, rule["severity"], rule["id"], message):
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

    webhook = None if args.dry_run else os.environ.get(cfg["alert"]["webhook_env"])
    provider = "stdout" if args.dry_run else cfg["alert"].get("provider", "auto")
    alerter = Alerter(webhook, provider=provider, cooldown_seconds=cfg["alert"]["cooldown_seconds"])

    log.info("AIOps detector khoi dong | provider=%s | %d rule | poll=%ss",
             alerter.provider, len(cfg["rules"]), cfg["poll_interval_seconds"])

    if args.once:
        fired = run_cycle(cfg, prom, osc, alerter)
        log.info("vong don hoan tat, da ban %d alert", fired)
        return

    while True:
        try:
            run_cycle(cfg, prom, osc, alerter)
        except Exception as exc:  # noqa: BLE001 - giu vong lap song
            log.error("loi trong vong lap: %s", exc)
        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
