"""Measure Shopping Copilot through its real gRPC service and downstream tools.

The target Shopping Copilot server must already be configured with a real
Bedrock client. Unlike ``measure_bedrock_latency.py``, this benchmark does not
inject synthetic tool results: the agent calls Product Catalog, Product
Reviews, and Cart over gRPC.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import grpc


REPO_ROOT = Path(__file__).resolve().parents[3]
COPILOT_SRC = REPO_ROOT / "techx-corp-platform" / "src" / "shopping-copilot"
sys.path.insert(0, str(COPILOT_SRC))

import demo_pb2  # noqa: E402
import demo_pb2_grpc  # noqa: E402
import shopping_copilot_pb2 as copilot_pb  # noqa: E402
import shopping_copilot_pb2_grpc as copilot_pb_grpc  # noqa: E402


@dataclass(frozen=True)
class EvalCase:
    key: str
    question: str
    expected_tool: str


@dataclass
class Sample:
    case: str
    latency_s: float
    tool_names: list[str]
    tool_latencies_ms: list[int]
    degraded: bool
    passed: bool
    error: str = ""


def nearest_rank(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile / 100 * len(ordered)) - 1)
    return ordered[index]


def summarize(samples: list[Sample]) -> dict:
    latencies = [sample.latency_s for sample in samples]
    tool_latencies = [
        latency
        for sample in samples
        for latency in sample.tool_latencies_ms
    ]
    return {
        "n": len(samples),
        "passed": sum(sample.passed for sample in samples),
        "latency_p50_s": statistics.median(latencies) if latencies else 0.0,
        "latency_p95_s": nearest_rank(latencies, 95),
        "latency_max_s": max(latencies, default=0.0),
        "tool_latency_p50_ms": statistics.median(tool_latencies) if tool_latencies else 0.0,
        "tool_latency_p95_ms": nearest_rank(tool_latencies, 95),
        "tool_latency_max_ms": max(tool_latencies, default=0),
    }


def get_cart(stub, user_id: str, deadline: float) -> tuple[list[tuple[str, int]], float]:
    started = time.perf_counter()
    cart = stub.GetCart(demo_pb2.GetCartRequest(user_id=user_id), timeout=deadline)
    elapsed = time.perf_counter() - started
    return [(item.product_id, item.quantity) for item in cart.items], elapsed


def run_case(stub, case: EvalCase, index: int, deadline: float) -> Sample:
    suffix = uuid.uuid4().hex[:10]
    request = copilot_pb.ChatWithCopilotRequest(
        question=case.question,
        user_id=f"e2e-{case.key}-{suffix}",
        session_id=f"e2e-{case.key}-{index}-{suffix}",
    )
    started = time.perf_counter()
    try:
        response = stub.ChatWithCopilot(request, timeout=deadline)
        elapsed = time.perf_counter() - started
        actions = list(response.actions_taken)
        tool_names = [action.tool_name for action in actions]
        tool_latencies = [action.duration_ms for action in actions]
        passed = (
            case.expected_tool in tool_names
            and not response.degraded
            and all(action.succeeded for action in actions)
        )
        return Sample(
            case=case.key,
            latency_s=elapsed,
            tool_names=tool_names,
            tool_latencies_ms=tool_latencies,
            degraded=response.degraded,
            passed=passed,
        )
    except grpc.RpcError as exc:
        return Sample(
            case=case.key,
            latency_s=time.perf_counter() - started,
            tool_names=[],
            tool_latencies_ms=[],
            degraded=True,
            passed=False,
            error=f"{exc.code().name}: {exc.details()}",
        )


def run_confirmation_gate(
    copilot_stub,
    cart_stub,
    product_id: str,
    product_name: str,
    deadline: float,
) -> dict:
    suffix = uuid.uuid4().hex[:10]
    user_id = f"e2e-gate-{suffix}"
    session_id = f"e2e-gate-session-{suffix}"

    before, before_latency = get_cart(cart_stub, user_id, deadline)
    started = time.perf_counter()
    phase_one = copilot_stub.ChatWithCopilot(
        copilot_pb.ChatWithCopilotRequest(
            question=f"Add one {product_name} to my cart.",
            user_id=user_id,
            session_id=session_id,
        ),
        timeout=deadline,
    )
    gate_latency = time.perf_counter() - started
    after_gate, after_gate_latency = get_cart(cart_stub, user_id, deadline)

    has_pending = phase_one.HasField("pending_confirmation")
    gate_tools = [action.tool_name for action in phase_one.actions_taken]
    pending_arguments = (
        json.loads(phase_one.pending_confirmation.arguments_json)
        if has_pending
        else {}
    )
    confirmed = False
    confirmation_latency = 0.0
    after_confirmation = after_gate
    confirmation_tools: list[str] = []
    if has_pending:
        started = time.perf_counter()
        phase_two = copilot_stub.ChatWithCopilot(
            copilot_pb.ChatWithCopilotRequest(
                question="",
                user_id=user_id,
                session_id=session_id,
                confirmation_token=phase_one.pending_confirmation.confirmation_token,
            ),
            timeout=deadline,
        )
        confirmation_latency = time.perf_counter() - started
        confirmation_tools = [action.tool_name for action in phase_two.actions_taken]
        after_confirmation, _ = get_cart(cart_stub, user_id, deadline)
        confirmed = any(
            item_product_id == product_id and quantity >= 1
            for item_product_id, quantity in after_confirmation
        )

    unchanged_before_confirmation = before == after_gate
    return {
        "user_id": user_id,
        "product_id": product_id,
        "product_name": product_name,
        "gate_tools": gate_tools,
        "pending_arguments": pending_arguments,
        "pending_confirmation_returned": has_pending,
        "pending_product_id_correct": pending_arguments.get("product_id") == product_id,
        "unchanged_before_confirmation": unchanged_before_confirmation,
        "written_after_confirmation": confirmed,
        "passed": (
            has_pending
            and pending_arguments.get("product_id") == product_id
            and unchanged_before_confirmation
            and confirmed
        ),
        "gate_latency_s": gate_latency,
        "confirmation_latency_s": confirmation_latency,
        "cart_read_before_latency_ms": round(before_latency * 1000, 3),
        "cart_read_after_gate_latency_ms": round(after_gate_latency * 1000, 3),
        "confirmation_tools": confirmation_tools,
        "cart_before": before,
        "cart_after_gate": after_gate,
        "cart_after_confirmation": after_confirmation,
    }


def markdown_report(target: str, cart_target: str, summaries: dict, gate: dict) -> str:
    lines = [
        "# Shopping Copilot Real gRPC End-to-End Latency",
        "",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
        f"- Shopping Copilot target: `{target}`",
        f"- Cart verification target: `{cart_target}`",
        "- Path: gRPC client -> Shopping Copilot -> Bedrock -> real downstream gRPC tool -> Bedrock -> gRPC client.",
        "",
        "| Intent | Expected tool | Pass | n | E2E P50 (s) | E2E P95 (s) | Tool gRPC P50 (ms) | Tool gRPC P95 (ms) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, expected_tool in (
        ("catalog_search", "search_products"),
        ("product_reviews", "get_product_reviews"),
        ("cart_read", "get_cart"),
    ):
        row = summaries[key]
        lines.append(
            f"| {key} | `{expected_tool}` | {row['passed']}/{row['n']} | {row['n']} | "
            f"{row['latency_p50_s']:.3f} | {row['latency_p95_s']:.3f} | "
            f"{row['tool_latency_p50_ms']:.1f} | {row['tool_latency_p95_ms']:.1f} |"
        )
    lines.extend([
        "",
        "## Confirmation gate",
        "",
        f"- Pending token returned: `{gate['pending_confirmation_returned']}`",
        f"- Pending product ID correct: `{gate['pending_product_id_correct']}`",
        f"- Cart unchanged before confirmation: `{gate['unchanged_before_confirmation']}`",
        f"- Cart written only after confirmation: `{gate['written_after_confirmation']}`",
        f"- Gate result: `{'PASS' if gate['passed'] else 'FAIL'}`",
        f"- Gate/confirmation latency: `{gate['gate_latency_s']:.3f}s/{gate['confirmation_latency_s']:.3f}s`",
        "",
        "Notes:",
        "- Bedrock model selection and AWS region are owned by the target Shopping Copilot process.",
        "- Tool latency comes from `ToolCallRecord.duration_ms` emitted by the real agent.",
        "- This local E2E benchmark includes host-to-container networking; repeat in EKS for production network evidence.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--cart-addr", default="localhost:7070")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--deadline", type=float, default=45.0)
    parser.add_argument("--product-id", default="1YMWWN1N4O")
    parser.add_argument("--product-name", default="Eclipsmart Travel Refractor Telescope")
    parser.add_argument("--markdown-out")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    target = f"{args.host}:{args.port}"
    copilot_channel = grpc.insecure_channel(target)
    cart_channel = grpc.insecure_channel(args.cart_addr)
    copilot_stub = copilot_pb_grpc.ShoppingCopilotServiceStub(copilot_channel)
    cart_stub = demo_pb2_grpc.CartServiceStub(cart_channel)

    cases = [
        EvalCase("catalog_search", "Find telescope products under 100 USD.", "search_products"),
        EvalCase(
            "product_reviews",
            f"Show me customer reviews for product {args.product_id}.",
            "get_product_reviews",
        ),
        EvalCase("cart_read", "What is currently in my cart?", "get_cart"),
    ]

    samples_by_case: dict[str, list[Sample]] = {}
    for case in cases:
        samples = []
        print(f"\n== {case.key}: expected {case.expected_tool} ({args.n} samples) ==", flush=True)
        for index in range(args.n):
            sample = run_case(copilot_stub, case, index, args.deadline)
            samples.append(sample)
            print(
                f"{index + 1:02d}/{args.n}: latency={sample.latency_s:.3f}s "
                f"tools={sample.tool_names} degraded={sample.degraded} pass={sample.passed} "
                f"error={sample.error}",
                flush=True,
            )
        samples_by_case[case.key] = samples

    print("\n== confirmation_gate ==", flush=True)
    gate = run_confirmation_gate(
        copilot_stub,
        cart_stub,
        args.product_id,
        args.product_name,
        args.deadline,
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2), flush=True)

    summaries = {key: summarize(samples) for key, samples in samples_by_case.items()}
    report = markdown_report(target, args.cart_addr, summaries, gate)
    print("\n" + report, flush=True)

    raw = {
        "target": target,
        "cart_target": args.cart_addr,
        "n": args.n,
        "summaries": summaries,
        "samples": {
            key: [asdict(sample) for sample in samples]
            for key, samples in samples_by_case.items()
        },
        "confirmation_gate": gate,
    }
    if args.markdown_out:
        Path(args.markdown_out).write_text(report, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    all_passed = all(row["passed"] == row["n"] for row in summaries.values()) and gate["passed"]
    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
