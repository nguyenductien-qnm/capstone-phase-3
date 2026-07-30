"""Unit tests for product-reviews/eval_guardrails.py (TF1-89)."""

import json
import os
import subprocess
import sys
import tempfile

import eval_guardrails


def test_load_dataset_default():
    dataset = eval_guardrails.load_dataset()
    assert isinstance(dataset, list)
    assert len(dataset) > 0


def test_load_dataset_custom_file():
    custom_data = [
        {
            "id": "custom_1",
            "type": "safe",
            "text": "Great product!",
            "expected_malicious": False,
            "expected_pii": False,
            "expected_leak": False,
        }
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(custom_data, f)
        temp_path = f.name

    try:
        loaded = eval_guardrails.load_dataset(temp_path)
        assert loaded == custom_data
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_cli_cases_flag():
    custom_data = [
        {
            "id": "custom_safe",
            "type": "safe",
            "text": "This telescope is awesome.",
            "expected_malicious": False,
            "expected_pii": False,
            "expected_leak": False,
        }
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(custom_data, f)
        temp_path = f.name

    try:
        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), "eval_guardrails.py"),
            "--cases",
            temp_path,
            "--mode=deterministic",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "custom_safe" in res.stdout
        assert "Grand Total (L1 + Hallucination): 1/1 tests passed." in res.stdout
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
