#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fallback_retry.py - Unit/Integration tests for LLM Fallback Routing & Retry/Timeout
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import logging
import random

# Ensure project paths are imported correctly
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "techx-corp-platform", "src", "product-reviews"))

# Fix encoding for Windows terminals (cp1258, etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# We must set dummy env vars that product_reviews_server requires at import time
os.environ["OTEL_SERVICE_NAME"] = "test-product-reviews"
os.environ["PRODUCT_REVIEWS_PORT"] = "8000"
os.environ["PRODUCT_CATALOG_ADDR"] = "localhost:50051"
os.environ["LLM_HOST"] = "localhost"
os.environ["LLM_PORT"] = "8000"
os.environ["LLM_BASE_URL"] = "http://localhost:8000/v1"
os.environ["DB_CONNECTION_STRING"] = "postgresql://user:pass@localhost:5432/db"

import product_reviews_server
from botocore.exceptions import ClientError, ReadTimeoutError

# Disable logging clutter during test
logging.getLogger("main").setLevel(logging.ERROR)

class TestFallbackRetry(unittest.TestCase):
    def setUp(self):
        # Reset global state and env vars
        os.environ["LLM_REVIEWS_MAIN_MODEL"] = "amazon.nova-lite-v1:0"
        os.environ["LLM_REVIEWS_FALLBACK_MODEL"] = "amazon.nova-micro-v1:0"
        os.environ["LLM_REVIEWS_MAX_RETRIES"] = "2"
        os.environ["LLM_REVIEWS_FALLBACK_RETRIES"] = "1"
        os.environ["LLM_MOCK_ENABLED"] = "false"
        product_reviews_server.bedrock_primary_client = MagicMock()
        product_reviews_server.bedrock_fallback_client = MagicMock()
        product_reviews_server.valkey_client = None # Skip cache writes
        # Reset circuit breaker (B2) — cac scenario exhaust primary se tang failures,
        # khong reset la scenario sau bi bypass oan (test pollution).
        product_reviews_server._cb_state["failures"] = 0
        product_reviews_server._cb_state["open_until"] = 0.0

        # Mock feature flags
        self.flags = {
            "llmReviewsCacheEnabled": False,
            "llmReviewsFallbackEnabled": True,
            "llmRateLimitError": False
        }
        product_reviews_server.check_feature_flag = lambda name, default=False: self.flags.get(name, default)

        # Mock guardrails
        self.patcher1 = patch('product_reviews_server.apply_guardrail_input', return_value=(False, "Tóm tắt review"))
        self.patcher2 = patch('product_reviews_server.apply_guardrail_output', return_value=(False, "Summary output"))
        self.patcher1.start()
        self.patcher2.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()

    def test_scenario_1_success_primary(self):
        """1. Success Flow: Calls primary model successfully on first attempt."""
        mock_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": "Sản phẩm tốt, đáng mua."}]}}
        }
        product_reviews_server.bedrock_primary_client.converse.return_value = mock_response

        res = product_reviews_server.get_ai_assistant_response("PROD123", "Tóm tắt review")
        self.assertEqual(res.response, "Sản phẩm tốt, đáng mua.")
        product_reviews_server.bedrock_primary_client.converse.assert_called_once()
        product_reviews_server.bedrock_fallback_client.converse.assert_not_called()

    def test_scenario_2_fallback_routing(self):
        """2. Fallback Flow: ThrottlingException on primary, triggers fallback model, which succeeds."""
        # Mock Throttling error for primary client
        error_response = {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate limit exceeded"
            },
            "ResponseMetadata": {"HTTPStatusCode": 429}
        }
        primary_err = ClientError(error_response, "converse")
        product_reviews_server.bedrock_primary_client.converse.side_effect = primary_err

        # Mock success for fallback client
        fallback_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": "Bản tóm tắt từ model dự phòng (Nova Micro)."}]}}
        }
        product_reviews_server.bedrock_fallback_client.converse.return_value = fallback_response

        # Disable sleep jitter/waiting to run tests fast
        with patch("time.sleep", return_value=None):
            res = product_reviews_server.get_ai_assistant_response("PROD123", "Tóm tắt review")

        self.assertEqual(res.response, "Bản tóm tắt từ model dự phòng (Nova Micro).")
        # Primary should be tried 3 times total (1 initial + 2 retries)
        self.assertEqual(product_reviews_server.bedrock_primary_client.converse.call_count, 3)
        # Fallback should succeed on first try
        product_reviews_server.bedrock_fallback_client.converse.assert_called_once()

    def test_scenario_3_all_fail_mock_fallback(self):
        """3. All-fail Flow: Both primary and fallback models fail, returns default Mock Summary."""
        error_response = {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate limit exceeded"
            },
            "ResponseMetadata": {"HTTPStatusCode": 429}
        }
        primary_err = ClientError(error_response, "converse")
        product_reviews_server.bedrock_primary_client.converse.side_effect = primary_err
        product_reviews_server.bedrock_fallback_client.converse.side_effect = primary_err

        with patch("time.sleep", return_value=None):
            res = product_reviews_server.get_ai_assistant_response("PROD123", "Tóm tắt review")

        # Must return the friendly Mock Summary
        self.assertTrue("Không thể tạo tóm tắt" in res.response or "Không thể" in res.response or "tham khảo" in res.response)

    def test_scenario_4_dynamic_deadline_fail_fast(self):
        """4. Dynamic Deadlines Flow: remaining time < fallback timeout, fails fast without Bedrock calls."""
        mock_context = MagicMock()
        mock_context.time_remaining.return_value = 1.5 # Less than fallback timeout (2s)

        res = product_reviews_server.get_ai_assistant_response("PROD123", "Tóm tắt review", context=mock_context)
        self.assertTrue("Không thể tạo tóm tắt" in res.response or "Không thể" in res.response or "tham khảo" in res.response)
        product_reviews_server.bedrock_primary_client.converse.assert_not_called()
        product_reviews_server.bedrock_fallback_client.converse.assert_not_called()

    def test_scenario_5_circuit_breaker_bypass(self):
        """5. Circuit Breaker (B2): open sau N loi primary lien tiep -> bypass primary, di fallback.
        Breaker theo loi quan sat duoc — KHONG doc co su co flagd (AI_FEATURE §3)."""
        import time as _time
        product_reviews_server._cb_state["failures"] = product_reviews_server.CB_FAILURE_THRESHOLD
        product_reviews_server._cb_state["open_until"] = _time.time() + 30

        fallback_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": "Bản tóm tắt từ model dự phòng (Nova Micro) sau bypass."}]}}
        }
        product_reviews_server.bedrock_fallback_client.converse.return_value = fallback_response

        res = product_reviews_server.get_ai_assistant_response("PROD123", "Tóm tắt review")
        self.assertEqual(res.response, "Bản tóm tắt từ model dự phòng (Nova Micro) sau bypass.")
        product_reviews_server.bedrock_primary_client.converse.assert_not_called()
        product_reviews_server.bedrock_fallback_client.converse.assert_called_once()

    def test_scenario_6_circuit_breaker_resets_on_success(self):
        """6. Circuit Breaker: primary thanh cong -> failures ve 0 (khong mo oan sau do)."""
        product_reviews_server._cb_state["failures"] = product_reviews_server.CB_FAILURE_THRESHOLD - 1
        ok_response = {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": "Summary OK."}]}}
        }
        product_reviews_server.bedrock_primary_client.converse.return_value = ok_response
        res = product_reviews_server.get_ai_assistant_response("PROD123", "Tóm tắt review")
        self.assertEqual(res.response, "Summary OK.")
        self.assertEqual(product_reviews_server._cb_state["failures"], 0)

