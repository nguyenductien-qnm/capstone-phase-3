#!/usr/bin/env python3
"""Measure real Amazon Nova latency for reviews and Shopping Copilot flows.

The task needs measured P50/P95, not the old TTFT-derived estimates.  Each
sample below performs the same two-Converse shape used by the services:

* reviews: first Converse requests a tool, second Converse summarizes tool data
* copilot: Converse/toolResult loop until end_turn or the 5-tool safety cap

The reported timeout is the measured end-to-end flow P95 rounded up to 0.1s.
This is intentionally conservative even though service env vars are currently
implemented as botocore read_timeout values per Bedrock call.

Example:
  AWS_PROFILE=Phase3-CDO-PermissionSet-804372444787 \\
    python docs/ai/evals/measure_bedrock_latency.py --region us-east-1 --n 10 \\
    --markdown-out docs/ai/evals/bedrock_latency_results_2026-07-15.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import boto3


DEFAULT_REGION = "us-east-1"
DEFAULT_PROFILE_PREFIX = "us."

REVIEWS_SYSTEM = (
    "You are a helpful assistant that answers related to a specific product. "
    "Use tools as needed to fetch the product reviews and product information. "
    "Keep the response brief with no more than 1-2 sentences. If you don't know "
    "the answer, just say you don't know."
)

COPILOT_SYSTEM = (
    "Ban la Shopping Copilot cua TechX Corp. Giup khach tim san pham, doc "
    "review, xem/them gio hang. Moi thong tin review phai den tu tool. "
    "Khong tu checkout, khong xoa gio. Tra loi ngan gon."
)

FAKE_REVIEWS_TEXT = (
    "Review: The solar-safe telescope is compact, easy to carry, and safe for "
    "family solar viewing. The image is clear for beginners, though the tripod "
    "can shake in wind. Shipping was fast. 4/5 stars. "
) * 45


def create_bedrock_runtime_client(*, session: boto3.Session, region_name: str):
    role_arn = os.environ.get("BEDROCK_AWS_ROLE_ARN")
    if role_arn:
        assume_role_kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": os.environ.get("BEDROCK_AWS_ROLE_SESSION_NAME", "measure-bedrock-latency"),
        }
        external_id = os.environ.get("BEDROCK_AWS_EXTERNAL_ID")
        if external_id:
            assume_role_kwargs["ExternalId"] = external_id

        sts = session.client("sts")
        response = sts.assume_role(**assume_role_kwargs)
        credentials = response["Credentials"]
        assumed = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        print("Using IRSA/profile credentials to assume BEDROCK_AWS_ROLE_ARN")
        return assumed.client("bedrock-runtime", region_name=region_name)

    return session.client("bedrock-runtime", region_name=region_name)

REVIEWS_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "fetch_product_reviews",
                "description": "Executes a SQL query to retrieve reviews for a product.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"product_id": {"type": "string"}},
                        "required": ["product_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "fetch_product_info",
                "description": "Executes a SQL query to retrieve product information.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"product_id": {"type": "string"}},
                        "required": ["product_id"],
                    }
                },
            }
        },
    ]
}

COPILOT_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "search_products",
                "description": "Search TechX catalog by natural language query.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "category": {"type": "string"},
                        },
                        "required": ["query"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_product_reviews",
                "description": "Get real reviews and average score for one product.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"product_id": {"type": "string"}},
                        "required": ["product_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_cart",
                "description": "Read the current cart.",
                "inputSchema": {"json": {"type": "object", "properties": {}}},
            }
        },
        {
            "toolSpec": {
                "name": "add_item_to_cart",
                "description": "Prepare add-to-cart; requires confirmation.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                        "required": ["product_id"],
                    }
                },
            }
        },
    ]
}


@dataclass(frozen=True)
class Case:
    key: str
    flow: str
    role: str
    model_name: str
    spec_model_id: str
    runtime_model_id: str
    runner: Callable


def runtime_id(spec_model_id: str, prefix: str) -> str:
    return spec_model_id if spec_model_id.startswith(prefix) else f"{prefix}{spec_model_id}"


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[index]


def ceil_tenth(value: float) -> float:
    return math.ceil(value * 10.0) / 10.0


def converse(client, model_id: str, **kwargs):
    t0 = time.monotonic()
    response = client.converse(modelId=model_id, **kwargs)
    return response, time.monotonic() - t0


def extract_tool_uses(blocks: list[dict]) -> list[dict]:
    return [block["toolUse"] for block in blocks if "toolUse" in block]


def tool_result_for_reviews(tool_name: str, tool_input: dict) -> dict:
    product_id = tool_input.get("product_id") or "1YMWWN1N4O"
    if tool_name == "fetch_product_info":
        return {
            "id": product_id,
            "name": "Eclipsmart Travel Refractor Telescope",
            "description": "Portable solar-safe refractor telescope for beginners.",
            "price_usd": 69.99,
        }
    return {
        "product_id": product_id,
        "average_score": "4.6",
        "reviews": FAKE_REVIEWS_TEXT,
    }


def reviews_flow(client, model_id: str) -> tuple[float, list[float], list[str]]:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Answer the following question about product ID:1YMWWN1N4O: "
                        "Can you summarize the product reviews?"
                    )
                }
            ],
        }
    ]
    call_latencies: list[float] = []
    stop_reasons: list[str] = []

    t0 = time.monotonic()
    first, elapsed = converse(
        client,
        model_id,
        system=[{"text": REVIEWS_SYSTEM}],
        messages=messages,
        toolConfig=REVIEWS_TOOL_CONFIG,
        inferenceConfig={"maxTokens": 1024, "temperature": 0.1, "topP": 0.9},
    )
    call_latencies.append(elapsed)
    stop_reasons.append(first.get("stopReason", "end_turn"))

    blocks = first["output"]["message"].get("content", [])
    tool_uses = extract_tool_uses(blocks)
    if tool_uses:
        messages.append({"role": "assistant", "content": blocks})
        tool_results = []
        for tool_use in tool_uses:
            tool_results.append(
                {
                    "toolUseId": tool_use["toolUseId"],
                    "content": [{"json": tool_result_for_reviews(tool_use["name"], tool_use.get("input", {}))}],
                }
            )
        messages.append(
            {
                "role": "user",
                "content": [{"toolResult": result} for result in tool_results]
                + [{"text": "Based on the tool results, answer in 1-2 sentences."}],
            }
        )
    else:
        messages.append({"role": "assistant", "content": blocks})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            "Fetched review data: "
                            + json.dumps(tool_result_for_reviews("fetch_product_reviews", {}))
                            + ". Summarize in 1-2 sentences."
                        )
                    }
                ],
            }
        )

    second_kwargs = {
        "system": [{"text": REVIEWS_SYSTEM}],
        "messages": messages,
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.1, "topP": 0.9},
    }
    if tool_uses:
        second_kwargs["toolConfig"] = REVIEWS_TOOL_CONFIG
    second, elapsed = converse(client, model_id, **second_kwargs)
    call_latencies.append(elapsed)
    stop_reasons.append(second.get("stopReason", "end_turn"))
    return time.monotonic() - t0, call_latencies, stop_reasons


def tool_result_for_copilot(tool_name: str, _tool_input: dict) -> dict:
    if tool_name == "get_cart":
        return {"items": []}
    if tool_name == "get_product_reviews":
        return {
            "product_id": "1YMWWN1N4O",
            "average_score": "4.6",
            "review_count": 5,
            "summary": "Customers like the telescope safety filter and portability.",
        }
    if tool_name == "add_item_to_cart":
        return {"status": "pending_confirmation", "message": "Prepared; waiting for confirmation."}
    return {
        "products": [
            {
                "id": "1YMWWN1N4O",
                "name": "Eclipsmart Travel Refractor Telescope",
                "category": "Telescopes",
                "price_usd": 69.99,
            },
            {
                "id": "66VCHSJNUP",
                "name": "StarSense Explorer LT Telescope",
                "category": "Telescopes",
                "price_usd": 99.99,
            },
        ]
    }


def copilot_flow(client, model_id: str) -> tuple[float, list[float], list[str]]:
    messages = [
        {
            "role": "user",
            "content": [
                {"text": "Toi muon tim kinh thien van du lich duoi 100 USD, goi y 2 lua chon phu hop."}
            ],
        }
    ]
    call_latencies: list[float] = []
    stop_reasons: list[str] = []

    t0 = time.monotonic()
    tool_loops = 0
    while True:
        response, elapsed = converse(
            client,
            model_id,
            system=[{"text": COPILOT_SYSTEM}],
            messages=messages,
            toolConfig=COPILOT_TOOL_CONFIG,
            inferenceConfig={"maxTokens": 1024, "temperature": 0.1, "topP": 0.9},
        )
        call_latencies.append(elapsed)
        stop = response.get("stopReason", "end_turn")
        stop_reasons.append(stop)

        blocks = response["output"]["message"].get("content", [])
        tool_uses = extract_tool_uses(blocks)
        if stop != "tool_use" or not tool_uses:
            break

        tool_loops += 1
        if tool_loops > 5:
            break

        messages.append({"role": "assistant", "content": blocks})
        results = []
        for tool_use in tool_uses:
            results.append(
                {
                    "toolUseId": tool_use["toolUseId"],
                    "content": [{"json": tool_result_for_copilot(tool_use["name"], tool_use.get("input", {}))}],
                }
            )
        messages.append({"role": "user", "content": [{"toolResult": result} for result in results]})

    return time.monotonic() - t0, call_latencies, stop_reasons


def summarize(case: Case, flow_latencies: list[float], call_latencies: list[float]) -> dict:
    flow_p95 = percentile(flow_latencies, 95)
    call_p95 = percentile(call_latencies, 95)
    return {
        "flow": case.flow,
        "role": case.role,
        "model_name": case.model_name,
        "spec_model_id": case.spec_model_id,
        "runtime_model_id": case.runtime_model_id,
        "n": len(flow_latencies),
        "flow_p50_s": statistics.median(flow_latencies),
        "flow_p95_s": flow_p95,
        "flow_max_s": max(flow_latencies),
        "call_p50_s": statistics.median(call_latencies),
        "call_p95_s": call_p95,
        "call_max_s": max(call_latencies),
        "timeout_s": ceil_tenth(flow_p95),
    }


def markdown_table(rows: list[dict], region: str, profile: str | None) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    profile_text = profile or "default credential chain"
    lines = [
        "# Bedrock Latency Measurement",
        "",
        f"- Generated: {generated}",
        f"- AWS region: `{region}`",
        f"- AWS profile: `{profile_text}`",
        "- Runtime API: `bedrock-runtime.converse`",
        "- Timeout rule: measured end-to-end `flow_p95_s`, rounded up to nearest 0.1s.",
        "",
        "| Flow | Role | Model | Runtime model ID | n | Flow P50 (s) | Flow P95 (s) | Per-call P95 (s) | Timeout (s) |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {flow} | {role} | `{spec_model_id}` | `{runtime_model_id}` | {n} | "
            "{flow_p50_s:.3f} | {flow_p95_s:.3f} | {call_p95_s:.3f} | {timeout_s:.1f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Notes:",
            "- Reviews flow latency is end-to-end for two Converse rounds.",
            "- Copilot flow latency is end-to-end for the measured tool loop until end_turn or 5-tool cap.",
            "- Per-call latency pools all Converse calls in the measured flow.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_n", nargs="?", type=int, help="Backward-compatible positional sample count.")
    parser.add_argument("--n", type=int, default=None, help="Samples per case.")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--profile-prefix", default=DEFAULT_PROFILE_PREFIX)
    parser.add_argument("--markdown-out", default=None)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    n = args.n if args.n is not None else (args.legacy_n if args.legacy_n is not None else 10)
    session = boto3.Session(profile_name=args.profile) if args.profile else boto3.Session()
    client = create_bedrock_runtime_client(session=session, region_name=args.region)

    cases = [
        Case(
            "reviews_primary",
            "reviews",
            "primary",
            "Amazon Nova Lite",
            "amazon.nova-lite-v1:0",
            runtime_id("amazon.nova-lite-v1:0", args.profile_prefix),
            reviews_flow,
        ),
        Case(
            "reviews_fallback",
            "reviews",
            "fallback",
            "Amazon Nova Micro",
            "amazon.nova-micro-v1:0",
            runtime_id("amazon.nova-micro-v1:0", args.profile_prefix),
            reviews_flow,
        ),
        Case(
            "copilot_primary",
            "copilot",
            "primary",
            "Amazon Nova Pro",
            "amazon.nova-pro-v1:0",
            runtime_id("amazon.nova-pro-v1:0", args.profile_prefix),
            copilot_flow,
        ),
        Case(
            "copilot_fallback",
            "copilot",
            "fallback",
            "Amazon Nova Lite",
            "amazon.nova-lite-v1:0",
            runtime_id("amazon.nova-lite-v1:0", args.profile_prefix),
            copilot_flow,
        ),
    ]

    rows = []
    raw = {"region": args.region, "n": n, "cases": {}}
    for case in cases:
        flow_latencies: list[float] = []
        call_latencies: list[float] = []
        stop_reasons: list[list[str]] = []
        print(f"\n== {case.key}: {case.runtime_model_id} ({n} samples) ==")
        for i in range(n):
            total, calls, stops = case.runner(client, case.runtime_model_id)
            flow_latencies.append(total)
            call_latencies.extend(calls)
            stop_reasons.append(stops)
            calls_text = ", ".join(f"{value:.3f}s" for value in calls)
            print(f"{i + 1:02d}/{n}: flow={total:.3f}s calls=[{calls_text}] stops={stops}")
        row = summarize(case, flow_latencies, call_latencies)
        rows.append(row)
        raw["cases"][case.key] = {
            "summary": row,
            "flow_latencies_s": flow_latencies,
            "call_latencies_s": call_latencies,
            "stop_reasons": stop_reasons,
        }

    table = markdown_table(rows, args.region, args.profile)
    print("\n" + table)

    if args.markdown_out:
        Path(args.markdown_out).write_text(table, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(raw, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
