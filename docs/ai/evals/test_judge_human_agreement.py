"""Unit tests for measure_judge_human_agreement.py (TF1-90 / A4)."""

import json
import tempfile
from pathlib import Path

import measure_judge_human_agreement as m


def test_compute_cohens_kappa_perfect():
    human = ["PASS", "PASS", "FAIL", "PASS"]
    judge = ["PASS", "PASS", "FAIL", "PASS"]
    p_o, p_e, kappa, matrix = m.compute_cohens_kappa(human, judge)
    assert p_o == 1.0
    assert kappa == 1.0
    assert matrix["tp"] == 3
    assert matrix["tn"] == 1
    assert matrix["fp"] == 0
    assert matrix["fn"] == 0


def test_compute_cohens_kappa_partial():
    human = ["PASS", "PASS", "FAIL", "FAIL"]
    judge = ["PASS", "FAIL", "FAIL", "PASS"]
    p_o, p_e, kappa, matrix = m.compute_cohens_kappa(human, judge)
    assert p_o == 0.5
    assert matrix["tp"] == 1
    assert matrix["tn"] == 1
    assert matrix["fp"] == 1
    assert matrix["fn"] == 1


def test_load_human_cases():
    cases = m.load_human_cases()
    assert len(cases) >= 10
    for case in cases:
        assert "case_id" in case
        assert "surface" in case
        assert "human_label" in case
        assert case["human_label"] in ("PASS", "FAIL")


def test_full_pipeline_execution():
    cases = m.load_human_cases()
    judge_labels = [m.evaluate_judge_prediction(c) for c in cases]
    p_o, p_e, kappa, matrix = m.compute_cohens_kappa([c["human_label"] for c in cases], judge_labels)
    assert p_o >= 0.8
    assert kappa >= 0.7