def measure_before_after(base_url="http://localhost:8080", n=30):
    """DO THAT truoc-sau tren stack DANG CHAY — thay ban mo phong random cu (review B5:
    "so khong tai tao duoc coi nhu chua chung minh"; ti le loi 22%/10% truoc day la tu dat).

    Phuong phap: bam su co that qua flagd (`llmRateLimitError=on`, mock LLM tra 429 ~50%),
    ban n request that toi endpoint storefront, phan loai response:
      - BEFORE (fallback OFF qua flag `llmReviewsFallbackEnabled`): ti le request khong co summary that
      - AFTER  (fallback ON): ti le tuong tu — chenh lech = gia tri thuc cua fallback routing
    Yeu cau: `docker compose up` (product-reviews build tu source). Khong co stack -> DUNG,
    khong in so — ham nay khong co duong mo phong.
    """
    import json as _json
    import urllib.request as _rq
    import urllib.error as _er

    flagd_file = os.path.join(os.path.dirname(__file__), "../../../techx-corp-platform/src/flagd/demo.flagd.json")
    mock_marker = "không thể tạo tóm tắt"

    def _set_flag(name, variant):
        cfg = _json.load(open(flagd_file))
        cfg["flags"][name]["defaultVariant"] = variant
        _json.dump(cfg, open(flagd_file, "w"), indent=2, ensure_ascii=False)

    def _ask():
        req = _rq.Request(f"{base_url}/api/product-ask-ai-assistant/L9ECAV7KIM",
                          data=b'{"question":"Can you summarize the product reviews?"}',
                          headers={"Content-Type": "application/json"})
        try:
            body = _rq.urlopen(req, timeout=60).read().decode()
            return "mock" if mock_marker in body.lower() else "real"
        except Exception:
            return "error"

    # Fail-fast neu stack khong chay — TUYET DOI khong fallback sang mo phong
    try:
        _rq.urlopen(base_url, timeout=5)
    except Exception:
        print("[measure_before_after] Stack chua chay (docker compose up truoc). "
              "Khong do duoc thi khong in so — xem docstring.")
        return None

    results = {}
    _set_flag("llmRateLimitError", "on")
    for label, variant in [("BEFORE (fallback off)", "off"), ("AFTER (fallback on)", "on")]:
        _set_flag("llmReviewsFallbackEnabled", variant)
        time_module = __import__("time"); time_module.sleep(3)  # flagd file-watch reload
        counts = {"real": 0, "mock": 0, "error": 0}
        for _ in range(n):
            counts[_ask()] += 1
        results[label] = counts
        no_real = (counts["mock"] + counts["error"]) / n
        print(f"{label}: n={n} real={counts['real']} mock={counts['mock']} error={counts['error']}"
              f" -> ti le KHONG co summary that: {no_real:.1%}")
    _set_flag("llmRateLimitError", "off")
    _set_flag("llmReviewsFallbackEnabled", "on")
    return results

if __name__ == "__main__":
    measure_before_after()
    unittest.main()
