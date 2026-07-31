import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "shopping-copilot"))

import ml_guard_client as m


def test_output_guard_fails_open_when_service_is_unavailable(monkeypatch):
    class BrokenStub:
        def CheckOutput(self, *args, **kwargs):
            raise RuntimeError("ml-guard down")

    monkeypatch.setattr(m, "_get_stub", lambda: BrokenStub())
    blocked, sanitized = m.apply_guardrail_output(None, "Pin dùng 24 giờ", "review không nói pin", "Pin dùng bao lâu?")
    assert blocked is False
    assert sanitized == "Pin dùng 24 giờ"


def test_redact_pii_does_not_merge_prices_across_lines():
    text = "1. Optical Tube Assembly - Price: $3599.00.\n2. Solar Imager - Price: $175.00"
    assert m.redact_pii(text) == text


def test_redact_pii_still_masks_spaced_phone_numbers():
    assert m.redact_pii("Call +84 912 345 678 today") == "Call [REDACTED_PHONE] today"
