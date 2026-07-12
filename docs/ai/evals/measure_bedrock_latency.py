#!/usr/bin/env python3
"""Measure REAL Nova Lite converse latency for the reviews-summary shape.

Purpose: replace the unverified "TTFT ~0.4s / ~2.5s end-to-end" numbers in
ADR-004 / fallback_retry.md with measured P50/P95 (see review B3).

Requires valid AWS credentials with bedrock:InvokeModel in us-east-1.
Usage: python3 measure_bedrock_latency.py [n_calls=20]
"""
import statistics
import sys
import time

import boto3

MODEL_ID = "amazon.nova-lite-v1:0"
REGION = "us-east-1"
# ~1500 input tokens: synthetic review blob matching the prompt shape in
# product_reviews_server.py (no real customer data).
FAKE_REVIEWS = ("Review: The battery lasts about 9 hours of continuous use, "
                "noise cancellation is decent for the price, but the ear cups "
                "get warm after an hour. Shipping was fast. 4/5 stars. ") * 55
SYSTEM = ("You are a helpful assistant that answers related to a specific "
          "product. Keep the response brief with no more than 1-2 sentences.")


def one_call(client) -> float:
    t0 = time.monotonic()
    client.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text":
            f"Summarize these product reviews:\n{FAKE_REVIEWS}"}]}],
        inferenceConfig={"maxTokens": 200, "temperature": 0.1},
    )
    return time.monotonic() - t0


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    client = boto3.client("bedrock-runtime", region_name=REGION)
    lat = []
    for i in range(n):
        s = one_call(client)
        lat.append(s)
        print(f"call {i + 1:2d}/{n}: {s:.3f}s")
    lat.sort()
    p50 = statistics.median(lat)
    p95 = lat[max(0, int(len(lat) * 0.95) - 1)]
    print(f"\n{MODEL_ID}  n={n}")
    print(f"  P50 = {p50:.3f}s   P95 = {p95:.3f}s   max = {lat[-1]:.3f}s")
    print(f"  Reviews flow = 2 converse rounds -> typical end-to-end ~= {2 * p50:.1f}s")
    print(f"  So sanh voi timeout 3.0s/call (fallback_retry.md): "
          f"{'OK' if p95 < 3.0 else 'P95 VUOT timeout -> se retry/fallback thuong xuyen'}")


if __name__ == "__main__":
    main()
