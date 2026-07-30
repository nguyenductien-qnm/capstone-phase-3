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


class FakeBedrock:
    def __init__(self, labels):
        self.labels = iter(labels)

    def converse(self, **kwargs):
        label = next(self.labels)
        return {"output": {"message": {"content": [{
            "text": '{"label": "%s", "rationale": "Evidence-based test response"}' % label
        }]}}}


def test_live_judge_pipeline_with_injected_client():
    cases = m.load_human_cases()
    client = FakeBedrock([c["human_label"] for c in cases])
    results = [m.judge_case(c, client=client) for c in cases]
    judge_labels = [r["label"] for r in results]
    p_o, p_e, kappa, matrix = m.compute_cohens_kappa([c["human_label"] for c in cases], judge_labels)
    assert p_o == 1.0
    assert kappa == 1.0


def test_judge_rejects_invalid_model_output():
    class BadBedrock:
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "PASS"}]}}}

    try:
        m.judge_case({"category": "leak", "prompt": "x", "llm_output": "y"}, client=BadBedrock())
    except ValueError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("invalid judge output must fail closed")


def test_recorded_results_round_trip_for_offline_replay():
    cases = m.load_human_cases()[:2]
    results = [
        {"label": "PASS", "rationale": "recorded pass"},
        {"label": "FAIL", "rationale": "recorded fail"},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.json"
        m.save_judge_results(path, cases, results, "recorded-model")
        model_id, replayed = m.load_judge_results(path, cases)

    assert model_id == "recorded-model"
    assert replayed == results


def test_saved_results_redact_and_bound_rationale():
    cases = m.load_human_cases()[:1]
    results = [{"label": "PASS", "rationale": "email user@example.com " + "x" * 600}]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.json"
        m.save_judge_results(path, cases, results, "recorded-model")
        saved = json.loads(path.read_text(encoding="utf-8"))["results"][0]["rationale"]
    assert "user@example.com" not in saved
    assert len(saved) <= 500


def test_recorded_results_reject_dataset_drift():
    cases = m.load_human_cases()[:2]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.json"
        path.write_text(json.dumps({
            "model_id": "recorded-model",
            "results": [{"case_id": "wrong", "label": "PASS", "rationale": "x"}],
        }), encoding="utf-8")
        try:
            m.load_judge_results(path, cases)
        except ValueError as exc:
            assert "case IDs" in str(exc)
        else:
            raise AssertionError("replay must fail when the dataset and recorded results drift")


def test_committed_replay_reproduces_published_kappa_offline():
    cases = m.load_human_cases()
    model_id, results = m.load_judge_results(m.RESULTS_PATH, cases)
    p_o, p_e, kappa, matrix = m.compute_cohens_kappa(
        [case["human_label"] for case in cases],
        [result["label"] for result in results],
    )

    assert model_id == "amazon.nova-lite-v1:0"
    assert (round(p_o, 4), round(p_e, 4), round(kappa, 4)) == (0.9333, 0.72, 0.7619)
    assert matrix == {"tp": 12, "tn": 2, "fp": 0, "fn": 1}
