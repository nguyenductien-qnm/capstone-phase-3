#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drift_replay.py — [DIRECTIVE #27] Mentor Replay Entry for Drift Detection
=========================================================================
Nhận một chuỗi eval metrics từ ngoài → chạy qua DriftDetector từng điểm theo
thứ tự thời gian → xuất drift signal với điểm phát hiện rõ ràng.

Usage:
  # Mentor đưa chuỗi stable → expects "STABLE"
  python drift_replay.py --series test_series_stable.json

  # Mentor đưa chuỗi có shift → expects "DRIFT_DETECTED"
  python drift_replay.py --series test_series_shifted.json

  # Tự sinh series test để demo
  python drift_replay.py --generate-test-series

Input format (series JSON):
  [
    {
      "timestamp": 1721800000,
      "surface": "review_summary",
      "metrics": {
        "keyword_accuracy": 0.82,
        "word_count_mean": 45.2,
        "fallback_rate": 0.0,
        "hallucination_risk_rate": 0.0
      }
    },
    ...
  ]

Output format:
  {
    "surface": "review_summary",
    "n_snapshots": 20,
    "baseline": {...},
    "drift_events": [...],
    "verdict": "DRIFT_DETECTED" | "STABLE",
    "first_drift_at_snapshot": 14
  }
