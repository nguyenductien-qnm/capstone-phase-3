#!/usr/bin/env python3
"""Simulate drift: feed 6 eval cycles with degraded metrics to trigger DRIFT_DETECTED."""
import sys
sys.path.insert(0, "docs/ai/evals")
from drift_detector import DriftDetector, DEFAULT_BASELINE_PATH

detector = DriftDetector(DEFAULT_BASELINE_PATH)

# keyword_accuracy tụt dần từ 0.81 (baseline) xuống 0.25
bad_metrics = [
    {"keyword_accuracy": 0.45, "word_count_mean": 44.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0},
    {"keyword_accuracy": 0.40, "word_count_mean": 42.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0},
    {"keyword_accuracy": 0.35, "word_count_mean": 40.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0},
    {"keyword_accuracy": 0.30, "word_count_mean": 38.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0},
    {"keyword_accuracy": 0.28, "word_count_mean": 36.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0},
    {"keyword_accuracy": 0.25, "word_count_mean": 35.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0},
]

print("=" * 60)
print("  DRIFT SIMULATION — feeding degraded metrics")
print("  Baseline keyword_accuracy ~0.81 | Injecting ~0.25-0.45")
print("=" * 60)

for i, m in enumerate(bad_metrics):
    detector.ingest("review_summary", m)
    result = detector.check_drift("review_summary")
    kw = m["keyword_accuracy"]
    status = "[DRIFT_DETECTED]" if result.drifted else ("[drift signal]" if result.drifted_metrics else "[stable]")
    print(f"Cycle {i+1}: keyword_accuracy={kw:.2f} -> {status}")
    if result.drifted:
        print(f"   Reason: {result.reason}")
        print(f"   Metrics: {result.drifted_metrics}")
