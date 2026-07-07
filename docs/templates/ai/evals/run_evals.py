#!/usr/bin/env python3
import json
import argparse

def evaluate_summaries(dataset_path):
    print(f"[*] Loading Golden Dataset from {dataset_path}...")
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"[*] Running AI summarization evals on {len(data)} test cases...")
    
    # Giả lập chạy đánh giá ROUGE/BLEU hoặc LLM-as-a-judge
    results = []
    total_score = 0
    
    for idx, case in enumerate(data):
        pid = case["product_id"]
        # Ở đây sẽ gọi API review summary hoặc LLM thật
        mock_summary = "Sản phẩm chất lượng tốt nhưng giá hơi đắt."
        expected = case["expected_summary_keywords"]
        
        # Đánh giá xem summary có chứa các từ khóa mong đợi không
        matched = [kw for kw in expected if kw.lower() in mock_summary.lower()]
        score = len(matched) / len(expected)
        total_score += score
        
        results.append({
            "product_id": pid,
            "score": score,
            "matched_keywords": matched
        })
        print(f"  [Case {idx+1}] Product: {pid} | Accuracy Score: {score:.2%}")
        
    avg_score = total_score / len(data)
    print(f"\n[+] Evals Complete! Average Summary Accuracy: {avg_score:.2%}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI summary quality evaluations")
    parser.add_argument("--dataset", type=str, default="golden_dataset.json", help="Path to golden dataset file")
    args = parser.parse_args()
    evaluate_summaries(args.dataset)
