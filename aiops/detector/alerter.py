# TF1-53 [AIOps-W1-T5] - Gui canh bao ra kenh on-call (Slack/Discord) + dedup/cooldown.
# Ho tro provider: slack | discord | stdout | auto (doan tu URL).
# stdout dung khi test/demo khong co webhook (giong tinh than dry-run cua TF1-50).
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import requests

log = logging.getLogger("aiops.alerter")

# Gio hien thi tren alert: pod chay TZ=UTC nhung on-call doc gio VN (review 16/07:
# alert ghi 06:42 trong khi Discord hien 13:42 -> gay nham lan khi doi chieu).
# Fixed offset +7 (VN khong co DST) - khong phu thuoc goi tzdata (python:slim khong co).
TZ_VN = timezone(timedelta(hours=7))

SEVERITY_EMOJI = {"critical": "\U0001F534", "warning": "\U0001F7E1", "info": "⚪"}
# Mau brand Discord theo severity (decimal, dung cho field `color` cua embed).
SEVERITY_COLOR = {"critical": 0xED4245, "warning": 0xFEE75C, "info": 0x5865F2}


class Alerter:
    def __init__(self, provider="auto", cooldown_seconds=600, timeout=5):
        self.webhook_critical = os.environ.get("AIOPS_SLACK_WEBHOOK_CRITICAL")
        self.webhook_info = os.environ.get("AIOPS_SLACK_WEBHOOK_INFO")
        self.cooldown = cooldown_seconds
        self.timeout = timeout
        
        # Resolve provider based on the critical webhook URL (or fallback to info)
        test_url = self.webhook_critical or self.webhook_info
        self.provider = self._resolve_provider(provider, test_url)
        self._last_sent = {}  # dedup key -> epoch

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

    def _build_slack_block_kit(self, severity, title, message):
        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        header_text = f"{emoji} [{severity.upper()}] {title}"
        grafana_url = os.environ.get("GRAFANA_BASE_URL", "http://grafana.internal")
        jaeger_url = os.environ.get("JAEGER_BASE_URL", "http://jaeger.internal")
        
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header_text
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Message:*\n```\n{message}\n```"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📊 Xem trên Grafana"
                            },
                            "url": grafana_url
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🕵️ Trace trên Jaeger"
                            },
                            "url": jaeger_url
                        }
                    ]
                }
            ]
        }

    def send(self, dedup_key, severity, title, message, fields=None):
        """Gui alert neu khong con trong cooldown. Return True neu da gui.

        `fields`: list tuple (name, value, inline) - du lieu that tach rieng
        (service, phuong phap phat hien, gia tri do...) de Discord embed hien
        thanh field ro rang thay vi nhoi het vao 1 doan text (review 17/07).
        """
        now = time.time()
        last = self._last_sent.get(dedup_key, 0)
        if now - last < self.cooldown:
            log.debug("cooldown active cho %s, bo qua", dedup_key)
            return False
        self._last_sent[dedup_key] = now

        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        stamp = datetime.now(TZ_VN).strftime("%Y-%m-%d %H:%M:%S (giờ VN)")
        text_fallback = f"{emoji} [{severity.upper()}] {title}\n{message}\nphát hiện lúc: {stamp}"

        webhook_url = self.webhook_critical if severity == "critical" else (self.webhook_info or self.webhook_critical)

        try:
            if self.provider == "slack" and webhook_url:
                payload = self._build_slack_block_kit(severity, title, message)
                self._post(webhook_url, payload)
            elif self.provider == "discord" and webhook_url:
                embed = {
                    "title": f"{emoji} [{severity.upper()}] {title}",
                    "description": message,
                    "color": SEVERITY_COLOR.get(severity, 0x99AAB5),
                    "timestamp": datetime.now(TZ_VN).isoformat(),
                    "footer": {"text": f"AIOps Detector · dedup={dedup_key} · cooldown {self.cooldown}s"},
                }
                if fields:
                    embed["fields"] = [
                        {"name": name, "value": value, "inline": inline}
                        for name, value, inline in fields
                    ]
                self._post(webhook_url, {"embeds": [embed]})
            else:  # stdout
                print(f"\n===== ALERT =====\n{text_fallback}\n=================\n", flush=True)
            log.info("da gui alert [%s] %s", severity, dedup_key)
            return True
        except Exception as exc:  # noqa: BLE001 - khong duoc de alerter lam chet detector
            log.error("gui alert that bai (%s): %s", dedup_key, exc)
            # In ra stdout de khong mat canh bao khi webhook loi
            print(f"\n===== ALERT (webhook FAILED, fallback stdout) =====\n{text_fallback}\n", flush=True)
            return False

    def _post(self, url, payload):
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
