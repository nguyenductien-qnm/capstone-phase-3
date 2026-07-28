import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "shopping-copilot"))

import ml_guard_client as m


def test_output_guard_fails_closed_when_service_is_unavailable(monkeypatch):
    class BrokenStub:
        def CheckOutput(self, *args, **kwargs):
            raise RuntimeError("ml-guard down")

    monkeypatch.setattr(m, "_get_stub", lambda: BrokenStub())
    blocked, sanitized = m.apply_guardrail_output(None, "Pin dùng 24 giờ", "review không nói pin", "Pin dùng bao lâu?")
    assert blocked is True
    assert sanitized == "Pin dùng 24 giờ"
