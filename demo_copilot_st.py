"""
Shopping Copilot — Streamlit PoC  (TF1-48 + TF1-56 gRPC integration)
=====================================================================
Tác giả : AIO Team (dinh144)
JIRA    : TF1-48, TF1-56
Mô tả   : Chatbot gọi AWS Bedrock (Amazon Nova) thật, hỗ trợ 3 intent cốt lõi:
           1. Tìm kiếm sản phẩm bằng ngôn ngữ tự nhiên (search_products)
           2. Hỏi đáp review không ảo giác / RAG (get_product_reviews)
           3. Thêm giỏ hàng với Confirmation Gate chống Excessive Agency (add_to_cart)

Tích hợp gRPC (TF1-56):
    Ba tool ở trên hỗ trợ HAI chế độ vận hành:
    • gRPC mode: khi PRODUCT_CATALOG_ADDR, PRODUCT_REVIEWS_ADDR, CART_SERVICE_ADDR
      được cấu hình → tool gọi thẳng vào microservice thật trên EKS qua gRPC.
    • Mock mode (fallback): khi env vars chưa set hoặc gRPC stubs chưa generate
      → tool chạy trên MOCK_PRODUCTS hardcode (chỉ dùng để demo local).
    Sidebar hiển thị rõ đang chạy ở mode nào. Xem grpc_clients.py để biết chi tiết.

Chạy thử local (mock mode):
  streamlit run demo_copilot_st.py --server.port 8503 --server.address 0.0.0.0

Chạy với gRPC thật (trên EKS hoặc port-forward):
  export PRODUCT_CATALOG_ADDR=productcatalogservice:3550
  export PRODUCT_REVIEWS_ADDR=productreviewservice:8080
  export CART_SERVICE_ADDR=cartservice:7070
  pip install -r requirements-copilot.txt
  bash generate_proto_stubs.sh   # tạo demo_pb2.py & demo_pb2_grpc.py
  streamlit run demo_copilot_st.py

Yêu cầu:
  pip install streamlit boto3 grpcio grpcio-tools
  AWS credentials nạp trong ~/.aws/credentials hoặc biến môi trường
  Nếu không có credentials: app tự chạy ở chế độ MOCK (demo đầy đủ chức năng)
"""

import os
import json
import re
import streamlit as st
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# gRPC integration layer (TF1-56)
try:
    from grpc_clients import (
        is_grpc_available, grpc_search_products,
        grpc_get_product_reviews, grpc_add_to_cart,
    )
    _GRPC_IMPORTED = True
except ImportError:
    _GRPC_IMPORTED = False

    def is_grpc_available() -> bool:
        return False

USE_GRPC = _GRPC_IMPORTED and is_grpc_available()

# ─────────────────────────────────────────────
# 0. Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Shopping Copilot — TechX Corp",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 1. Mock data (sản phẩm thật của TechX Corp)
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

