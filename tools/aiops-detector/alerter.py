# TF1-53 [AIOps-W1-T5] - Gui canh bao ra kenh on-call (Slack/Discord) + dedup/cooldown.
# Ho tro provider: slack | discord | stdout | auto (doan tu URL).
# stdout dung khi test/demo khong co webhook (giong tinh than dry-run cua TF1-50).
import time
import logging
import requests

log = logging.getLogger("aiops.alerter")

SEVERITY_EMOJI = {"critical": "\U0001F534", "warning": "\U0001F7E1", "info": "⚪"}


class Alerter:
    def __init__(self, webhook_url, provider="auto", cooldown_seconds=600, timeout=5):
        self.webhook_url = webhook_url
        self.cooldown = cooldown_seconds
        self.timeout = timeout
        self.provider = self._resolve_provider(provider, webhook_url)
        self._last_sent = {}  # dedup key -> epoch

    @staticmethod
    def _resolve_provider(provider, url):
        if provider != "auto":
            return provider
        if not url:
            return "stdout"
        if "discord.com" in url or "discordapp.com" in url:
            return "discord"
        if "slack.com" in url or "hooks.slack" in url:
            return "slack"
        return "stdout"

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
        text = f"{emoji} [{severity.upper()}] {title}\n{message}\nphat hien luc: {stamp}"

        try:
            if self.provider == "slack":
                self._post({"text": text})
            elif self.provider == "discord":
                self._post({"content": text})
            else:  # stdout
                print(f"\n===== ALERT =====\n{text}\n=================\n", flush=True)
            log.info("da gui alert [%s] %s", severity, dedup_key)
            return True
        except Exception as exc:  # noqa: BLE001 - khong duoc de alerter lam chet detector
            log.error("gui alert that bai (%s): %s", dedup_key, exc)
            # In ra stdout de khong mat canh bao khi webhook loi
            print(f"\n===== ALERT (webhook FAILED, fallback stdout) =====\n{text}\n", flush=True)
            return False

    def _post(self, payload):
        resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
