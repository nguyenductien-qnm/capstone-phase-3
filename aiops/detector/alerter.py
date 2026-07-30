# TF1-53 [AIOps-W1-T5] - Send alerts to on-call channel (Slack/Discord) + dedup/cooldown.
# Supports providers: slack | discord | stdout | auto (inferred from URL).
# stdout used for test/demo without a webhook (mirrors dry-run spirit of TF1-50).
#
# [W2-K3] Fingerprint dedup: alerts sharing the same (service, 5-min bucket) are buffered
# and flushed as ONE grouped message instead of N separate pings.
# Call alerter.flush() at the end of each detector cycle.
import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import requests

log = logging.getLogger("aiops.alerter")

# Display timezone on alerts: pod runs TZ=UTC but on-call reads VN time (review 16/07:
# alert showed 06:42 while Discord showed 13:42 -> confusion when cross-referencing).
# Fixed offset +7 (VN has no DST) - no tzdata dependency (python:slim doesn't have it).
TZ_VN = timezone(timedelta(hours=7))

SEVERITY_EMOJI = {"critical": "\U0001F534", "warning": "\U0001F7E1", "info": "\u26AA"}
# Discord brand colors by severity (decimal, used for embed `color` field).
SEVERITY_COLOR = {"critical": 0xED4245, "warning": 0xFEE75C, "info": 0x5865F2}

# History file for G7 co-occurrence analysis (overridable via env var).
_DEFAULT_HISTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerter_history.jsonl")


def _history_path():
    return os.environ.get("ALERTER_HISTORY_FILE", _DEFAULT_HISTORY)


