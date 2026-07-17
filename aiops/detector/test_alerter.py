from unittest.mock import patch, MagicMock

from alerter import Alerter, SEVERITY_COLOR


def _make_discord_alerter():
    # provider="auto" doan tu URL webhook (xem _resolve_provider) - dung URL discord.com that
    # de test di dung nhanh, khong can set provider="discord" tay.
    a = Alerter(provider="auto", cooldown_seconds=600)
    a.webhook_critical = "https://discord.com/api/webhooks/123/abc"
    a.webhook_info = a.webhook_critical
    a.provider = "discord"
    return a


@patch("alerter.requests.post")
def test_discord_embed_has_color_and_fields(mock_post):
    mock_post.return_value = MagicMock(status_code=204, raise_for_status=lambda: None)
    a = _make_discord_alerter()

    fields = [
        ("🎯 Dịch vụ", "cart", True),
        ("📊 Giá trị đo / Ngưỡng SLO", "1.5000 / 1.0", True),
        ("🔍 Phương pháp phát hiện", "Static (val=1.5000 > th=1.0)", False),
    ]
    sent = a.send("rule:cart", "critical", "latency-p95-high", "p95 latency > 1s", fields=fields)

    assert sent is True
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    payload = kwargs["json"]
    embed = payload["embeds"][0]

    assert embed["color"] == SEVERITY_COLOR["critical"]
    assert embed["description"] == "p95 latency > 1s"
    assert "latency-p95-high" in embed["title"]
    assert embed["fields"] == [
        {"name": "🎯 Dịch vụ", "value": "cart", "inline": True},
        {"name": "📊 Giá trị đo / Ngưỡng SLO", "value": "1.5000 / 1.0", "inline": True},
        {"name": "🔍 Phương pháp phát hiện", "value": "Static (val=1.5000 > th=1.0)", "inline": False},
    ]
    assert "content" not in payload  # khong con fallback text phang


@patch("alerter.requests.post")
def test_discord_embed_without_fields_still_sends(mock_post):
    """log_clustering.py goi alerter.send() khong truyen fields - phai van chay duoc (backward-compat)."""
    mock_post.return_value = MagicMock(status_code=204, raise_for_status=lambda: None)
    a = _make_discord_alerter()

    sent = a.send("cluster:1", "warning", "new-log-template", "Phat hien template log moi")

    assert sent is True
    payload = mock_post.call_args.kwargs["json"]
    embed = payload["embeds"][0]
    assert embed["color"] == SEVERITY_COLOR["warning"]
    assert "fields" not in embed
