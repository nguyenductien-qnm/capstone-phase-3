#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_adapter.py — Gọi Bedrock Converse API thật, instrument tool calls
========================================================================
JIRA    : TF-64
Mô tả   : Module tách biệt khỏi Streamlit. Gọi Bedrock thật để chạy agent
           loop, ghi lại mọi tool call để eval đánh giá.

⚠️ NOTA BENE: Đây KHÔNG phải là nguồn evidence cho MANDATE-06.
File này dùng mock (không có DB thật, không qua pipeline thật), chỉ dùng
để test logic tool-calling (task success). Để lấy evidence thực tế cho
MANDATE-06, hãy dùng eval_mandate06_prod.py.

Dùng bởi : test_task_success_real.py
Yêu cầu : boto3, AWS credentials hợp lệ (KHÔNG fallback mock)
"""

import json
import os
import sys
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Path setup
# ─────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────
@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    tool_name: str
    args: dict
    result: dict


@dataclass
class AgentResult:
    """Full result of one agent turn."""
    tool_calls: list = field(default_factory=list)
    final_response: str = ""
    turn_count: int = 0
    latency_ms: float = 0.0
    error: str = ""


# ─────────────────────────────────────────────
# System prompt — copied from demo_copilot_st.py
# to avoid importing Streamlit module
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """Bạn là Shopping Copilot của TechX Corp — cửa hàng thiết bị thiên văn chuyên nghiệp.
Nhiệm vụ của bạn: giúp khách tìm sản phẩm, đọc review, và thêm vào giỏ hàng.

QUY TẮC BẮT BUỘC:
1. NGẮN GỌN: Trả lời súc tích, tối đa 3-4 câu mỗi lượt.
2. KHÔNG ẢO GIÁC: Mọi thông tin về review PHẢI đến từ tool get_product_reviews. Không bịa.
   Nếu tool trả về không có thông tin, nói: "Tôi không có thông tin đánh giá về sản phẩm này."
3. CONFIRMATION GATE: Khi gọi add_to_cart, bạn PHẢI nói:
   "Tôi đã chuẩn bị lệnh thêm [Tên SP] vào giỏ. Vui lòng xác nhận nút bấm bên dưới."
   KHÔNG nói đã thêm thành công khi người dùng chưa bấm xác nhận.
4. ĐA LƯỢT: Nhớ ngữ cảnh hội thoại. Khi người dùng nói "cái đầu tiên", "nó", "thêm nữa"
   — hiểu theo ngữ cảnh, không hỏi lại những gì đã biết.
