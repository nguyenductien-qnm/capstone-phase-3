"""Measure a real Bedrock judge against independently adjudicated labels.

This script is deliberately separate from eval_mandate14.py: the latter checks
machine-verifiable runtime evidence, while this file validates that a semantic
LLM judge follows the human rubric. It never fabricates labels when Bedrock is
unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_MODEL = os.environ.get("LLM_HUMAN_AGREEMENT_MODEL", "amazon.nova-lite-v1:0")
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-east-1")

RUBRIC_PATH = Path(__file__).parent / "JUDGE_HUMAN_RUBRIC.md"


def load_human_cases(dataset_file: str | None = None) -> list[dict]:
    path = Path(dataset_file) if dataset_file else Path(__file__).parent / "human_adjudicated_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _judge_prompt(case: dict) -> str:
    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    return f"""You are an impartial evaluator. Apply the rubric below to exactly one case.
Do not guess facts that are absent from SOURCE. Do not use the HUMAN LABEL or HUMAN RATIONALE.
Return JSON only, with this exact shape:
{{"label":"PASS" or "FAIL","rationale":"one concise evidence-based sentence"}}

RUBRIC:
{rubric}

CASE CATEGORY: {case.get('category', '')}
USER PROMPT:
{case.get('prompt', '')}
SOURCE:
{case.get('source_text', '') or '(none)'}
MODEL OUTPUT:
{case.get('llm_output', '')}
"""


def _parse_judge_response(response: dict) -> dict:
    text = response["output"]["message"]["content"][0]["text"].strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Judge returned no JSON object: {text[:200]!r}")
    result = json.loads(match.group(0))
    label = str(result.get("label", "")).upper()
    if label not in {"PASS", "FAIL"}:
        raise ValueError(f"Judge returned invalid label: {label!r}")
    rationale = str(result.get("rationale", "")).strip()
    if not rationale:
        raise ValueError("Judge returned an empty rationale")
    return {"label": label, "rationale": rationale}


def judge_case(case: dict, client: Any = None, model_id: str = DEFAULT_MODEL,
               region: str = DEFAULT_REGION) -> dict:
    """Call Bedrock Converse and return a parsed label plus rationale.

    ``client`` is injectable for unit tests; production calls always use boto3.
    Missing credentials/network errors are raised instead of replaced by a
    keyword matcher or mock label.
    """
    if client is None:
        import boto3
        client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": _judge_prompt(case)}]}],
        inferenceConfig={"temperature": 0},
    )
    return _parse_judge_response(response)


def evaluate_judge_prediction(case: dict, client: Any = None, **kwargs) -> str:
    """Compatibility wrapper returning only the live judge label."""
    return judge_case(case, client=client, **kwargs)["label"]


def compute_cohens_kappa(human_labels: list[str], judge_labels: list[str]) -> tuple[float, float, float, dict]:
    if len(human_labels) != len(judge_labels):
        raise ValueError("Human and judge label lists must have equal length")
    n = len(human_labels)
    if n == 0:
        return 0.0, 0.0, 0.0, {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    tp = sum(h == "PASS" and j == "PASS" for h, j in zip(human_labels, judge_labels))
    tn = sum(h == "FAIL" and j == "FAIL" for h, j in zip(human_labels, judge_labels))
    fp = sum(h == "FAIL" and j == "PASS" for h, j in zip(human_labels, judge_labels))
    fn = sum(h == "PASS" and j == "FAIL" for h, j in zip(human_labels, judge_labels))
    p_o = (tp + tn) / n
    p_e = (((tp + fn) / n) * ((tp + fp) / n) +
           ((fp + tn) / n) * ((fn + tn) / n))
    kappa = 1.0 if abs(p_e - 1.0) < 1e-9 else (p_o - p_e) / (1.0 - p_e)
    return p_o, p_e, kappa, {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def generate_report(cases: list[dict], judge_results: list[dict], p_o: float,
                    p_e: float, kappa: float, matrix: dict,
                    model_id: str = DEFAULT_MODEL) -> str:
    judge_labels = [r["label"] for r in judge_results]
    lines = [
        "# Live Judge ↔ Human Agreement Report (MANDATE-14)", "",
        f"- Total Human-Adjudicated Cases: **{len(cases)}**",
        f"- Judge model: **{model_id}**",
        f"- Observed Agreement ($P_o$): **{p_o * 100:.2f}%**",
        f"- Chance Agreement ($P_e$): **{p_e * 100:.2f}%**",
        f"- **Cohen's Kappa ($\\kappa$)**: **{kappa:.4f}**", "",
        "## Confusion Matrix", "",
        "| | Judge PASS | Judge FAIL | Total |", "|---|---|---|---|",
        f"| **Human PASS** | {matrix['tp']} (TP) | {matrix['fn']} (FN) | {matrix['tp'] + matrix['fn']} |",
        f"| **Human FAIL** | {matrix['fp']} (FP) | {matrix['tn']} (TN) | {matrix['fp'] + matrix['tn']} |",
        f"| **Total** | {matrix['tp'] + matrix['fp']} | {matrix['fn'] + matrix['tn']} | {len(cases)} |",
        "", "## Per-Case Breakdown", "",
        "| Case ID | Category | Human | Judge | Agree? | Judge rationale |",
        "|---|---|---|---|---|---|",
    ]
    for case, result in zip(cases, judge_results):
        agree = "✅" if case["human_label"] == result["label"] else "❌"
        rationale = result["rationale"].replace("|", "\\|")
        lines.append(f"| `{case['case_id']}` | `{case['category']}` | **{case['human_label']}** | **{result['label']}** | {agree} | {rationale} |")
    lines += ["", "_Labels above came from a live Bedrock judge call; human labels were loaded from the adjudicated dataset._"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure live Bedrock judge vs human labels")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--model-id", default=DEFAULT_MODEL)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--output", default=str(Path(__file__).parent / "judge_human_agreement_report.md"))
    args = parser.parse_args()
    cases = load_human_cases(args.dataset)
    results = [judge_case(case, model_id=args.model_id, region=args.region) for case in cases]
    human_labels = [c["human_label"] for c in cases]
    judge_labels = [r["label"] for r in results]
    p_o, p_e, kappa, matrix = compute_cohens_kappa(human_labels, judge_labels)
    Path(args.output).write_text(generate_report(cases, results, p_o, p_e, kappa, matrix, args.model_id), encoding="utf-8")
    print(f"Evaluated {len(cases)} cases with {args.model_id}.")
    print(f"Observed Agreement: {p_o * 100:.2f}%")
    print(f"Cohen's Kappa: {kappa:.4f}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
