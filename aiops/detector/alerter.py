# TF1-53 [AIOps-W1-T5] - Gui canh bao ra kenh on-call (Slack/Discord) + dedup/cooldown.
# Ho tro provider: slack | discord | stdout | auto (doan tu URL).
# stdout dung khi test/demo khong co webhook (giong tinh than dry-run cua TF1-50).
import os
import time
import logging
from urllib.parse import urlparse
import requests

log = logging.getLogger("aiops.alerter")

SEVERITY_EMOJI = {"critical": "\U0001F534", "warning": "\U0001F7E1", "info": "⚪"}


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

    def send(self, dedup_key, severity, title, message):
        """Gui alert neu khong con trong cooldown. Return True neu da gui."""
        now = time.time()
        last = self._last_sent.get(dedup_key, 0)
        if now - last < self.cooldown:
            log.debug("cooldown active cho %s, bo qua", dedup_key)
            return False
        self._last_sent[dedup_key] = now

        emoji = SEVERITY_EMOJI.get(severity, "⚪")
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        text_fallback = f"{emoji} [{severity.upper()}] {title}\n{message}\nphat hien luc: {stamp}"
        
        webhook_url = self.webhook_critical if severity == "critical" else (self.webhook_info or self.webhook_critical)

        try:
            if self.provider == "slack" and webhook_url:
                payload = self._build_slack_block_kit(severity, title, message)
                self._post(webhook_url, payload)
            elif self.provider == "discord" and webhook_url:
                # Discord doesn't support Slack Block Kit natively via webhook unless mapped, fallback to content
                self._post(webhook_url, {"content": text_fallback})
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
