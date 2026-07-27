"""Quét ngưỡng similarity cho L2 semantic cache — ĐO THẬT bằng Titan, không mô phỏng.

Cách chấm: mỗi cặp câu có nhãn sẵn (`hit` = cùng ý, phải trúng cache; `miss` = khác ý,
tuyệt đối không được trúng). Quét ngưỡng 0.70→0.99, mỗi ngưỡng đếm:

    recall     = số cặp `hit` được nhận  / tổng cặp `hit`
    false_hit  = số cặp `miss` bị nhận   / tổng cặp `miss`

**Luật chọn viết TRƯỚC khi chạy:** lấy ngưỡng **thấp nhất** có `false_hit = 0`; nhiều
ngưỡng cùng thoả thì lấy cái cho recall cao nhất. Thấp nhất chứ không phải recall đẹp
nhất — trả sai một lần là fail tiêu chí "không trả cũ sai" của MANDATE-23.

Chạy: python3 docs/ai/evals/param_sweep_m23.py
"""
import json
import os
import sys

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL = "amazon.titan-embed-text-v2:0"

# `hit`  : diễn đạt khác nhưng CÙNG ý — cache trúng là đúng.
# `miss` : gần giống mà KHÁC nghĩa (phủ định, đổi mốc giá, đổi sản phẩm, đổi thuộc tính).
PAIRS = [
    ("Ống nhòm Roof Binoculars giá bao nhiêu?",
     "Cho mình hỏi giá của ống nhòm Roof Binoculars?", "hit"),
    ("Ống nhòm Roof Binoculars giá bao nhiêu?",
     "Roof Binoculars bán bao nhiêu tiền vậy shop?", "hit"),
    ("Kính National Park Foundation Explorascope có tốt không?",
     "Khách đánh giá kính National Park Foundation Explorascope thế nào?", "hit"),
    ("Kính thiên văn nào phù hợp cho người mới bắt đầu?",
     "Người mới chơi thiên văn nên mua kính nào?", "hit"),
    # --- đối chứng: PHẢI miss ---
    ("Ống nhòm Roof Binoculars giá bao nhiêu?",
     "Ống nhòm Roof Binoculars có chống nước không?", "miss"),
    ("Kính thiên văn dưới 200 USD có gì?",
     "Kính thiên văn trên 200 USD có gì?", "miss"),
    ("Pin của sản phẩm này dùng được lâu không?",
     "Pin của sản phẩm này không bền phải không?", "miss"),
    ("Kính National Park Foundation Explorascope có tốt không?",
     "Ống nhòm Roof Binoculars có tốt không?", "miss"),
    ("Cho mình xem kính thiên văn",
     "Cho mình xem sách thiên văn", "miss"),
]


def embed(client, text):
    resp = client.invoke_model(modelId=MODEL, body=json.dumps({"inputText": text}))
    return json.loads(resp["body"].read())["embedding"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def main():
    client = boto3.client("bedrock-runtime", region_name=REGION)
    cache = {}

    def emb(t):
        if t not in cache:
            cache[t] = embed(client, t)
        return cache[t]

    rows = []
    for src, other, label in PAIRS:
        sim = cosine(emb(src), emb(other))
        rows.append((src, other, label, sim))
        print(f"{label:5} {sim:.4f}  {other[:52]}")

    hits = [r for r in rows if r[2] == "hit"]
    misses = [r for r in rows if r[2] == "miss"]

    print(f"\ncặp hit: {len(hits)} · cặp miss: {len(misses)}")
    print(f"similarity nhỏ nhất nhóm hit : {min(r[3] for r in hits):.4f}")
    print(f"similarity lớn nhất nhóm miss: {max(r[3] for r in misses):.4f}")

    print("\n| Ngưỡng | Recall | False-hit |")
    print("|---|---|---|")
    table = []
    th = 0.70
    while th <= 0.995:
        recall = sum(1 for r in hits if r[3] >= th) / len(hits)
        false_hit = sum(1 for r in misses if r[3] >= th) / len(misses)
        table.append((round(th, 2), recall, false_hit))
        print(f"| {th:.2f} | {recall*100:.0f}% | {false_hit*100:.0f}% |")
        th += 0.01

    safe = [t for t in table if t[2] == 0.0]
    if not safe:
        print("\nKhông ngưỡng nào cho false-hit = 0 → TẮT L2, chạy L1 thôi.")
        return 1
    best_recall = max(t[1] for t in safe)
    chosen = min(t[0] for t in safe if t[1] == best_recall)
    print(f"\nCHỌN SEMANTIC_CACHE_MIN_SIM = {chosen:.2f} "
          f"(recall {best_recall*100:.0f}%, false-hit 0%) — luật: thấp nhất có false-hit = 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
