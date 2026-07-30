#!/usr/bin/env python3
"""Simulate drift: feed 6 eval cycles with degraded metrics to trigger DRIFT_DETECTED."""
import sys
sys.path.insert(0, "docs/ai/evals")
from drift_detector import DriftDetector, DEFAULT_BASELINE_PATH

detector = DriftDetector(DEFAULT_BASELINE_PATH)

# 7 cycles đầu điểm cao (ổn định)
good_metrics = [
    {"keyword_accuracy": 0.85, "word_count_mean": 67.0, "fallback_rate": 0.0, "hallucination_risk_rate": 0.0}
    for _ in range(7)
]
# 2 cycles sau điểm cực tệ (để ép drift ở cycle 8 và 9)
bad_metrics = [
    {"keyword_accuracy": 0.20, "word_count_mean": 20.0, "fallback_rate": 1.0, "hallucination_risk_rate": 1.0},
    {"keyword_accuracy": 0.20, "word_count_mean": 20.0, "fallback_rate": 1.0, "hallucination_risk_rate": 1.0},
]
all_metrics = good_metrics + bad_metrics

print("=" * 60)
print("  DRIFT SIMULATION — feeding degraded metrics")
print("  Baseline keyword_accuracy ~0.81 | Injecting ~0.25-0.45")
print("=" * 60)

for i, m in enumerate(all_metrics):
    detector.ingest("review_summary", m)
    result = detector.check_drift("review_summary")
    kw = m["keyword_accuracy"]
    if result.drifted:
        status = "[DRIFT_DETECTED]"
    elif "not yet confirmed" in result.reason:
        status = "[suspicious]"
    else:
        status = "[stable]"
    print(f"Cycle {i+1}: keyword_accuracy={kw:.2f} -> {status}")
    if result.drifted:
        print(f"   Reason: {result.reason}")
        print(f"   Metrics: {result.drifted_metrics}")
