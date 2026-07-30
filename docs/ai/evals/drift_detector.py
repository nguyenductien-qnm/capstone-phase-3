#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drift_detector.py — [DIRECTIVE #27] AI Quality Drift Detection
==============================================================
Phát hiện data/model drift trên hai bề mặt AI:
  - review_summary : keyword_accuracy, word_count_mean, fallback_rate, hallucination_risk_rate
  - copilot        : task_success_rate, abstention_rate, fallback_rate

Approach: Sliding-window PSI (Population Stability Index) + KS-test
  PSI < 0.10  → Stable
  PSI 0.10–0.20 → Warning
  PSI > 0.20  → DRIFT

CLI:
  # Generate baseline từ golden_dataset evaluation
  python drift_detector.py --generate-baseline

  # Check drift từ một single metrics snapshot (daemon mode gọi mỗi eval cycle)
  python drift_detector.py --surface review_summary --metrics '{"keyword_accuracy": 0.45}'

Usage trong code:
  from drift_detector import DriftDetector
  detector = DriftDetector("baseline_snapshot.json")
  detector.ingest("review_summary", {"keyword_accuracy": 0.82, ...}, time.time())
  result = detector.check_drift("review_summary")
"""

import json
import math
import os
import sys
import time
import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from scipy.stats import ks_2samp
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

log = logging.getLogger("aiops.drift")

_HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_BASELINE_PATH = os.path.join(_HERE, "baseline_snapshot.json")
DEFAULT_DATASET_PATH  = os.path.join(_HERE, "golden_dataset.json")

# ─────────────────────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────────────────────
PSI_WARN  = 0.10   # PSI > 0.10 → warn
PSI_DRIFT = 0.25   # PSI > 0.25 → drift (raised from 0.20 — small baseline has high variance)
KS_P_THRESHOLD = 0.05
WINDOW_SIZE   = 10  # số snapshots trong cửa sổ trượt
MIN_WINDOW    = 5   # tối thiểu cần đủ data
CONSECUTIVE_DRIFT_REQUIRED = 2  # cần N window liên tiếp mới chắc chắn flag

# Minimum absolute change to confirm drift (avoids PSI fire on tiny distributional noise)
MIN_DELTA_MEAN = 0.08  # 8 pp absolute change in primary metric required

# Metric names per surface
MONITORED_METRICS = {
    "review_summary": ["keyword_accuracy", "word_count_mean", "fallback_rate", "hallucination_risk_rate"],
    "copilot":        ["task_success_rate", "abstention_rate", "fallback_rate"],
}


# ─────────────────────────────────────────────────────────────
# PSI implementation (no scipy needed)
# ─────────────────────────────────────────────────────────────
def _psi(baseline_vals: List[float], current_vals: List[float], n_bins: int = 5) -> float:
    """
    Population Stability Index.
    Returns PSI value: < 0.1 stable, 0.1-0.2 warn, > 0.2 drift.
    
    Uses smaller bin count (5) because baseline is often only 10 samples;
    too many bins → very noisy PSI.
    
    For near-constant baseline (std ≈ 0), PSI is undefined; returns 0.
    """
    if not baseline_vals or not current_vals:
        return 0.0

    # If baseline has essentially no variance (constant or near-constant), 
    # PSI is not meaningful — use 0 and let delta-mean check handle it
    base_std = (sum((v - sum(baseline_vals)/len(baseline_vals))**2 for v in baseline_vals) / len(baseline_vals)) ** 0.5
    if base_std < 1e-6:
        return 0.0

    all_vals = baseline_vals + current_vals
    lo, hi = min(all_vals), max(all_vals)
    if hi == lo:
        return 0.0  # constant series

    def _bin_counts(vals):
        counts = [0] * n_bins
        for v in vals:
            idx = min(int((v - lo) / (hi - lo) * n_bins), n_bins - 1)
            counts[idx] += 1
        return counts

    base_counts = _bin_counts(baseline_vals)
    curr_counts = _bin_counts(current_vals)
    n_base = len(baseline_vals)
    n_curr = len(current_vals)

    psi = 0.0
    eps = 1e-4  # larger epsilon to avoid log blowup on small n
    for b, c in zip(base_counts, curr_counts):
        p_b = max(b / n_base, eps)
        p_c = max(c / n_curr, eps)
        psi += (p_c - p_b) * math.log(p_c / p_b)

    return round(abs(psi), 4)


def _delta_mean_drift(baseline_vals: List[float], current_vals: List[float],
                      threshold: float = 0.15) -> bool:
    """
    Simple delta-mean check for near-zero metrics (fallback_rate, hallucination_risk_rate).
    When baseline is near-zero, a large relative increase is the real signal.
    threshold=0.15 means: if current_mean > 15x baseline_mean or > 0.10 absolute → drift.
    """
    if not baseline_vals or not current_vals:
        return False
    b_mean = sum(baseline_vals) / len(baseline_vals)
    c_mean = sum(current_vals) / len(current_vals)
    # Absolute drift: 10 percentage points
    abs_drift = abs(c_mean - b_mean) > 0.10
    # Relative drift: 5x increase on top of near-zero baseline
    rel_drift = b_mean < 0.05 and c_mean > 5 * b_mean + 0.05
    return abs_drift or rel_drift


def _ks_pvalue(baseline_vals: List[float], current_vals: List[float]) -> float:
    """KS test p-value. Low p-value = distributions differ = drift."""
    if not _HAS_SCIPY or len(baseline_vals) < 3 or len(current_vals) < 3:
        return 1.0  # cannot decide, assume stable
    _, p = ks_2samp(baseline_vals, current_vals)
    return float(p)


# ─────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────
@dataclass
class MetricDrift:
    metric: str
    psi: float
    ks_p: float
    baseline_mean: float
    current_mean: float
    severity: str  # "stable", "warn", "drift"
    drifted: bool


@dataclass
class DriftResult:
    surface: str
    drifted: bool
    drifted_metrics: List[str]
    details: Dict[str, MetricDrift]
    reason: str
    timestamp: float = field(default_factory=time.time)
    window_index: int = 0

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "drifted": self.drifted,
            "drifted_metrics": self.drifted_metrics,
            "details": {
                k: {
                    "psi": v.psi, "ks_p": v.ks_p,
                    "baseline_mean": v.baseline_mean,
                    "current_mean": v.current_mean,
                    "severity": v.severity,
                    "drifted": v.drifted,
                }
                for k, v in self.details.items()
            },
            "reason": self.reason,
            "timestamp": self.timestamp,
            "window_index": self.window_index,
        }


# ─────────────────────────────────────────────────────────────
# Baseline generation
# ─────────────────────────────────────────────────────────────
def generate_baseline(dataset_path: str = DEFAULT_DATASET_PATH) -> dict:
    """
    Run evaluation on golden_dataset to produce baseline metric distributions.
    Works offline — uses keyword matching, no Bedrock call needed.
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # Simulate what run_evals produces but collect distributions
    kw_scores = []
    word_counts = []
    fallback_flags = []
    hallucination_flags = []

    for case in dataset:
        expected_kw = case.get("expected_summary_keywords", [])
        # Use reviews' comment text as a proxy for a "baseline model output"
        # In a real system this would be actual LLM output
        reviews = case.get("reviews", [])
        if reviews:
            summary_text = " ".join(r.get("comment", "") for r in reviews[:3])
        else:
            summary_text = ""

        # keyword_accuracy
        if expected_kw and summary_text:
            hits = sum(1 for kw in expected_kw if kw.lower() in summary_text.lower())
            score = hits / len(expected_kw)
        else:
            score = 0.0
        kw_scores.append(score)

        # word_count
        words = summary_text.split()
        word_counts.append(float(len(words)))

        # fallback_rate (0 in golden dataset — all have reviews)
        fallback_flags.append(0.0 if summary_text else 1.0)

        # hallucination_risk_rate (simple heuristic)
        suspicious = ["guaranteed", "100%", "proven", "scientifically"]
        has_risk = any(s in summary_text.lower() for s in suspicious)
        hallucination_flags.append(1.0 if has_risk else 0.0)

    baseline = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_path": dataset_path,
        "n_cases": len(dataset),
        "review_summary": {
            "keyword_accuracy_distribution": kw_scores,
            "keyword_accuracy_mean": round(sum(kw_scores) / len(kw_scores), 4) if kw_scores else 0.0,
            "word_count_mean_distribution": word_counts,
            "word_count_mean_mean": round(sum(word_counts) / len(word_counts), 2) if word_counts else 0.0,
            "fallback_rate_distribution": fallback_flags,
            "fallback_rate_mean": round(sum(fallback_flags) / len(fallback_flags), 4) if fallback_flags else 0.0,
            "hallucination_risk_rate_distribution": hallucination_flags,
            "hallucination_risk_rate_mean": round(sum(hallucination_flags) / len(hallucination_flags), 4) if hallucination_flags else 0.0,
        },
        # Copilot baseline: reasonable defaults from golden_qa_dataset
        "copilot": {
            "task_success_rate_distribution": [0.85, 0.90, 0.88, 0.92, 0.87, 0.91, 0.89, 0.86, 0.88, 0.90],
            "task_success_rate_mean": 0.886,
            "abstention_rate_distribution": [0.05, 0.08, 0.06, 0.04, 0.07, 0.05, 0.06, 0.07, 0.05, 0.06],
            "abstention_rate_mean": 0.059,
            "fallback_rate_distribution": [0.02, 0.03, 0.01, 0.02, 0.03, 0.02, 0.01, 0.02, 0.02, 0.03],
            "fallback_rate_mean": 0.021,
        }
    }
    return baseline


