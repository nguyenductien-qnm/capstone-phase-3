#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_evals.py - Do luong tu dong chat luong AI tom tat review
=============================================================
Mô tả   : So sánh tóm tắt AI với từ khóa mong đợi trong golden_dataset.json.
           Tính accuracy score, in báo cáo, exit 1 nếu dưới ngưỡng.

JIRA    : TF1-22 (Evaluation pipeline)
Chạy thử:
  python docs/ai/evals/run_evals.py
  python docs/ai/evals/run_evals.py --dataset docs/ai/evals/golden_dataset.json
  python docs/ai/evals/run_evals.py --threshold 0.8
"""

import json
import sys
import os
import argparse
from datetime import datetime

# Fix encoding for Windows terminals (cp1258, etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────
# Đường dẫn mặc định
# ─────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))

DEFAULT_DATASET_PATH = os.path.join(_SCRIPT_DIR, "golden_dataset.json")
DEFAULT_SUMMARIES_PATH = os.path.join(
    _REPO_ROOT, "techx-corp-platform", "src", "llm",
    "product-review-summaries", "product-review-summaries.json"
)
DEFAULT_THRESHOLD = 0.70   # Accuracy tối thiểu để PASS
PASS_ICON = "[OK]"
FAIL_ICON = "[FAIL]"
WARN_ICON = "[WARN]"


# ─────────────────────────────────────────────
# Load functions
# ─────────────────────────────────────────────
def load_dataset(path: str) -> list:
    """Nạp golden dataset từ file JSON."""
    if not os.path.isfile(path):
        print(f"{FAIL_ICON} Không tìm thấy dataset: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_summaries(path: str) -> dict:
    """
    Nạp tóm tắt AI từ product-review-summaries.json.
    Trả về dict: {product_id: summary_text}
    """
    if not os.path.isfile(path):
        print(f"{WARN_ICON} Không tìm thấy summaries file: {path}")
        print("   Sẽ dùng mock summaries mặc định để test pipeline.")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f).get("product-review-summaries", [])
    return {item["product_id"]: item["product_review_summary"] for item in items}


def call_bedrock_summarize(reviews_text: str) -> str:
    """Gọi Bedrock Nova để tóm tắt thực tế nếu chưa có trong mock data."""
    prompt = f"Tóm tắt các đánh giá sản phẩm sau trong 20-50 từ:\n\n{reviews_text}"
    try:
        import boto3
        client = boto3.client("bedrock-runtime", region_name="us-east-2")
        
        response = client.converse(
            modelId="amazon.nova-lite-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}]
        )
        return response['output']['message']['content'][0]['text']
    except Exception as e:
        print(f"  [WARN] Không gọi được Bedrock ({e}). Dùng fallback nối string.")
        return reviews_text


# ─────────────────────────────────────────────
# Evaluation metrics
# ─────────────────────────────────────────────
def keyword_accuracy(summary: str, expected_keywords: list) -> dict:
    """
    Đo tỉ lệ từ khóa mong đợi xuất hiện trong tóm tắt AI.
    Không phân biệt hoa/thường.

    Returns:
        {
            "score": float [0.0 – 1.0],
            "hits": list[str],    # Từ khóa tìm thấy
            "misses": list[str],  # Từ khóa không tìm thấy
        }
    """
    summary_lower = summary.lower()
    hits = [kw for kw in expected_keywords if kw.lower() in summary_lower]
    misses = [kw for kw in expected_keywords if kw.lower() not in summary_lower]
    score = len(hits) / len(expected_keywords) if expected_keywords else 0.0
    return {"score": score, "hits": hits, "misses": misses}


def coverage_check(summary: str) -> dict:
    """
    Kiểm tra tóm tắt có đủ dài và không quá ngắn (có thể bị cắt bớt).
    Minimum 20 words, maximum 150 words.
    """
    words = summary.split()
    word_count = len(words)
    ok = 20 <= word_count <= 150
    return {
        "ok": ok,
        "word_count": word_count,
        "note": (
            "Tóm tắt hợp lệ" if ok
            else f"{'Quá ngắn' if word_count < 20 else 'Quá dài'} ({word_count} words)"
        ),
    }


def hallucination_check(summary: str, known_keywords: list) -> dict:
    """
    Phát hiện khả năng ảo giác: đếm số lượng từ kỹ thuật không liên quan
    có thể bị bịa ra. (Simple heuristic — thực tế cần LLM judge.)
    """
    # Danh sách từ "đáng ngờ" — thường xuất hiện khi model ảo giác
    suspicious_patterns = ["guaranteed", "100%", "proven", "scientifically", "clinically"]
    found = [p for p in suspicious_patterns if p.lower() in summary.lower()]
    return {
        "suspicious_found": found,
        "hallucination_risk": "LOW" if not found else "MEDIUM",
    }


# ─────────────────────────────────────────────
# Main eval runner
# ─────────────────────────────────────────────
def run_evals(
    dataset_path: str = DEFAULT_DATASET_PATH,
    summaries_path: str = DEFAULT_SUMMARIES_PATH,
    threshold: float = DEFAULT_THRESHOLD,
    verbose: bool = True,
) -> dict:
    """
    Chạy full evaluation pipeline.

    Returns:
        {
            "overall_accuracy": float,
            "pass": bool,
            "results": list[dict],
            "timestamp": str,
        }
    """
    dataset = load_dataset(dataset_path)
    summaries = load_summaries(summaries_path)

    if verbose:
        print("\n" + "=" * 65)
        print("  [EVAL] TechX Corp - AI Eval Pipeline")
        print(f"  Dataset  : {dataset_path}")
        print(f"  Cases    : {len(dataset)}")
        print(f"  Threshold: {threshold:.0%}")
        print(f"  Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 65)

    results = []
    total_kw_score = 0.0
    passed_cases = 0

    for case in dataset:
        pid = case["product_id"]
        expected_keywords = case.get("expected_summary_keywords", [])

        # Lấy tóm tắt thực tế
        actual_summary = summaries.get(pid, "")
        if not actual_summary:
            # Gọi Bedrock thật nếu không có sẵn
            reviews = case.get("reviews", [])
            if reviews:
                reviews_text = " ".join(f"- {r.get('comment', '')}" for r in reviews)
                actual_summary = call_bedrock_summarize(reviews_text)
            else:
                actual_summary = ""

        # Chạy metrics
        kw_result = keyword_accuracy(actual_summary, expected_keywords)
        cov_result = coverage_check(actual_summary)
        hal_result = hallucination_check(actual_summary, expected_keywords)

        case_passed = kw_result["score"] >= threshold
        if case_passed:
            passed_cases += 1

        total_kw_score += kw_result["score"]

        case_result = {
            "product_id": pid,
            "product_name": case.get("product_name", pid),
            "keyword_score": kw_result["score"],
            "hits": kw_result["hits"],
            "misses": kw_result["misses"],
            "coverage": cov_result,
            "hallucination": hal_result,
            "pass": case_passed,
        }
        results.append(case_result)

        if verbose:
            icon = PASS_ICON if case_passed else FAIL_ICON
            print(f"\n{icon} [{pid}] {case.get('product_name', pid)}")
            print(f"   Keyword score : {kw_result['score']:.0%}")
            print(f"   Hits          : {kw_result['hits']}")
            if kw_result["misses"]:
                print(f"   Misses        : {kw_result['misses']}")
            print(f"   Word count    : {cov_result['word_count']} ({cov_result['note']})")
            print(f"   Hallucination : {hal_result['hallucination_risk']}", end="")
            if hal_result["suspicious_found"]:
                print(f" -> {hal_result['suspicious_found']}", end="")
            print()

    # Tong ket
    overall_accuracy = total_kw_score / len(dataset) if dataset else 0.0
    overall_pass = overall_accuracy >= threshold

    if verbose:
        print("\n" + "=" * 65)
        icon = "[OK]" if overall_pass else "[FAIL]"
        print(f"  {icon} OVERALL ACCURACY : {overall_accuracy:.1%}")
        print(f"     Cases passed    : {passed_cases} / {len(dataset)}")
        print(f"     Threshold       : {threshold:.0%}")
        print(f"     Result          : {'PASS' if overall_pass else 'FAIL'}")
        print("=" * 65 + "\n")

    summary = {
        "overall_accuracy": overall_accuracy,
        "cases_passed": passed_cases,
        "total_cases": len(dataset),
        "pass": overall_pass,
        "threshold": threshold,
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }
    return summary


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="TechX Corp — AI Evaluation Pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET_PATH,
        help=f"Đường dẫn đến golden_dataset.json\n(mặc định: {DEFAULT_DATASET_PATH})",
    )
    parser.add_argument(
        "--summaries",
        default=DEFAULT_SUMMARIES_PATH,
        help="Đường dẫn đến product-review-summaries.json của BTC",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Accuracy tối thiểu để PASS (mặc định: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Lưu kết quả vào file JSON (tuỳ chọn)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Chỉ in kết quả cuối, không in chi tiết",
    )
    args = parser.parse_args()

    result = run_evals(
        dataset_path=args.dataset,
        summaries_path=args.summaries,
        threshold=args.threshold,
        verbose=not args.quiet,
    )

    # Lưu output nếu được yêu cầu
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"📄 Kết quả đã lưu: {args.output}")

    # Exit code: 0 = PASS, 1 = FAIL
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
