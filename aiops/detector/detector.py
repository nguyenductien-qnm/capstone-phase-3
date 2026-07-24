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


def eval_metric_rule(rule, prom):
    """
    Return list of (dedup_key, headline, fields) for each series that breaches
    threshold or trips the dynamic 3-sigma detector.

    headline: uses summary (SLO breach) or summary_dynamic (baseline deviation only).
    fields:   structured list of (name, value, inline) for Discord embed.
    """
    alerts = []
    try:
        series = prom.query(rule["query"])
    except Exception as exc:  # noqa: BLE001
        log.error("Prometheus query error (rule=%s): %s", rule["id"], exc)
        return alerts

    op = rule.get("op", "gt")
    threshold = rule["threshold"]

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

        if history_key not in metric_history:
            metric_history[history_key] = []

        history = metric_history[history_key]

        if len(history) >= 5:
            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std_dev = variance ** 0.5
            if op == "gt":
                dynamic_threshold = mean + 3 * std_dev
                if value > dynamic_threshold and (value - mean) > 0.001:
                    dynamic_fired = True
            elif op == "lt":
                dynamic_threshold = mean - 3 * std_dev
                if value < dynamic_threshold and (mean - value) > 0.001:
                    dynamic_fired = True

        # Keep rolling window of 30 samples. Winsorize before appending: an
        # unmitigated outlier would otherwise drag mean/std toward itself for
        # the next ~30 cycles, raising the bar for detecting a second, smaller,
        # separate incident right after (MANDATE-15 masking-resistance case —
        # a single spike/noise in the window must not hide a distinct real
        # incident). Only clip once a baseline exists (len>=5); clip toward
        # dynamic_threshold rather than dropping the sample, so a sustained
        # anomaly still drags the baseline eventually instead of pinning it.
        history_value = value
        if len(history) >= 5:
            if op == "gt":
                history_value = min(value, dynamic_threshold)
            elif op == "lt":
                history_value = max(value, dynamic_threshold)
        history.append(history_value)
        if len(history) > 30:
            history.pop(0)

        if static_fired or dynamic_fired:
            dedup_key = f"{rule['id']}:{svc}"
            method_parts = []
            if static_fired:
                method_parts.append(f"Static (val={value:.4f} > th={threshold})")
            if dynamic_fired:
                method_parts.append(
                    f"3-Sigma (val={value:.4f} > th_dev={dynamic_threshold:.4f}, "
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


def run_cycle(cfg, prom, osc, core_v1, alerter) -> int:
    """
    One detection cycle: evaluate all rules, buffer alerts, flush grouped messages.
    Returns the number of grouped alert messages dispatched.
    """
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
        dispatched = run_cycle(cfg, prom, osc, core_v1, alerter)
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