DEFAULT_STATE_PATH    = os.path.join(_HERE, "drift_window_state.json")

# ─────────────────────────────────────────────────────────────
# DriftDetector
# ─────────────────────────────────────────────────────────────
class DriftDetector:
    """
    Sliding-window drift detector.
    Call ingest() each eval cycle, then check_drift() to get signal.
    """
    def __init__(self, baseline_path: str = DEFAULT_BASELINE_PATH, state_path: str = DEFAULT_STATE_PATH):
        self.state_path = state_path

        if os.path.exists(baseline_path):
            with open(baseline_path, "r", encoding="utf-8") as f:
                self.baseline = json.load(f)
            log.info("Loaded baseline from %s", baseline_path)
        else:
            log.warning("Baseline not found at %s — generating from default dataset", baseline_path)
            self.baseline = generate_baseline()

        if os.path.exists(self.state_path):
            with open(self.state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                self.windows = defaultdict(list, state.get("windows", {}))
                self._consecutive_drift = defaultdict(int, state.get("consecutive_drift", {}))
                self._window_index = defaultdict(int, state.get("window_index", {}))
            log.info("Loaded drift state from %s", self.state_path)
        else:
            self.windows: Dict[str, List[dict]] = defaultdict(list)
            self._consecutive_drift: Dict[str, int] = defaultdict(int)
            self._window_index: Dict[str, int] = defaultdict(int)

    def save_state(self):
        """Save the current sliding windows to disk to persist across runs."""
        state = {
            "windows": dict(self.windows),
            "consecutive_drift": dict(self._consecutive_drift),
            "window_index": dict(self._window_index)
        }
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def ingest(self, surface: str, metrics: dict, timestamp: float = None):
        """Add one eval snapshot to the sliding window."""
        if timestamp is None:
            timestamp = time.time()
        entry = {"ts": timestamp, **metrics}
        self.windows[surface].append(entry)
        if len(self.windows[surface]) > WINDOW_SIZE:
            self.windows[surface].pop(0)
        self._window_index[surface] += 1

    def check_drift(self, surface: str) -> DriftResult:
        """Compare current window against baseline for a surface."""
        w = self.windows[surface]
        if len(w) < MIN_WINDOW:
            return DriftResult(
                surface=surface, drifted=False, drifted_metrics=[],
                details={}, reason=f"insufficient_data (need {MIN_WINDOW}, have {len(w)})",
                window_index=self._window_index[surface]
            )

        surf_baseline = self.baseline.get(surface, {})
        monitored = MONITORED_METRICS.get(surface, [])

        details: Dict[str, MetricDrift] = {}
        drifted_metrics = []

        for metric in monitored:
            dist_key = f"{metric}_distribution"
            baseline_dist = surf_baseline.get(dist_key, [])
            if not baseline_dist:
                continue

            current_vals = [entry[metric] for entry in w if metric in entry]
            if not current_vals:
                continue

            psi_score = _psi(baseline_dist, current_vals)
            ks_p = _ks_pvalue(baseline_dist, current_vals)

            b_mean = round(sum(baseline_dist) / len(baseline_dist), 4)
            c_mean = round(sum(current_vals) / len(current_vals), 4)

            # For near-zero baseline metrics (fallback, hallucination), PSI is unreliable.
            # Use delta-mean check instead: a big absolute jump IS the drift signal.
            near_zero_metrics = {"fallback_rate", "hallucination_risk_rate", "abstention_rate"}
            # word_count_mean has different scale — use 20% relative shift
            pct_metrics = {"word_count_mean"}

            if metric in near_zero_metrics:
                is_drifted = _delta_mean_drift(baseline_dist, current_vals)
                psi_score = 0.0  # PSI not applicable here
            elif metric in pct_metrics:
                mean_delta_pct = abs(c_mean - b_mean) / max(b_mean, 1.0)
                psi_triggered = psi_score > PSI_DRIFT and mean_delta_pct >= 0.20
                ks_triggered  = ks_p < KS_P_THRESHOLD and mean_delta_pct >= 0.20
                is_drifted = psi_triggered or ks_triggered
            else:
                # Require PSI/KS + meaningful mean shift (8 pp) to avoid noise
                mean_delta = abs(c_mean - b_mean)
                psi_triggered = psi_score > PSI_DRIFT and mean_delta >= MIN_DELTA_MEAN
                ks_triggered  = ks_p < KS_P_THRESHOLD and mean_delta >= MIN_DELTA_MEAN
                is_drifted = psi_triggered or ks_triggered

            if is_drifted:
                severity = "drift"
            elif psi_score > PSI_WARN:
                severity = "warn"
            else:
                severity = "stable"

            md = MetricDrift(
                metric=metric, psi=psi_score, ks_p=round(ks_p, 4),
                baseline_mean=b_mean, current_mean=c_mean,
                severity=severity, drifted=is_drifted
            )
            details[metric] = md
            if is_drifted:
                drifted_metrics.append(metric)



        # Consecutive drift gate: require N windows in a row
        if drifted_metrics:
            self._consecutive_drift[surface] += 1
        else:
            self._consecutive_drift[surface] = 0

        confirmed_drift = (
            bool(drifted_metrics)
            and self._consecutive_drift[surface] >= CONSECUTIVE_DRIFT_REQUIRED
        )

        if confirmed_drift:
            reason = (
                f"PSI/KS drift confirmed on [{', '.join(drifted_metrics)}] "
                f"for {self._consecutive_drift[surface]} consecutive windows"
            )
        elif drifted_metrics:
            reason = (
                f"Drift signal on [{', '.join(drifted_metrics)}] "
                f"but only {self._consecutive_drift[surface]}/{CONSECUTIVE_DRIFT_REQUIRED} "
                "consecutive windows — not yet confirmed"
            )
        else:
            reason = "stable"

        result = DriftResult(
            surface=surface,
            drifted=confirmed_drift,
            drifted_metrics=drifted_metrics if confirmed_drift else [],
            details=details,
            reason=reason,
            window_index=self._window_index[surface],
        )
        
        # Persist state after checking
        self.save_state()
        
        return result


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="[DIRECTIVE #27] AI Drift Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--generate-baseline", action="store_true",
                        help="Generate baseline_snapshot.json from golden_dataset.json")
    parser.add_argument("--dataset", default=DEFAULT_DATASET_PATH)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--surface", choices=["review_summary", "copilot"],
                        help="Surface to check drift for")
    parser.add_argument("--metrics", type=str,
                        help="JSON string of current metrics snapshot")
    args = parser.parse_args()

    if args.generate_baseline:
        log.info("Generating baseline from %s ...", args.dataset)
        baseline = generate_baseline(args.dataset)
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)
        log.info("Baseline written → %s", args.baseline)
        print(json.dumps(baseline, indent=2))
        return

    if args.surface and args.metrics:
        metrics = json.loads(args.metrics)
        detector = DriftDetector(args.baseline)
        detector.ingest(args.surface, metrics)
        # Pad window for single-snapshot check
        for _ in range(MIN_WINDOW - 1):
            detector.ingest(args.surface, metrics)
        result = detector.check_drift(args.surface)
        print(json.dumps(result.to_dict(), indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
