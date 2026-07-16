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


metric_history = {}

# Review 16/07: sàn tuyệt đối cũ (0.001) giả định đơn vị "gần 1" (tỉ lệ lỗi 0-1,
# memory ratio 0-1) — vỡ trên rule đơn vị khác thang: latency tính bằng giây có
# baseline chỉ vài ms (cart p95 ~6ms) nên 0.001 quá LỎNG (lọt FP khi std_dev siết
# chặt band); kafka lag tính bằng số nguyên hàng trăm/nghìn thì 0.001 msg vô nghĩa.
# Sàn TƯƠNG ĐỐI không phụ thuộc đơn vị: chỉ tính bất thường nếu lệch >= 20% so với
# mean của chính service. 20% là mặc định ban đầu, còn phải hiệu chỉnh bằng dữ liệu
# thật cho MANDATE #7b — xem ADR-012.
MIN_RELATIVE_DEVIATION = 0.20
# Baseline gần 0 (vd tỉ lệ lỗi vừa xuất hiện lần đầu) làm độ lệch tương đối vô nghĩa
# (chia cho ~0) — fallback dùng sàn tuyệt đối nhỏ để vẫn bắt được "từ 0 thành có lỗi".
NEAR_ZERO_MEAN = 1e-9
MIN_ABSOLUTE_DEVIATION_NEAR_ZERO = 0.001

def eval_metric_rule(rule, prom):
    """Tra ve list cac alert (dedup_key, message) cho tung series vuot nguong hoac bat thuong dynamic 3-sigma."""
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
        
        if len(history) >= 5:
            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std_dev = variance ** 0.5
            dynamic_threshold = mean + 3 * std_dev
            abs_mean = abs(mean)
            # Vuot 3-sigma thoi chua du - con phai lech CO Y NGHIA so voi mean cua
            # chinh no (sàn tương đối), khong chi "thong ke lech" (band qua siet o
            # baseline gan-hang-so lam moi jitter nho cung vuot 3-sigma).
            if op == "gt" and value > dynamic_threshold:
                if abs_mean > NEAR_ZERO_MEAN:
                    dynamic_fired = (value - mean) / abs_mean > MIN_RELATIVE_DEVIATION
                else:
                    dynamic_fired = (value - mean) > MIN_ABSOLUTE_DEVIATION_NEAR_ZERO
            elif op == "lt" and value < (mean - 3 * std_dev):
                if abs_mean > NEAR_ZERO_MEAN:
                    dynamic_fired = (mean - value) / abs_mean > MIN_RELATIVE_DEVIATION
                else:
                    dynamic_fired = (mean - value) > MIN_ABSOLUTE_DEVIATION_NEAR_ZERO

        # Append current metric value to history (cap at 30 values)
        history.append(value)
        if len(history) > 30:
            history.pop(0)

        # Trigger alert if either threshold is breached
        if static_fired or dynamic_fired:
            dedup_key = f"{rule['id']}:{svc}"
            method_str = []
            if static_fired:
                method_str.append(f"Static (val={value:.4f} > th={threshold})")
            if dynamic_fired:
                method_str.append(f"3-Sigma (val={value:.4f} > th_dev={dynamic_threshold:.4f}, mean={sum(history[:-1])/len(history[:-1]):.4f})")

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
            msg = f"{headline} | service={svc} | Detected by: {', '.join(method_str)}"
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
        msg = f"{rule['summary']} | số log khớp={count} trong {rule.get('window_minutes', 5)}m"
        if sample:
            msg += f"\n  ví dụ log: {str(sample)[:200]}"
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