"""

import argparse
import json
import math
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from drift_detector import DriftDetector, generate_baseline, DEFAULT_BASELINE_PATH

# ─────────────────────────────────────────────────────────────
# Test series generators (for demo and unit tests)
# ─────────────────────────────────────────────────────────────
def _stable_series(surface: str = "review_summary", n: int = 20,
                   mean: float = None, std: float = 0.025,
                   start_ts: float = None, rng: random.Random = None,
                   baseline_path: str = DEFAULT_BASELINE_PATH) -> list:
    """Generate a stable series close to baseline."""
    if rng is None:
        rng = random.Random(42)
    if start_ts is None:
        start_ts = time.time() - n * 300

    # Try to load baseline means so we're centered on the real baseline
    bl_means = {}
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path) as f:
                bl = json.load(f)
            surf = bl.get(surface, {})
            for key in ["keyword_accuracy", "word_count_mean", "fallback_rate",
                        "hallucination_risk_rate", "task_success_rate", "abstention_rate"]:
                v = surf.get(f"{key}_mean")
                if v is not None:
                    bl_means[key] = v
        except Exception:
            pass

    METRIC_DEFAULTS = {
        "review_summary": {
            "keyword_accuracy": 0.82, "word_count_mean": 48.0,
            "fallback_rate": 0.02, "hallucination_risk_rate": 0.01,
        },
        "copilot": {
            "task_success_rate": 0.88, "abstention_rate": 0.06, "fallback_rate": 0.02,
        },
    }
    bases = {k: bl_means.get(k, v) for k, v in METRIC_DEFAULTS.get(surface, {}).items()}
    if mean is not None:
        # Override primary metric only
        if "keyword_accuracy" in bases:
            bases["keyword_accuracy"] = mean
        if "task_success_rate" in bases:
            bases["task_success_rate"] = mean
    series = []
    for i in range(n):
        metrics = {
            k: max(0.0, min(1.0, v + rng.gauss(0, std)))
            if k != "word_count_mean" else max(10.0, v + rng.gauss(0, 3.0))
            for k, v in bases.items()
        }
        series.append({
            "timestamp": start_ts + i * 300,
            "surface": surface,
            "metrics": {k: round(v, 4) for k, v in metrics.items()},
        })
    return series


def _shifted_series(surface: str = "review_summary", n: int = 20,
                    pre_mean: float = 0.82, post_mean: float = 0.35,
                    shift_at: int = 12, std: float = 0.02,
                    start_ts: float = None, rng: random.Random = None,
                    baseline_path: str = DEFAULT_BASELINE_PATH) -> list:
    """Generate a series that shifts distribution at shift_at index."""
    if rng is None:
        rng = random.Random(42)
    if start_ts is None:
        start_ts = time.time() - n * 300

    bl_means = {}
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path) as f:
                bl = json.load(f)
            surf = bl.get(surface, {})
            for key in ["keyword_accuracy", "word_count_mean", "fallback_rate",
                        "hallucination_risk_rate", "task_success_rate", "abstention_rate"]:
                v = surf.get(f"{key}_mean")
                if v is not None:
                    bl_means[key] = v
        except Exception:
            pass

    METRIC_BASES_PRE = {
        "review_summary": {
            "keyword_accuracy": pre_mean, "word_count_mean": bl_means.get("word_count_mean", 48.0),
            "fallback_rate": bl_means.get("fallback_rate", 0.02), "hallucination_risk_rate": bl_means.get("hallucination_risk_rate", 0.01),
        },
        "copilot": {
            "task_success_rate": pre_mean, "abstention_rate": bl_means.get("abstention_rate", 0.06), "fallback_rate": bl_means.get("fallback_rate", 0.02),
        },
    }
    METRIC_BASES_POST = {
        "review_summary": {
            "keyword_accuracy": post_mean, "word_count_mean": bl_means.get("word_count_mean", 48.0) * 0.25, # drop significantly
            "fallback_rate": 0.55, "hallucination_risk_rate": 0.05,
        },
        "copilot": {
            "task_success_rate": post_mean, "abstention_rate": 0.40, "fallback_rate": 0.35,
        },
    }

    series = []
    for i in range(n):
        bases = METRIC_BASES_POST[surface] if i >= shift_at else METRIC_BASES_PRE[surface]
        metrics = {
            k: max(0.0, min(1.0, v + rng.gauss(0, std)))
            if k != "word_count_mean" else max(5.0, v + rng.gauss(0, 2.0))
            for k, v in bases.items()
        }
        series.append({
            "timestamp": start_ts + i * 300,
            "surface": surface,
            "metrics": {k: round(v, 4) for k, v in metrics.items()},
        })
    return series


# ─────────────────────────────────────────────────────────────
# Replay engine
# ─────────────────────────────────────────────────────────────
def replay(series: list, baseline_path: str = DEFAULT_BASELINE_PATH, state_path: str = None) -> dict:
    """
    Run DriftDetector over a time-ordered series of eval snapshots.
    Returns a full drift report.
    """
    if not series:
        return {"verdict": "NO_DATA", "drift_events": [], "n_snapshots": 0}

    # Determine surface (use first entry's surface)
    surface = series[0].get("surface", "review_summary")

    # Ensure baseline exists
    if not os.path.exists(baseline_path):
        baseline = generate_baseline()
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)

    if state_path:
        detector = DriftDetector(baseline_path, state_path=state_path)
    else:
        detector = DriftDetector(baseline_path)
    drift_events = []

    for i, snap in enumerate(series):
        svc = snap.get("surface", surface)
        metrics = snap.get("metrics", {})
        ts = snap.get("timestamp", time.time())
        detector.ingest(svc, metrics, ts)

        result = detector.check_drift(svc)
        if result.drifted:
            event = result.to_dict()
            event["snapshot_index"] = i
            drift_events.append(event)

    # Load baseline stats for report
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    surf_baseline = baseline_data.get(surface, {})
    baseline_summary = {
        k.replace("_distribution", "_mean"): baseline_data.get(surface, {}).get(k + "_mean")
        for k in ["keyword_accuracy", "word_count_mean", "fallback_rate",
                  "hallucination_risk_rate", "task_success_rate", "abstention_rate"]
        if baseline_data.get(surface, {}).get(k + "_mean") is not None
    }

    verdict = "DRIFT_DETECTED" if drift_events else "STABLE"
    first_drift_at = drift_events[0]["snapshot_index"] if drift_events else None

    return {
        "surface": surface,
        "n_snapshots": len(series),
        "baseline": baseline_summary,
        "drift_events": drift_events,
        "verdict": verdict,
        "first_drift_at_snapshot": first_drift_at,
    }


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def _print_report(result: dict):
    print("\n" + "=" * 70)
    print(f"DRIFT REPLAY REPORT — surface: {result['surface']}")
    print(f"Snapshots processed : {result['n_snapshots']}")
    print(f"Baseline            : {json.dumps(result['baseline'])}")
    print("-" * 70)
    if result["drift_events"]:
        first = result["drift_events"][0]
        print(f"  DRIFT DETECTED at snapshot #{first['snapshot_index']}")
        print(f"  Drifted metrics : {first['drifted_metrics']}")
        print(f"  Reason          : {first['reason']}")
        for metric, detail in first.get("details", {}).items():
            if detail.get("drifted"):
                print(f"    [{metric}] PSI={detail['psi']:.3f}, "
                      f"baseline_mean={detail['baseline_mean']:.3f} -> "
                      f"current_mean={detail['current_mean']:.3f} ({detail['severity'].upper()})")
    else:
        print("  STABLE — no drift flagged across the series")
    print("-" * 70)
    print(f"VERDICT: {result['verdict']}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="[DIRECTIVE #27] Drift Replay — feed a series, get drift signal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--series", help="Path to eval series JSON file")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--output", help="Write result JSON to this path")
    parser.add_argument("--generate-test-series", action="store_true",
                        help="Generate test series files for demo/mentor use")
    parser.add_argument("--surface", default="review_summary",
                        choices=["review_summary", "copilot"])
    args = parser.parse_args()

    if args.generate_test_series:
        # Generate stable and shifted series files
        for surface in ["review_summary", "copilot"]:
            stable = _stable_series(surface=surface, n=20)
            shifted = _shifted_series(surface=surface, n=20, shift_at=12)

            stable_path = os.path.join(_HERE, f"test_series_stable_{surface}.json")
            shifted_path = os.path.join(_HERE, f"test_series_shifted_{surface}.json")

            with open(stable_path, "w", encoding="utf-8") as f:
                json.dump(stable, f, indent=2)
            with open(shifted_path, "w", encoding="utf-8") as f:
                json.dump(shifted, f, indent=2)

            print(f"Generated: {stable_path}")
            print(f"Generated: {shifted_path}")
        return

    if not args.series:
        parser.print_help()
        sys.exit(1)

    with open(args.series, "r", encoding="utf-8") as f:
        series = json.load(f)

    # Ensure baseline exists
    if not os.path.exists(args.baseline):
        print(f"[INFO] Baseline not found — generating from golden_dataset.json...")
        baseline = generate_baseline()
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)
        print(f"[INFO] Baseline written → {args.baseline}")

    result = replay(series, args.baseline)
    _print_report(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Result written → {args.output}")


if __name__ == "__main__":
    main()