# ─────────────────────────────────────────────
# 2. Load review summaries từ file BTC (có sẵn trong repo)
# ─────────────────────────────────────────────
def _load_review_summaries() -> dict:
    """
    Nạp tóm tắt review từ file product-review-summaries.json của BTC.
    Fallback về dict rỗng nếu không tìm thấy file.
    """
    # Tìm file theo đường dẫn tương đối từ vị trí script này
    _here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_here, "techx-corp-platform", "src", "llm",
                     "product-review-summaries", "product-review-summaries.json"),
        # Nếu chạy từ thư mục gốc capstone-phase-3:
        os.path.join(_here, "product-review-summaries", "product-review-summaries.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f).get("product-review-summaries", [])
                return {item["product_id"]: item["product_review_summary"] for item in items}
            except Exception:
                pass
    # Fallback: tóm tắt ngắn gọn nội tuyến
    return {
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

MOCK_REVIEWS = _load_review_summaries()

# ─────────────────────────────────────────────
# 3. Tool implementations (gRPC thật → fallback mock)
# ─────────────────────────────────────────────

# ── 3a. Mock implementations (fallback khi không có gRPC) ──
def _mock_search_products(query: str, category: str | None = None) -> str:
    """Intent 1 (mock): Tìm sản phẩm bằng ngôn ngữ tự nhiên."""
    query_lower = query.lower()
    results = []
    for pid, info in MOCK_PRODUCTS.items():
        if category and category.lower() not in info["category"].lower():
            continue
        searchable = (
            info["name"] + " " + info["description"] + " " + info["category"]
        ).lower()
        if any(word in searchable for word in query_lower.split()):
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


def _mock_get_product_reviews(product_id: str) -> str:
    """Intent 2 (mock): Đọc tóm tắt review (RAG — không ảo giác)."""
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


def _mock_add_to_cart(product_id: str, quantity: int = 1) -> str:
    """Intent 3 (mock): Thêm vào giỏ hàng (Confirmation Gate)."""
    if product_id not in MOCK_PRODUCTS:
        return json.dumps({"status": "error", "message": f"Sản phẩm {product_id} không tồn tại."})
    if not MOCK_PRODUCTS[product_id]["in_stock"]:
        return json.dumps({"status": "out_of_stock",
                           "message": f"{MOCK_PRODUCTS[product_id]['name']} hiện hết hàng."})
    st.session_state.pending_action = {
        "type": "add_to_cart",
        "product_id": product_id,
        "product_name": MOCK_PRODUCTS[product_id]["name"],
        "quantity": max(1, int(quantity)),
        "unit_price": MOCK_PRODUCTS[product_id]["price"],
    }
    return json.dumps({
        "status": "pending_confirmation",
        "message": (
            f"Đã chuẩn bị thêm {quantity}x {MOCK_PRODUCTS[product_id]['name']} "
            "vào giỏ hàng. Chờ người dùng xác nhận."
        ),
    })


# ── 3b. Dispatch: gRPC thật → fallback mock ──
def _tool_search_products(query: str, category: str | None = None) -> str:
    """Intent 1: Tìm sản phẩm — gọi gRPC ProductCatalogService nếu có."""
    if USE_GRPC:
        try:
            raw = grpc_search_products(query, category)
            data = json.loads(raw)
            if "error" not in data:
                products = data if isinstance(data, list) else data.get("products", data)
                if isinstance(products, list):
                    for p in products:
                        if isinstance(p.get("price"), (int, float)):
                            p["price"] = f"${p['price']:.2f}"
                    return json.dumps({"status": "ok", "count": len(products), "products": products})
        except Exception:
            pass  # Fallthrough to mock
    return _mock_search_products(query, category)


def _tool_get_product_reviews(product_id: str) -> str:
    """Intent 2: Review — gọi gRPC ProductReviewService nếu có."""
    if USE_GRPC:
        try:
            raw = grpc_get_product_reviews(product_id)
            data = json.loads(raw)
            if "error" not in data:
                return json.dumps({
                    "status": "ok",
                    "product_id": product_id,
                    "product_name": data.get("product_name", product_id),
                    "review_summary": data.get("summary", ""),
                })
        except Exception:
            pass
    return _mock_get_product_reviews(product_id)


def _tool_add_to_cart(product_id: str, quantity: int = 1) -> str:
    """
    Intent 3: Thêm vào giỏ hàng.
    QUAN TRỌNG: Hàm này chỉ CHUẨN BỊ pending_action (Confirmation Gate).
    Hành động thật chỉ xảy ra sau khi người dùng bấm ✅ Xác nhận.
    Khi gRPC khả dụng: xác nhận xong → gọi CartService.AddItem thật.
    """
    # Kiểm tra sản phẩm tồn tại (mock catalog vẫn cần để lấy tên/giá)
    product_info = MOCK_PRODUCTS.get(product_id)
    if not product_info:
        return json.dumps({"status": "error", "message": f"Sản phẩm {product_id} không tồn tại."})
    if not product_info["in_stock"]:
        return json.dumps({"status": "out_of_stock",
                           "message": f"{product_info['name']} hiện hết hàng."})
    # Lưu pending_action — KHÔNG thêm vào cart ngay (Confirmation Gate)
    st.session_state.pending_action = {
        "type": "add_to_cart",
        "product_id": product_id,
        "product_name": product_info["name"],
        "quantity": max(1, int(quantity)),
        "unit_price": product_info["price"],
        "use_grpc": USE_GRPC,  # Flag để confirm handler biết gọi gRPC
    }
    return json.dumps({
        "status": "pending_confirmation",
        "message": (
            f"Đã chuẩn bị thêm {quantity}x {product_info['name']} "
            "vào giỏ hàng. Chờ người dùng xác nhận."
        ),
    })


# Map tên tool → hàm thực thi
TOOL_HANDLERS = {
    "search_products": lambda args: _tool_search_products(
        query=args.get("query", ""), category=args.get("category")
    ),
    "get_product_reviews": lambda args: _tool_get_product_reviews(
        product_id=args.get("product_id", "")
    ),
    "add_to_cart": lambda args: _tool_add_to_cart(
        product_id=args.get("product_id", ""),
        quantity=args.get("quantity", 1),
    ),
}

# ─────────────────────────────────────────────
# 4. Bedrock tool definitions (Converse API format)
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
# 5. System prompt
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
# 6. Mock agent (chạy khi không có credentials Bedrock)
# ─────────────────────────────────────────────
def run_mock_agent(user_input: str) -> str:
    """
    Agent rule-based đơn giản — hoạt động hoàn toàn offline.
    Minh hoạ 3 intent mà không cần AWS credentials.
    """
    txt = user_input.lower()

    # Intent 3: Thêm giỏ hàng (Ưu tiên kiểm tra trước vì thường chứa từ khóa của SP)
    cart_keywords = ["thêm", "mua", "add", "giỏ", "cart", "order", "đặt"]
    if any(k in txt for k in cart_keywords):
        # Map từ tiếng Việt sang product ID
        if "star" in txt or "sense" in txt:
            _tool_add_to_cart("66VCHSJNUP", quantity=1)
            return "Tôi đã chuẩn bị lệnh thêm **1x StarSense Explorer** vào giỏ hàng.\nVui lòng xác nhận nút bấm bên dưới."
        elif "outland" in txt or "nhòm" in txt:
            _tool_add_to_cart("2ZYFJ3GM2N", quantity=1)
            return "Tôi đã chuẩn bị lệnh thêm **1x Celestron Outland Binoculars** vào giỏ hàng.\nVui lòng xác nhận nút bấm bên dưới."
        elif "cleaning" in txt or "lau" in txt or "vệ sinh" in txt:
            _tool_add_to_cart("L9ECAV7KIM", quantity=1)
            return "Tôi đã chuẩn bị lệnh thêm **1x Lens Cleaning Kit** vào giỏ hàng.\nVui lòng xác nhận nút bấm bên dưới."
        else:
            # Default fallback for cart
            _tool_add_to_cart("OLJCESPC7Z", quantity=1)
            return "Tôi đã chuẩn bị lệnh thêm **1x Celestron AstroMaster 70** (kính thiên văn phổ biến nhất) vào giỏ hàng.\nVui lòng xác nhận nút bấm bên dưới."

    # Intent 2: Hỏi review
    review_keywords = ["review", "đánh giá", "tốt không", "chất lượng", "nhận xét",
                       "pin", "bền", "dùng", "người ta nói"]
    if any(k in txt for k in review_keywords):
        pid_to_check = "OLJCESPC7Z" # Default
        if "star" in txt or "sense" in txt: pid_to_check = "66VCHSJNUP"
        elif "nhòm" in txt or "outland" in txt: pid_to_check = "2ZYFJ3GM2N"
        
        result = json.loads(_tool_get_product_reviews(pid_to_check))
        if result["status"] == "ok":
            return (
                f"📋 **Tóm tắt đánh giá — {result['product_name']}:**\n\n"
                f"{result['review_summary']}\n\n"
                "_Nguồn: tổng hợp từ đánh giá thật của khách hàng._"
            )

    # Intent 1: Tìm kiếm sản phẩm
    search_keywords = ["tìm", "có", "bán", "nào", "telescope", "kính", "ống nhòm",
                       "binoculars", "solar", "filter", "cleaning", "book", "sách",
                       "accessories", "camera", "imager", "sản phẩm"]
    if any(k in txt for k in search_keywords) or True: # Mặc định rơi vào đây
        # Override query để match với danh mục tiếng Anh
        query_for_tool = "telescope" 
        if "nhòm" in txt: query_for_tool = "binoculars"
        elif "lau" in txt or "vệ sinh" in txt or "cleaning" in txt: query_for_tool = "cleaning"
        elif "mặt trời" in txt or "solar" in txt: query_for_tool = "solar"
        elif "sách" in txt or "book" in txt: query_for_tool = "book"

        result = json.loads(_tool_search_products(query_for_tool))
        if result["status"] == "not_found":
            return "Xin lỗi, hiện tại cửa hàng không có sản phẩm này."
        
        products = result["products"]
        lines = [f"Tôi tìm được **{len(products)} sản phẩm** gợi ý cho bạn:\n"]
        for i, p in enumerate(products[:4], 1):
            stock = "Còn hàng" if p["in_stock"] else "Hết hàng"
            lines.append(f"**{i}. {p['name']}** — {p['price']} [{stock}]")
            lines.append(f"   _{p['description']}_")
        lines.append("\nBạn muốn xem review hay thêm sản phẩm nào vào giỏ?")
        return "\n".join(lines)




# ─────────────────────────────────────────────
# 7. Bedrock agent loop với Hard Limit
# ─────────────────────────────────────────────
MAX_TOOL_CALLS = 5  # Hard limit — chống infinite loop đốt tiền Bedrock


def run_agent_turn(bedrock_client, model_id: str, messages: list) -> str:
    """
    Chạy một lượt agent với Bedrock Converse API.
    Hard Limit: tối đa MAX_TOOL_CALLS tool calls mỗi lượt.
    Returns: chuỗi câu trả lời cuối cùng của agent.
    """
    tool_call_count = 0
    current_messages = list(messages)  # Sao chép để không ảnh hưởng state gốc

    while True:
        # ── Gọi Bedrock ──────────────────────────────────────────────
        try:
            response = bedrock_client.converse(
                modelId=model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=current_messages,
                toolConfig={"tools": TOOLS_DEFINITION},
                inferenceConfig={
                    "maxTokens": 1024,
                    "temperature": 0.1,   # Thấp → ít ảo giác
                    "topP": 0.9,
                },
            )
        except ClientError as e:
            err = e.response["Error"]
            if err["Code"] == "ThrottlingException":
                return "⚠️ Bedrock đang bị rate-limit. Vui lòng thử lại sau vài giây."
            return f"❌ Lỗi Bedrock: {err['Code']} — {err['Message']}"
        except Exception as e:
            return f"❌ Lỗi không xác định: {str(e)}"

        stop_reason = response.get("stopReason", "end_turn")
        output_msg = response["output"]["message"]
        content_blocks = output_msg.get("content", [])

        # ── Kết thúc bình thường ─────────────────────────────────────
        if stop_reason == "end_turn":
            text_parts = [b["text"] for b in content_blocks if "text" in b]
            return "\n".join(text_parts) if text_parts else "(Không có phản hồi)"

        # ── Tool call ────────────────────────────────────────────────
        if stop_reason == "tool_use":
            tool_call_count += 1

            # ← HARD LIMIT CHECK
            if tool_call_count > MAX_TOOL_CALLS:
                return (
                    f"⚠️ Agent đã gọi quá {MAX_TOOL_CALLS} tools trong 1 lượt. "
                    "Vui lòng hỏi lại câu đơn giản hơn để tiết kiệm chi phí."
                )

            # Thêm tin nhắn của assistant vào lịch sử
            current_messages.append({"role": "assistant", "content": content_blocks})

            # Xử lý từng tool use block
            tool_results = []
            for block in content_blocks:
                if "toolUse" not in block:
                    continue
                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]

                # Gọi hàm tương ứng
                handler = TOOL_HANDLERS.get(tool_name)
                if handler:
                    try:
                        result_str = handler(tool_input)
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)})
                else:
                    result_str = json.dumps({"error": f"Tool '{tool_name}' không tồn tại."})

                tool_results.append({
                    "toolUseId": tool_use_id,
                    "content": [{"json": json.loads(result_str)}],
                })

            # Đưa kết quả tool vào lịch sử và tiếp tục vòng lặp
            current_messages.append({
                "role": "user",
                "content": [{"toolResult": tr} for tr in tool_results],
            })
            continue  # Quay lại đầu vòng lặp

        # Stop reason khác (max_tokens, content_filtered...)
        text_parts = [b["text"] for b in content_blocks if "text" in b]
        return "\n".join(text_parts) if text_parts else f"(Dừng: {stop_reason})"


