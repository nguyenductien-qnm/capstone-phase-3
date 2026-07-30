from unittest.mock import patch, MagicMock

from alerter import Alerter, SEVERITY_COLOR


def _make_discord_alerter():
    # provider="auto" infers from webhook URL — use a real discord.com URL
    # to hit the discord branch without setting provider="discord" manually.
    a = Alerter(provider="auto", cooldown_seconds=0)  # cooldown=0 for test isolation
    a.webhook_critical = "https://discord.com/api/webhooks/123/abc"
    a.webhook_info = a.webhook_critical
    a.provider = "discord"
    return a


@patch("alerter.requests.post")
def test_discord_embed_has_color_and_fields(mock_post):
    mock_post.return_value = MagicMock(status_code=204, raise_for_status=lambda: None)
    a = _make_discord_alerter()

    fields = [
        ("\U0001F3AF Dịch vụ", "cart", True),
        ("\U0001F4CA Giá trị đo / Ngưỡng SLO", "1.5000 / 1.0", True),
        ("\U0001F50D Phương pháp phát hiện", "Static (val=1.5000 > th=1.0)", False),
    ]
    sent = a.send("rule:cart", "critical", "latency-p95-high", "p95 latency > 1s", fields=fields)
    assert sent is True

    # K3: send() buffers — flush() dispatches the grouped message
    dispatched = a.flush()
    assert dispatched == 1

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    embed = payload["embeds"][0]

    assert embed["color"] == SEVERITY_COLOR["critical"]
    # Grouped message: description contains the rule message, title contains service info
    assert "p95 latency > 1s" in embed["description"]
    assert "latency-p95-high" in embed["description"]
    # Fields from the alert entry are merged into the grouped embed
    assert any(f["name"] == "\U0001F3AF Dịch vụ" and f["value"] == "cart"
               for f in embed.get("fields", []))
    assert "content" not in payload  # no flat text fallback


@patch("alerter.requests.post")
def test_discord_embed_without_fields_still_sends(mock_post):
    """log_clustering.py calls alerter.send() without fields — must work (backward-compat)."""
    mock_post.return_value = MagicMock(status_code=204, raise_for_status=lambda: None)
    a = _make_discord_alerter()

    sent = a.send("cluster:1", "warning", "new-log-template", "Phat hien template log moi")
    assert sent is True

    # K3: must flush to dispatch
    dispatched = a.flush()
    assert dispatched == 1

    payload = mock_post.call_args.kwargs["json"]
    embed = payload["embeds"][0]
    assert embed["color"] == SEVERITY_COLOR["warning"]
    # No fields passed — embed should have no fields key (or empty)
    assert not embed.get("fields")