def _append_history(record: dict):
    """Append one alert record to the JSONL history log (used by G7 co-occurrence analysis)."""
    try:
        with open(_history_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("could not write alert history: %s", exc)


def _time_bucket(ts: float, bucket_seconds: int = 300) -> int:
    """Floor-divide timestamp into fixed-width buckets (default 5 min = 300 s)."""
    return int(ts // bucket_seconds)


def _fingerprint(service: str, ts: float, bucket_seconds: int = 300) -> str:
    """Dedup key: same service + same 5-min window -> same fingerprint."""
    return f"{service}:{_time_bucket(ts, bucket_seconds)}"


class Alerter:
    """
    Detect-stage alert dispatcher with two dedup layers:

    Layer 1 — per-rule cooldown (existing):
        Same rule_id + service fires at most once per cooldown_seconds.

    Layer 2 — fingerprint grouping (K3, new):
        All rules that fire for the same service within the same 5-minute
        bucket are buffered in self._pending and sent as ONE merged message
        when flush() is called at the end of the detector cycle.
    """

    def __init__(self, provider="auto", cooldown_seconds=600, timeout=5,
                 bucket_seconds=300):
        # Webhook URLs pulled from env (dual-channel: critical vs info).
        self.webhook_critical = os.environ.get("AIOPS_SLACK_WEBHOOK_CRITICAL")
        self.webhook_info = os.environ.get("AIOPS_SLACK_WEBHOOK_INFO")
        self.cooldown = cooldown_seconds
        self.timeout = timeout
        self.bucket_seconds = bucket_seconds

        # Resolve provider based on the critical webhook URL (or fallback to info).
        test_url = self.webhook_critical or self.webhook_info
        self.provider = self._resolve_provider(provider, test_url)

        # Layer 1: per-(rule_id, service) cooldown -> dedup_key -> last_sent epoch
        self._last_sent: dict[str, float] = {}

        # Layer 2: fingerprint buffer -> fingerprint -> list of alert dicts
        self._pending: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_provider(provider, url):
        if provider != "auto":
            return provider
        if not url:
            return "stdout"
        parsed_url = urlparse(url)
        hostname = (parsed_url.hostname or "").lower()
        if not hostname:
            return "stdout"
        if (
            hostname == "discord.com"
            or hostname.endswith(".discord.com")
            or hostname == "discordapp.com"
            or hostname.endswith(".discordapp.com")
        ):
            return "discord"
        if hostname == "slack.com" or hostname.endswith(".slack.com"):
            return "slack"
        return "stdout"

    # ------------------------------------------------------------------
    # Slack Block Kit builder
    # ------------------------------------------------------------------
    def _build_slack_block_kit(self, severity, title, message):
        emoji = SEVERITY_EMOJI.get(severity, "\u26AA")
        header_text = f"{emoji} [{severity.upper()}] {title}"
        grafana_url = os.environ.get("GRAFANA_BASE_URL", "http://grafana.internal")
        jaeger_url = os.environ.get("JAEGER_BASE_URL", "http://jaeger.internal")
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": header_text},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Message:*\n```\n{message}\n```"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "\U0001F4CA Xem tren Grafana"},
                            "url": grafana_url,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "\U0001F575 Trace tren Jaeger"},
                            "url": jaeger_url,
                        },
                    ],
                },
            ]
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def send(self, dedup_key: str, severity: str, rule_id: str, message: str,
             fields=None) -> bool:
        """
        Buffer an alert after passing the per-rule cooldown gate.

        dedup_key format: "<rule_id>:<service_name>"
        fields: list of (name, value, inline) tuples for Discord embed structured fields.
        Returns True if the alert passed the cooldown gate and was buffered.
        """
        now = time.time()
        last = self._last_sent.get(dedup_key, 0)
        if now - last < self.cooldown:
            log.debug("cooldown active for %s, skipping", dedup_key)
            return False

        self._last_sent[dedup_key] = now

        # Parse service from dedup_key ("<rule_id>:<service>")
        parts = dedup_key.split(":", 1)
        service = parts[1] if len(parts) == 2 else "unknown"

        fp = _fingerprint(service, now, self.bucket_seconds)
        entry = {
            "rule_id": rule_id,
            "dedup_key": dedup_key,
            "severity": severity,
            "message": message,
            "fields": fields or [],
            "ts": now,
            "service": service,
        }
        self._pending.setdefault(fp, []).append(entry)
        log.debug("buffered alert fingerprint=%s rule=%s", fp, rule_id)
        return True

    def flush(self) -> int:
        """
        Dispatch all buffered alerts, grouped by fingerprint (K3 dedup).

        Each fingerprint -> ONE webhook message listing all triggered rules.
        Returns the number of messages dispatched.
        """
        if not self._pending:
            return 0

        dispatched = 0
        for fp, entries in self._pending.items():
            sev_order = {"critical": 0, "warning": 1, "info": 2}
            entries_sorted = sorted(entries, key=lambda e: sev_order.get(e["severity"], 9))
            top_sev = entries_sorted[0]["severity"]
            service = entries_sorted[0]["service"]
            emoji = SEVERITY_EMOJI.get(top_sev, "\u26AA")
            stamp = datetime.now(TZ_VN).strftime("%Y-%m-%d %H:%M:%S (gio VN)")

            # Build grouped message body
            rule_lines = []
            for e in entries_sorted:
                rule_emoji = SEVERITY_EMOJI.get(e["severity"], "\u26AA")
                rule_lines.append(
                    f"  {rule_emoji} [{e['severity'].upper()}] {e['rule_id']}\n"
                    f"     {e['message']}"
                )

            header = (
                f"{emoji} [GROUPED ALERT] service={service} | "
                f"{len(entries)} rule(s) triggered | detected: {stamp}"
            )
            body = "\n".join(rule_lines)
            text = f"{header}\n{body}"

            webhook_url = (
                self.webhook_critical if top_sev == "critical"
                else (self.webhook_info or self.webhook_critical)
            )

            try:
                if self.provider == "slack" and webhook_url:
                    self._post(webhook_url, self._build_slack_block_kit(top_sev, header, body))
                elif self.provider == "discord" and webhook_url:
                    # Merge all fields from all entries for the grouped embed
                    all_fields = []
                    for e in entries_sorted:
                        for name, value, inline in e["fields"]:
                            all_fields.append({"name": name, "value": value, "inline": inline})
                    embed = {
                        "title": header,
                        "description": body,
                        "color": SEVERITY_COLOR.get(top_sev, 0x99AAB5),
                        "timestamp": datetime.now(TZ_VN).isoformat(),
                        "footer": {
                            "text": (
                                f"AIOps Detector \u00b7 fingerprint={fp} \u00b7 "
                                f"{len(entries)} rules \u00b7 cooldown {self.cooldown}s"
                            )
                        },
                    }
                    if all_fields:
                        embed["fields"] = all_fields
                    self._post(webhook_url, {"embeds": [embed]})
                else:  # stdout
                    print(f"\n===== GROUPED ALERT =====\n{text}\n=========================\n",
                          flush=True)
                log.info("dispatched grouped alert fingerprint=%s rules=%d severity=%s",
                         fp, len(entries), top_sev)
                dispatched += 1
            except Exception as exc:  # noqa: BLE001
                log.error("dispatch failed for fingerprint=%s: %s", fp, exc)
                print(f"\n===== GROUPED ALERT (webhook FAILED, fallback stdout) =====\n{text}\n",
                      flush=True)

            # Write each alert to history log for G7 co-occurrence analysis
            for e in entries:
                _append_history({
                    "ts": e["ts"],
                    "rule_id": e["rule_id"],
                    "service": e["service"],
                    "severity": e["severity"],
                    "fingerprint": fp,
                })

        self._pending.clear()
        return dispatched

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _post(self, url, payload):
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
