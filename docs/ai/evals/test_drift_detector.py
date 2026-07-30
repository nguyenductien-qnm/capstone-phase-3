#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_drift_detector.py — [DIRECTIVE #27] Unit tests for drift detection
"""
import json
import os
import sys
import time
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from drift_detector import DriftDetector, generate_baseline, _psi, DEFAULT_BASELINE_PATH
from drift_replay import replay, _stable_series, _shifted_series


@pytest.fixture(scope="module")
def baseline_path(tmp_path_factory):
    """Generate a fresh baseline for tests."""
    tmp = tmp_path_factory.mktemp("drift_test")
    bl_path = str(tmp / "baseline_snapshot.json")
    dataset_path = os.path.join(_HERE, "golden_dataset.json")
    if os.path.exists(dataset_path):
        bl = generate_baseline(dataset_path)
    else:
        # Fallback minimal baseline for CI without full dataset
        bl = {
            "review_summary": {
                "keyword_accuracy_distribution": [0.8, 0.82, 0.79, 0.83, 0.81, 0.80, 0.82, 0.81, 0.80, 0.83],
                "keyword_accuracy_mean": 0.811,
                "word_count_mean_distribution": [45.0, 47.0, 44.0, 48.0, 46.0, 45.0, 47.0, 46.0, 45.0, 48.0],
                "word_count_mean_mean": 46.1,
                "fallback_rate_distribution": [0.0]*10,
                "fallback_rate_mean": 0.0,
                "hallucination_risk_rate_distribution": [0.0]*10,
                "hallucination_risk_rate_mean": 0.0,
            },
            "copilot": {
                "task_success_rate_distribution": [0.85, 0.88, 0.87, 0.90, 0.86, 0.88, 0.89, 0.87, 0.88, 0.90],
                "task_success_rate_mean": 0.878,
                "abstention_rate_distribution": [0.05, 0.06, 0.07, 0.05, 0.06, 0.05, 0.07, 0.06, 0.05, 0.06],
                "abstention_rate_mean": 0.058,
                "fallback_rate_distribution": [0.02, 0.03, 0.02, 0.01, 0.02, 0.03, 0.02, 0.01, 0.02, 0.02],
                "fallback_rate_mean": 0.02,
            }
        }
    with open(bl_path, "w") as f:
        json.dump(bl, f)
    return bl_path


# ─────────────────────────────────────────────────────────────
# PSI unit tests
# ─────────────────────────────────────────────────────────────
def test_psi_identical_distributions():
    """Same distribution → PSI = 0."""
    vals = [0.8, 0.82, 0.79, 0.83, 0.81, 0.80, 0.82, 0.81, 0.80, 0.83]
    psi = _psi(vals, vals)
    assert psi < 0.05, f"Identical distributions should have PSI near 0, got {psi}"


def test_psi_very_different_distributions():
    """Very different distributions → PSI > 0.20."""
    baseline = [0.8, 0.82, 0.79, 0.83, 0.81, 0.80, 0.82, 0.81, 0.80, 0.83]
    current = [0.20, 0.25, 0.18, 0.22, 0.15, 0.20, 0.23, 0.19, 0.21, 0.20]
    psi = _psi(baseline, current)
    assert psi > 0.20, f"Very different distributions should have PSI > 0.20, got {psi}"


def test_psi_empty_inputs():
    """Empty inputs → PSI = 0, no crash."""
    assert _psi([], []) == 0.0
    assert _psi([0.8, 0.9], []) == 0.0


# ─────────────────────────────────────────────────────────────
# Drift detector unit tests
# ─────────────────────────────────────────────────────────────
def test_stable_series_no_drift(baseline_path, tmp_path):
    """Stable series near baseline → verdict = STABLE."""
    series = _stable_series(surface="review_summary", n=20, baseline_path=baseline_path)
    result = replay(series, baseline_path, state_path=str(tmp_path / "state.json"))
    assert result["verdict"] == "STABLE", (
        f"Stable series should not flag drift, got: {result['drift_events']}"
    )


def test_shifted_series_flags_drift(baseline_path, tmp_path):
    """Strongly shifted series -> DRIFT_DETECTED."""
    series = _shifted_series(
        surface="review_summary", n=20,
        pre_mean=0.82, post_mean=0.20,  # big drop
        shift_at=12,
        baseline_path=baseline_path
    )
    result = replay(series, baseline_path, state_path=str(tmp_path / "state.json"))
    assert result["verdict"] == "DRIFT_DETECTED", (
        "Shifted series should flag drift"
    )
    assert result["first_drift_at_snapshot"] is not None
    # Drift should be detected before or shortly after the shift point
    # (sliding window of 10 + min 5 means detection can be early if
    #  the generated series also differs from baseline word_count mean)
    assert result["first_drift_at_snapshot"] <= 18, (
        f"Drift detected too late: {result['first_drift_at_snapshot']}"
    )


def test_no_false_alarm_on_natural_variance(baseline_path, tmp_path):
    """Small natural variance (±3%) → STABLE, no false alarm."""
    series = _stable_series(surface="review_summary", n=20, std=0.03, baseline_path=baseline_path)
    result = replay(series, baseline_path, state_path=str(tmp_path / "state.json"))
    assert result["verdict"] == "STABLE", (
        f"Natural variance should not trigger drift, events: {result['drift_events']}"
    )


def test_copilot_surface_drift(baseline_path, tmp_path):
    """Copilot surface drift detection works too."""
    series = _shifted_series(
        surface="copilot", n=20,
        pre_mean=0.88, post_mean=0.30,
        shift_at=10,
        baseline_path=baseline_path
    )
    result = replay(series, baseline_path, state_path=str(tmp_path / "state.json"))
    assert result["verdict"] == "DRIFT_DETECTED"
    if result["drift_events"]:
        drifted = result["drift_events"][0]["drifted_metrics"]
        # At least one copilot metric should be flagged
        assert any(m in drifted for m in ["task_success_rate", "abstention_rate", "fallback_rate"])


def test_insufficient_data_no_drift(baseline_path, tmp_path):
    """Only 3 snapshots (< MIN_WINDOW=5) → no drift flag, not enough data."""
    series = _shifted_series(surface="review_summary", n=3, pre_mean=0.82, post_mean=0.20, baseline_path=baseline_path)
    result = replay(series, baseline_path, state_path=str(tmp_path / "state.json"))
    # With only 3 samples, detector should not confirm drift
    assert result["verdict"] == "STABLE"


def test_drift_report_has_evidence(baseline_path, tmp_path):
    """Drift report must include per-metric evidence (PSI, means)."""
    series = _shifted_series(surface="review_summary", n=20, pre_mean=0.82, post_mean=0.20, baseline_path=baseline_path)
    result = replay(series, baseline_path, state_path=str(tmp_path / "state.json"))

    if result["verdict"] == "DRIFT_DETECTED":
        event = result["drift_events"][0]
        assert "drifted_metrics" in event
        assert len(event["drifted_metrics"]) > 0
        assert "details" in event
        for metric in event["drifted_metrics"]:
            detail = event["details"].get(metric, {})
            assert "psi" in detail
            assert "baseline_mean" in detail
            assert "current_mean" in detail
            assert detail["severity"] in ("warn", "drift")


def test_generate_baseline_from_dataset():
    """generate_baseline() produces valid structure."""
    dataset_path = os.path.join(_HERE, "golden_dataset.json")
    if not os.path.exists(dataset_path):
        pytest.skip("golden_dataset.json not available")
    bl = generate_baseline(dataset_path)
    assert "review_summary" in bl
    assert "copilot" in bl
    assert "keyword_accuracy_distribution" in bl["review_summary"]
    assert len(bl["review_summary"]["keyword_accuracy_distribution"]) > 0