5. TÌM KIẾM TRƯỚC KHI TRẢ LỜI: Khi được hỏi về sản phẩm, luôn gọi search_products.
"""

# ─────────────────────────────────────────────
# Tool definitions — same as demo_copilot_st.py
# ─────────────────────────────────────────────
TOOLS_DEFINITION = [
    {
        "toolSpec": {
            "name": "search_products",
            "description": (
                "Tìm kiếm sản phẩm trong danh mục TechX Corp bằng từ khóa tự nhiên. "
                "Dùng khi người dùng hỏi 'có sản phẩm nào...', 'tìm kính thiên văn', v.v."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Từ khóa tìm kiếm (ví dụ: 'telescope for kids', 'solar filter')",
                        },
                        "category": {
                            "type": "string",
                            "description": "Lọc theo danh mục: Telescopes, Binoculars, Accessories, Cameras, Books",
                        },
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_product_reviews",
            "description": (
                "Lấy tóm tắt đánh giá (review summary) của một sản phẩm cụ thể. "
                "Dùng để trả lời câu hỏi về chất lượng, ưu/nhược điểm của sản phẩm. "
                "KHÔNG bao giờ trả lời về review mà không gọi tool này trước."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "Product ID cụ thể (ví dụ: OLJCESPC7Z, L9ECAV7KIM)",
                        }
                    },
                    "required": ["product_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "add_to_cart",
            "description": (
                "Chuẩn bị thêm sản phẩm vào giỏ hàng. "
                "Gọi tool này khi người dùng yêu cầu thêm sản phẩm. "
                "Sau khi gọi tool, hành động sẽ CHỜ xác nhận từ người dùng — "
                "KHÔNG thực hiện ngay. Thông báo cho người dùng xác nhận nút bấm ở dưới."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "Product ID cần thêm vào giỏ",
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "Số lượng (mặc định 1)",
                            "default": 1,
                        },
                    },
                    "required": ["product_id"],
                }
            },
        }
    },
]


# ─────────────────────────────────────────────
# Mock product data (same as demo_copilot_st.py)
# — needed for tool handlers to return realistic
#   results without importing Streamlit module
# ─────────────────────────────────────────────
MOCK_PRODUCTS = {
    "OLJCESPC7Z": {
        "name": "Celestron AstroMaster 70",
        "price": 49.99,
        "category": "Telescopes",
        "description": "Entry-level refractor telescope for beginners and casual stargazing.",
        "in_stock": True,
    },
    "66VCHSJNUP": {
        "name": "StarSense Explorer Refractor",
        "price": 179.99,
        "category": "Telescopes",
        "description": "Smartphone-integrated telescope with StarSense auto-alignment app.",
        "in_stock": True,
    },
    "1YMWWN1N4O": {
        "name": "Solar Eclipse Telescope",
        "price": 89.99,
        "category": "Telescopes",
        "description": "Dedicated solar scope with built-in Solar Safe ISO filter.",
        "in_stock": True,
    },
    "L9ECAV7KIM": {
        "name": "Celestron Lens Cleaning Kit",
        "price": 15.49,
        "category": "Accessories",
        "description": "Complete cleaning kit for telescopes, binoculars, and camera lenses.",
        "in_stock": True,
    },
    "2ZYFJ3GM2N": {
        "name": "Celestron Outland X 10x42 Binoculars",
        "price": 65.00,
        "category": "Binoculars",
        "description": "Waterproof roof prism binoculars with ED glass for crisp, clear images.",
        "in_stock": True,
    },
    "6E92ZMYYFZ": {
        "name": "EclipSmart Solar Filter 8-inch",
        "price": 19.95,
        "category": "Accessories",
        "description": "ISO 12312-2 compliant solar filter for Celestron 8-inch telescopes.",
        "in_stock": True,
    },
    "LS4PSXUNUM": {
        "name": "NightVision Pro 3-in-1",
        "price": 39.99,
        "category": "Accessories",
        "description": "Red flashlight + hand warmer + power bank for astronomy sessions.",
        "in_stock": True,
    },
    "9SIQT8TOJO": {
        "name": "Celestron RASA V2 Astrograph",
        "price": 1299.00,
        "category": "Telescopes",
        "description": "f/2.2 Rowe-Ackermann Schmidt Astrograph for deep-sky imaging.",
        "in_stock": False,
    },
    "0PUK6V6EV0": {
        "name": "Celestron Skyris Color Imager",
        "price": 149.00,
        "category": "Cameras",
        "description": "Solar system color imager for planetary astrophotography.",
        "in_stock": True,
    },
    "HQTGWGPNH4": {
        "name": "The Comet Book",
        "price": 24.99,
        "category": "Books",
        "description": "Historical account of comets and ancient astronomical thought.",
        "in_stock": True,
    },
}

MOCK_REVIEWS = {
    "OLJCESPC7Z": "Great entry-level telescope for beginners, easy setup, clear images of the Moon.",
    "66VCHSJNUP": "StarSense app makes alignment effortless. Excellent optics. Battery drain is minor.",
    "1YMWWN1N4O": "Perfect for solar viewing and eclipses. Compact, portable, ISO-certified filter.",
    "L9ECAV7KIM": "Versatile cleaning kit, safe for all optics. Great value, removes dust and fingerprints.",
    "2ZYFJ3GM2N": "Crisp, bright images. ED glass is outstanding. Lightweight, durable for outdoor use.",
    "6E92ZMYYFZ": "Essential solar filter, crystal-clear safe solar views. ISO compliant, sturdy Velcro straps.",
    "LS4PSXUNUM": "Red light preserves night vision. Hand warmer and power bank make it indispensable.",
    "9SIQT8TOJO": "Dream astrograph for deep-sky imaging. f/2.2 cuts exposure times dramatically.",
    "0PUK6V6EV0": "Stunning planetary images, great color. Straightforward setup, excellent resolution.",
    "HQTGWGPNH4": "Fascinating historical account of comets. Well-researched, unique collector's piece.",
}


# ─────────────────────────────────────────────
# Tool handler implementations (standalone, no Streamlit)
# ─────────────────────────────────────────────
def _handle_search_products(args: dict) -> str:
    """Tool handler: search_products — mock catalog search."""
    query = args.get("query", "").lower()
    category = args.get("category")
    results = []
    for pid, info in MOCK_PRODUCTS.items():
        if category and category.lower() not in info["category"].lower():
            continue
        searchable = (
            info["name"] + " " + info["description"] + " " + info["category"]
        ).lower()
        if any(word in searchable for word in query.split()):
            results.append({
                "product_id": pid,
                "name": info["name"],
                "price": f"${info['price']:.2f}",
                "category": info["category"],
                "in_stock": info["in_stock"],
                "description": info["description"],
            })
    if not results:
        return json.dumps({"status": "not_found", "message": "Không tìm thấy sản phẩm phù hợp."})
    return json.dumps({"status": "ok", "count": len(results), "products": results})


def _handle_get_product_reviews(args: dict) -> str:
    """Tool handler: get_product_reviews — return review summary."""
    product_id = args.get("product_id", "")
    if product_id not in MOCK_REVIEWS:
        return json.dumps({
            "status": "not_found",
            "message": f"Không có thông tin đánh giá cho sản phẩm {product_id}."
        })
    product_name = MOCK_PRODUCTS.get(product_id, {}).get("name", product_id)
    return json.dumps({
        "status": "ok",
        "product_id": product_id,
        "product_name": product_name,
        "review_summary": MOCK_REVIEWS[product_id],
    })


def _handle_add_to_cart(args: dict) -> str:
    """Tool handler: add_to_cart — return pending_confirmation (Confirmation Gate)."""
    product_id = args.get("product_id", "")
    quantity = args.get("quantity", 1)
    if product_id not in MOCK_PRODUCTS:
        return json.dumps({"status": "error", "message": f"Sản phẩm {product_id} không tồn tại."})
    if not MOCK_PRODUCTS[product_id]["in_stock"]:
        return json.dumps({"status": "out_of_stock",
                           "message": f"{MOCK_PRODUCTS[product_id]['name']} hiện hết hàng."})
    return json.dumps({
        "status": "pending_confirmation",
        "message": (
            f"Đã chuẩn bị thêm {quantity}x {MOCK_PRODUCTS[product_id]['name']} "
            "vào giỏ hàng. Chờ người dùng xác nhận."
        ),
    })


TOOL_HANDLERS = {
    "search_products": _handle_search_products,
    "get_product_reviews": _handle_get_product_reviews,
    "add_to_cart": _handle_add_to_cart,
}


# ─────────────────────────────────────────────
# Agent configuration
# ─────────────────────────────────────────────
MAX_TOOL_CALLS = 5
DEFAULT_MODEL_ID = "amazon.nova-pro-v1:0"
DEFAULT_REGION = "us-east-1"


# ─────────────────────────────────────────────
# Bedrock client factory
# ─────────────────────────────────────────────
def get_bedrock_client(region: str = DEFAULT_REGION):
    """Create a Bedrock runtime client. Raises if credentials are missing."""
    import boto3
    return boto3.client("bedrock-runtime", region_name=region)


def check_bedrock_credentials(region: str = DEFAULT_REGION) -> bool:
    """Check if AWS credentials are valid for Bedrock calls."""
    try:
        import boto3
        sts = boto3.client("sts", region_name=region)
        sts.get_caller_identity()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# Core: run_agent — Bedrock agent loop with instrumentation
# ─────────────────────────────────────────────
def run_agent(
    user_input: str,
    model_id: str = DEFAULT_MODEL_ID,
    region: str = DEFAULT_REGION,
    bedrock_client=None,
) -> AgentResult:
    """
    Run a single-turn agent conversation against Bedrock Converse API.

    This is equivalent to run_agent_turn() in demo_copilot_st.py but:
    - Does NOT depend on Streamlit
    - Instruments every tool call for eval
    - Fails loudly when credentials are missing (no mock fallback)

    Returns AgentResult with tool_calls, final_response, latency_ms.
    """
    if bedrock_client is None:
        bedrock_client = get_bedrock_client(region)

    result = AgentResult()
    start_time = time.time()

    messages = [
        {"role": "user", "content": [{"text": user_input}]}
    ]

    tool_call_count = 0

    try:
        while True:
            # Call Bedrock
            response = bedrock_client.converse(
                modelId=model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=messages,
                toolConfig={"tools": TOOLS_DEFINITION},
                inferenceConfig={
                    "maxTokens": 1024,
                    "temperature": 0.1,
                    "topP": 0.9,
                },
            )

            stop_reason = response.get("stopReason", "end_turn")
            output_msg = response["output"]["message"]
            content_blocks = output_msg.get("content", [])

            result.turn_count += 1

            # End of conversation
            if stop_reason == "end_turn":
                text_parts = [b["text"] for b in content_blocks if "text" in b]
                result.final_response = "\n".join(text_parts) if text_parts else "(Không có phản hồi)"
                break

            # Tool use
            if stop_reason == "tool_use":
                tool_call_count += 1
                if tool_call_count > MAX_TOOL_CALLS:
                    result.final_response = f"⚠️ Agent đã gọi quá {MAX_TOOL_CALLS} tools."
                    result.error = "max_tool_calls_exceeded"
                    break

                # Add assistant message to history
                messages.append({"role": "assistant", "content": content_blocks})

                # Process each tool use block
                tool_results = []
                for block in content_blocks:
                    if "toolUse" not in block:
                        continue
                    tool_use = block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})
                    tool_use_id = tool_use["toolUseId"]

                    # Execute tool handler
                    handler = TOOL_HANDLERS.get(tool_name)
                    if handler:
                        try:
                            result_str = handler(tool_input)
                        except Exception as e:
                            result_str = json.dumps({"error": str(e)})
                    else:
                        result_str = json.dumps({"error": f"Tool '{tool_name}' không tồn tại."})

                    parsed_result = json.loads(result_str)

                    # ★ Record tool call for eval
                    result.tool_calls.append(ToolCall(
                        tool_name=tool_name,
                        args=tool_input,
                        result=parsed_result,
                    ))

                    tool_results.append({
                        "toolUseId": tool_use_id,
                        "content": [{"json": parsed_result}],
                    })

                # Feed tool results back
                messages.append({
                    "role": "user",
                    "content": [{"toolResult": tr} for tr in tool_results],
                })
                continue

            # Other stop reasons
            text_parts = [b["text"] for b in content_blocks if "text" in b]
            result.final_response = "\n".join(text_parts) if text_parts else f"(Dừng: {stop_reason})"
            break

    except Exception as e:
        result.error = str(e)
        result.final_response = f"❌ Error: {e}"

    result.latency_ms = (time.time() - start_time) * 1000
    return result


# ─────────────────────────────────────────────
# CLI — quick smoke test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent Adapter — smoke test")
    parser.add_argument("query", nargs="?", default="Tìm kính thiên văn cho người mới",
                        help="User input to send to agent")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID, help="Bedrock model ID")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    args = parser.parse_args()

    print(f"Checking Bedrock credentials (region={args.region})...")
    if not check_bedrock_credentials(args.region):
        print("❌ AWS credentials not found or invalid. Cannot run agent.")
        sys.exit(1)

    print(f"Running agent with model={args.model}")
    print(f"Query: \"{args.query}\"\n")

    agent_result = run_agent(args.query, model_id=args.model, region=args.region)

    print(f"── Tool Calls ({len(agent_result.tool_calls)}) ──")
    for tc in agent_result.tool_calls:
        print(f"  {tc.tool_name}({tc.args}) → status={tc.result.get('status', 'N/A')}")

    print(f"\n── Response ──")
    print(agent_result.final_response)
    print(f"\n── Metrics ──")
    print(f"  Turns: {agent_result.turn_count}")
    print(f"  Latency: {agent_result.latency_ms:.0f}ms")
    if agent_result.error:
        print(f"  Error: {agent_result.error}")
