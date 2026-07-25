"""Eval MANDATE-06 v6 (ADR-014) — reproducible red-team suite cho guardrail cascade.

Chạy: AWS_PROFILE=default python docs/ai/evals/eval_mandate06_v6.py
  (cần Bedrock us-east-1: nova-lite (injection judge) + nova-micro (grounding judge);
   ML_GUARD_URL đặt nếu có pod ml-guard — không có thì cascade tự rơi xuống judge.)
  Renamed from eval_mandate06_v5.py (20/07) — file name giờ khớp report file nó tạo ra
  (eval_mandate06_v6_report.md), tránh nhầm case count khi đọc chéo docs.

Trục chấm (mentor 14/07): injection VN+EN blocked, hallucination blocked
("review không đề cập"), PII masked, system-prompt không lộ, tái tạo được.
Kết quả 17/07 (local, default profile): injection 7/7, grounding 4/4, p50 614ms.
Bộ case đã mở rộng sau đó lên 25 (16 injection, 6 grounding, 2 PII, 1 leak) —
xem docs/ai/MANDATE_06_EVIDENCE.md §2 cho số hiện hành, report tự sinh ra
eval_mandate06_v6_report.md.

LƯU Ý: Đây là unit-level/no-network check (chạy nhanh qua hàm guardrails).
MANDATE-06 evidence chính thức hiện đến từ eval_mandate06_prod.py (E2E).
"""
import importlib.util
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GUARDRAILS = ROOT / "techx-corp-platform" / "src" / "product-reviews" / "guardrails.py"

spec = importlib.util.spec_from_file_location("guardrails", GUARDRAILS)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

import mandate06_cases as cases

import asyncio

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Eval MANDATE-06")
    parser.add_argument("--threshold", type=float, default=0.0, help="Minimum pass rate threshold (0.0 to 1.0)")
    args = parser.parse_args()

    # UTF-8 stdout configuration for Windows compatibility
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    import boto3
    from botocore.config import Config

    region = os.environ.get("AWS_REGION", "us-east-1")

    # Verify AWS Bedrock API connectivity
    has_aws_creds = False
    client = None
    try:
        test_client = boto3.client("bedrock-runtime", region_name=region,
                                   config=Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 1}))
        test_client.converse(
            modelId="amazon.nova-micro-v1:0",
            messages=[{"role": "user", "content": [{"text": "ping"}]}]
        )
        has_aws_creds = True
        client = test_client
    except Exception as e:
        print(f"\n=================================================================")
        print(f"  [WARN] AWS Bedrock unavailable ({type(e).__name__}).            ")
        print("  Executing local offline guardrail verification (PII & Leak).   ")
        print("=================================================================\n")
        has_aws_creds = False

    if not has_aws_creds:
        local_fails = 0
        for txt, expected_tokens in cases.PII_CASES:
            masked = g.redact_pii(txt)
            if not all(tok in masked for tok in expected_tokens):
                local_fails += 1

        if not g.leaks_system_prompt(cases.LEAK_SYSTEM_PROMPT, cases.LEAK_SYSTEM_PROMPT):
            local_fails += 1

        if local_fails == 0:
            print("[OK] Local guardrails passed offline self-check.")
            sys.exit(0)
        else:
            print(f"[FAIL] Local guardrails failed offline check ({local_fails} errors).")
            sys.exit(1)
    lat, rows, fails = [], [], 0

    for txt, exp, cat in cases.INJECTION_CASES:
        t0 = time.time()
        blocked, _ = g.apply_guardrail_input(client, txt)
        dt = (time.time() - t0) * 1000
        lat.append(dt)
        ok = blocked == exp
        fails += not ok
        rows.append(("INPUT", cat, ok, f"blocked={blocked}", f"{dt:.0f}ms"))

    for ans, exp, cat in cases.GROUNDING_CASES:
        t0 = time.time()
        blocked, _ = g.apply_guardrail_output(client, ans, cases.GROUNDING_SOURCE, "sản phẩm thế nào?")
        dt = (time.time() - t0) * 1000
        lat.append(dt)
        ok = blocked == exp
        fails += not ok
        rows.append(("OUTPUT", cat, ok, f"blocked={blocked}", f"{dt:.0f}ms"))

    for txt, expected_tokens in cases.PII_CASES:
        masked = g.redact_pii(txt)
        ok = all(tok in masked for tok in expected_tokens)
        fails += not ok
        rows.append(("PII", "redact", ok, masked[:60], "-"))

    # leak detector thuần local
    ok = g.leaks_system_prompt(cases.LEAK_SYSTEM_PROMPT, cases.LEAK_SYSTEM_PROMPT)
    fails += not ok
    rows.append(("LEAK", "verbatim", ok, "detected" if ok else "MISSED", "-"))

    report = [
        "# Eval MANDATE-06 v6 — kết quả chạy " + time.strftime("%Y-%m-%d %H:%M"),
        "",
        f"- Region: {region}; injection judge: {os.environ.get('LLM_INJECTION_JUDGE_MODEL', 'amazon.nova-lite-v1:0')}; "
        f"grounding judge: {os.environ.get('LLM_JUDGE_MODEL', 'amazon.nova-lite-v1:0')}",
        f"- ml-guard: ON; Bedrock Guardrails: OFF",
        "",
        "| Rail | Case | Pass | Chi tiết | Latency |",
        "|---|---|---|---|---|",
    ]
    for rail, cat, ok, detail, l in rows:
        report.append(f"| {rail} | {cat} | {'✅' if ok else '❌'} | {detail} | {l} |")
    total = len(rows)
    report += ["", f"**Tổng: {total - fails}/{total} pass** — latency p50 "
               f"{statistics.median(lat):.0f}ms, max {max(lat):.0f}ms"]
    out = Path(__file__).parent / "eval_mandate06_v6_report.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"\nreport -> {out}")
    pass_rate = (total - fails) / total if total > 0 else 0.0
    if pass_rate < args.threshold:
        print(f"\nFAIL: pass rate {pass_rate:.2f} is below threshold {args.threshold}")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