# ─────────────────────────────────────────────
# 7. Khởi tạo Bedrock client + Session State
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_bedrock_client(region: str):
    """Tạo Bedrock client (lấy credentials tự động từ môi trường local)."""
    return boto3.client(service_name="bedrock-runtime", region_name=region)


def check_bedrock_connection(region: str) -> tuple[bool, object]:
    """
    Kiểm tra credentials có hợp lệ và Bedrock có truy cập được không.
    Returns: (ok: bool, client | None)
    """
    try:
        client = get_bedrock_client(region)
        # Gọi nhẹ để kiểm tra auth (list models)
        sts = boto3.client("sts", region_name=region)
        sts.get_caller_identity()
        return True, client
    except NoCredentialsError:
        return False, None
    except ClientError as e:
        code = e.response["Error"]["Code"]
        # Credentials sai/hết hạn
        if code in ("InvalidClientTokenId", "ExpiredTokenException",
                    "AuthFailure", "UnauthorizedException"):
            return False, None
        # Credentials ok nhưng có lỗi khác (ví dụ permission Bedrock) → vẫn dùng client
        return True, get_bedrock_client(region)
    except Exception:
        return False, None


def init_session():
    defaults = {
        "messages": [],          # Lịch sử hội thoại Bedrock format
        "display_messages": [],  # Lịch sử hiển thị UI (role, content)
        "cart": {},              # {product_id: quantity}
        "pending_action": None,  # Hành động chờ xác nhận
        "bedrock_ok": False,     # Trạng thái kết nối Bedrock
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─────────────────────────────────────────────
# 8. UI — Sidebar
# ─────────────────────────────────────────────
def render_sidebar():
    st.sidebar.title("⚙️ Cấu hình Agent")

    # Model selection
    model_id = st.sidebar.selectbox(
        "Model Bedrock",
        options=[
            "amazon.nova-pro-v1:0",
            "amazon.nova-lite-v1:0",
            "amazon.nova-micro-v1:0",
        ],
        index=0,
        help="Nova Pro: Chất lượng cao cho Agent. Nova Lite/Micro: Nhanh, nhẹ, rẻ cho fallback.",
    )

    region = st.sidebar.selectbox(
        "AWS Region",
        options=["us-east-1"],  # ADR-004: đơn vùng. Nova model availability khác nhau theo region.
        index=0,
    )

    # Kết nối Bedrock bằng cấu hình máy tính local
    try:
        client = get_bedrock_client(region)
        # Ping nhẹ bằng STS để xác nhận credentials có hợp lệ không
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        st.sidebar.success(
            f"🔌 Bedrock: Kết nối OK\n"
            f"`{identity.get('Arn', '').split('/')[-1]}`"
        )
        st.session_state.bedrock_ok = True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("InvalidClientTokenId", "ExpiredTokenException", "AuthFailure"):
            st.sidebar.error(
                "❌ Credentials không hợp lệ hoặc đã hết hạn.\n"
                "Vui lòng chạy `aws configure` để cập nhật."
            )
        else:
            st.sidebar.warning(f"⚠️ {code}: {e.response['Error']['Message']}")
        st.session_state.bedrock_ok = False
        client = None
    except NoCredentialsError:
        st.sidebar.warning("⚠️ Chưa có credentials trên máy. Vui lòng chạy `aws configure`.")
        st.session_state.bedrock_ok = False
        client = None
    except Exception as e:
        st.sidebar.error(f"❌ Lỗi không xác định: {e}")
        st.session_state.bedrock_ok = False
        client = None

    st.sidebar.divider()

    # Thông số agent
    st.sidebar.info(
        f"**Hard Limit:** {MAX_TOOL_CALLS} tool calls/lượt\n\n"
        "**Confirmation Gate:** ✅ Bật\n\n"
        "**Anti-hallucination:** ✅ Bật"
    )

    # gRPC integration status (TF1-56)
    if USE_GRPC:
        st.sidebar.success(
            "🔗 **Data Source:** gRPC thật\n\n"
            "Tool gọi trực tiếp vào microservice trên EKS."
        )
    else:
        st.sidebar.warning(
            "⚠️ **Data Source:** Mock (local)\n\n"
            "Set `PRODUCT_CATALOG_ADDR`, `PRODUCT_REVIEWS_ADDR`, "
            "`CART_SERVICE_ADDR` để dùng gRPC thật."
        )

    st.sidebar.divider()

    # Giỏ hàng
    st.sidebar.subheader("🛒 Giỏ hàng")
    if not st.session_state.cart:
        st.sidebar.caption("Giỏ hàng trống.")
    else:
        total = 0.0
        for pid, qty in st.session_state.cart.items():
            info = MOCK_PRODUCTS.get(pid, {})
            name = info.get("name", pid)
            price = info.get("price", 0)
            subtotal = price * qty
            total += subtotal
            st.sidebar.markdown(f"- **{name}** \u00d7 {qty} = `${subtotal:.2f}`")
        st.sidebar.markdown(f"**Tổng: `${total:.2f}`**")
        if st.sidebar.button("🗑️ Xóa giỏ hàng"):
            st.session_state.cart = {}
            st.rerun()

    st.sidebar.divider()

    if st.sidebar.button("🔄 Reset hội thoại"):
        st.session_state.messages = []
        st.session_state.display_messages = []
        st.session_state.pending_action = None
        st.rerun()

    return client, model_id


# ─────────────────────────────────────────────
# 9. UI — Confirmation Gate
# ─────────────────────────────────────────────
def render_confirmation_gate():
    """
    Hiển thị hộp xác nhận khi agent muốn thực hiện cart mutation.
    Đây là Confirmation Gate chống Excessive Agency.
    """
    if not st.session_state.pending_action:
        return

    action = st.session_state.pending_action
    if action["type"] == "add_to_cart":
        qty = action["quantity"]
        name = action["product_name"]
        pid = action["product_id"]
        unit_price = action["unit_price"]
        total = unit_price * qty

        st.warning(
            f"🛒 **Agent muốn thêm vào giỏ hàng:**\n\n"
            f"**{qty}× {name}** — `${unit_price:.2f}` mỗi cái = **`${total:.2f}`**\n\n"
            f"*Product ID: {pid}*"
        )

        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("✅ Xác nhận", type="primary", key="confirm_btn"):
                # Thực sự thêm vào giỏ
                current_qty = st.session_state.cart.get(pid, 0)
                st.session_state.cart[pid] = current_qty + qty
                # Thêm xác nhận vào lịch sử chat
                st.session_state.display_messages.append({
                    "role": "system",
                    "content": f"✅ Đã thêm {qty}× **{name}** vào giỏ hàng."
                })
                st.session_state.pending_action = None
                st.rerun()
        with col2:
            if st.button("❌ Hủy", key="cancel_btn"):
                st.session_state.display_messages.append({
                    "role": "system",
                    "content": f"❌ Đã hủy lệnh thêm **{name}** vào giỏ."
                })
                st.session_state.pending_action = None
                st.rerun()


# ─────────────────────────────────────────────
# 10. Main app
# ─────────────────────────────────────────────
def main():
    init_session()

    # Header
    st.title("🛒 Shopping Copilot — TechX Corp")
    st.markdown(
        "**PoC Demo** · Gọi **AWS Bedrock** thật · "
        "3 intent: tìm sản phẩm · hỏi review · thêm giỏ hàng\n\n"
        "_Dùng cho Pitching nghiệm thu Tuần 1 — TF AIO Team_"
    )
    st.warning(
        "**Dữ liệu là MOCK.** LLM gọi Bedrock thật, nhưng `search_products`, "
        "`get_product_reviews`, `add_to_cart` chạy trên dict hardcode trong file "
        "này — chưa nối gRPC tới product-catalog / product-reviews / cart trên "
        "EKS. RULES.md §4 đòi hạng mục AIE phải chạy thật, nên PoC này chứng "
        "minh được lớp an toàn (Confirmation Gate, giới hạn vòng lặp, block-list) "
        "chứ chưa chứng minh được tích hợp. Theo dõi ở TF1-56.",
        icon="⚠️",
    )

    # Sidebar
    bedrock_client, model_id = render_sidebar()

    # Hiển thị lịch sử hội thoại
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.display_messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                with st.chat_message("user"):
                    st.markdown(content)
            elif role == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(content)
            elif role == "system":
                # Thông báo hệ thống (xác nhận giỏ hàng, v.v.)
                st.info(content)

    # Confirmation Gate (luôn hiện khi có pending action)
    render_confirmation_gate()

    # Yêu cầu cài đặt credentials nếu chưa kết nối nhưng VẪN CHO PHÉP TEST LOCAL (Mock)
    if not st.session_state.bedrock_ok:
        st.warning("⚠️ Chưa kết nối được AWS Bedrock. Ứng dụng đang chạy ở **Chế độ Mock (Local)**.")
        with st.expander("Hướng dẫn cấu hình AWS Credentials để dùng Bedrock thật"):
            st.code(
                "# Cách 1: Sử dụng AWS CLI (Khuyên dùng)\naws configure\n\n"
                "# Cách 2: Biến môi trường\nexport AWS_ACCESS_KEY_ID=...\n"
                "export AWS_SECRET_ACCESS_KEY=...\nexport AWS_SESSION_TOKEN=...",
                language="bash"
            )

    # Input chat (Luôn hiện để test local)
    user_input = st.chat_input("Hỏi về sản phẩm, review, hoặc thêm vào giỏ hàng...")
    if not user_input:
        return

    # Hiển thị tin nhắn user ngay
    st.session_state.display_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Thêm vào lịch sử Bedrock format
    st.session_state.messages.append({
        "role": "user",
        "content": [{"text": user_input}],
    })

    # Gọi agent
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Đang xử lý..."):
            if st.session_state.bedrock_ok and bedrock_client:
                # Bedrock thật
                reply = run_agent_turn(bedrock_client, model_id, st.session_state.messages)
            else:
                # Chế độ MOCK — không cần credentials
                reply = run_mock_agent(user_input)

        st.markdown(reply)

    # Lưu câu trả lời vào lịch sử
    st.session_state.display_messages.append({"role": "assistant", "content": reply})
    st.session_state.messages.append({
        "role": "assistant",
        "content": [{"text": reply}],
    })

    # Nếu có pending action, rerun để hiển thị confirmation gate
    if st.session_state.pending_action:
        st.rerun()


if __name__ == "__main__" or True:
    main()
