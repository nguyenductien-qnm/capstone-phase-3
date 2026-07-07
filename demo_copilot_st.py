import streamlit as st
import boto3
import json
import os

# Set page config
st.set_page_config(
    page_title="Shopping Copilot (AIO03 PoC)",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 Shopping Copilot - AI Agent Prototype")
st.markdown("""
Bản Demo chạy thử (PoC) Trợ lý mua sắm AI dành cho buổi **Pitching nghiệm thu Tuần 1**.
Agent kết nối tới **AWS Bedrock thật** để gọi các công cụ (Tool Calling) tìm kiếm sản phẩm, đọc review và điều khiển giỏ hàng.
""")

# Initialize session states
if "messages" not in st.session_state:
    st.session_state.messages = []
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

# Sidebar configs
st.sidebar.header("⚙️ Cấu hình Agent")

# Model selection from active Bedrock models list
model_option = st.sidebar.selectbox(
    "Chọn Model Bedrock",
    [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "anthropic.claude-sonnet-4-20250514-v1:0"
    ]
)

# Connect to Bedrock
try:
    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime",
        region_name="us-west-2"
    )
    st.sidebar.success("🔌 Kết nối AWS Bedrock: OK")
except Exception as e:
    st.sidebar.error(f"❌ Lỗi kết nối AWS: {e}")

# Load mock catalog data
MOCK_PRODUCTS = {
    "OLJCESPC7Z": {"name": "Celestron Beginner Telescope", "price": 49.99, "category": "Telescopes", "description": "Entry-level telescope for stargazing beginners."},
    "66VCHSJNUP": {"name": "StarSense Refractor Telescope", "price": 179.99, "category": "Telescopes", "description": "Smartphone integrated telescope with StarSense App."},
    "1YMWWN1N4O": {"name": "Solar Eclipse Telescope", "price": 89.99, "category": "Telescopes", "description": "Dedicated solar scope with Solar Safe filter."},
    "L9ECAV7KIM": {"name": "Celestron Lens Cleaning Kit", "price": 15.49, "category": "Accessories", "description": "Cleaning kit for lenses, telescopes and binocular optics."},
    "2ZYFJ3GM2N": {"name": "Celestron Outland Binoculars", "price": 65.00, "category": "Binoculars", "description": "Waterproof roof binoculars for outdoor viewing."},
    "6E92ZMYYFZ": {"name": "EclipSmart Solar Filter", "price": 19.95, "category": "Accessories", "description": "ISO compliant solar filter for Celestron 8-inch telescopes."}
}

# Load mock review summaries
REVIEWS_FILE = "/home/dinh/capstone-phase-3/techx-corp-platform/src/llm/product-review-summaries/product-review-summaries.json"
try:
    with open(REVIEWS_FILE, 'r') as f:
        reviews_data = json.load(f).get("product-review-summaries", [])
        MOCK_REVIEWS = {item["product_id"]: item["product_review_summary"] for item in reviews_data}
except Exception:
    MOCK_REVIEWS = {}

# System prompt defining Agent instructions
SYSTEM_PROMPT = """
You are the Shopping Copilot, a helpful AI shopping assistant for TechX Corp.
You have access to tools to search the product catalog, read reviews summaries, and manipulate the shopping cart.

RULES:
1. Always keep responses brief, polite, and directly answer the question.
2. Ground all answers about reviews in the tool results. Do not hallucinate. If no reviews are found, say "Tôi không có thông tin đánh giá về sản phẩm này".
3. For action that alters the cart (adding or removing items):
   - You MUST call the `add_to_cart` tool.
   - Do NOT tell the user you have already completed the action until the user confirms it in the UI.
   - Just say: "Tôi đã chuẩn bị lệnh thêm [Tên sản phẩm] vào giỏ hàng. Vui lòng xác nhận nút bấm ở dưới."
"""

# Define Bedrock converse tools
tools_definition = [
    {
        "toolSpec": {
            "name": "search_products",
            "description": "Tìm kiếm sản phẩm trong danh mục bằng từ khóa tự nhiên hoặc danh mục sản phẩm.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Từ khóa tìm kiếm (ví dụ: kính thiên văn, telescope, binoculars)"},
                        "max_price": {"type": "number", "description": "Bộ lọc giá tối đa (ví dụ: 50)"}
                    },
                    "required": ["query"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_product_reviews",
            "description": "Đọc bản tóm tắt review đánh giá của khách hàng về một sản phẩm.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Mã ID của sản phẩm (ví dụ: OLJCESPC7Z)"}
                    },
                    "required": ["product_id"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "add_to_cart",
            "description": "Thêm sản phẩm và số lượng tương ứng vào giỏ hàng.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Mã ID của sản phẩm cần mua"},
                        "quantity": {"type": "integer", "description": "Số lượng cần thêm (ví dụ: 1, 2)"}
                    },
                    "required": ["product_id", "quantity"]
                }
            }
        }
    }
]

# Implement tool execution functions
def exec_tool(name, args):
    if name == "search_products":
        query = args.get("query", "").lower()
        max_price = args.get("max_price")
        
        matches = []
        for pid, p in MOCK_PRODUCTS.items():
            if query in p["name"].lower() or query in p["description"].lower() or query in p["category"].lower():
                if max_price is None or p["price"] <= max_price:
                    matches.append({"product_id": pid, **p})
        return json.dumps(matches)
        
    elif name == "get_product_reviews":
        pid = args.get("product_id")
        summary = MOCK_REVIEWS.get(pid, "Sản phẩm này chưa có đánh giá nào từ khách hàng.")
        return json.dumps({"product_id": pid, "summary": summary})
        
    elif name == "add_to_cart":
        pid = args.get("product_id")
        qty = args.get("quantity", 1)
        # Store in pending action state to trigger Confirmation Gate in Streamlit
        st.session_state.pending_action = {
            "action": "add_to_cart",
            "product_id": pid,
            "quantity": qty
        }
        return json.dumps({"status": "pending_user_confirmation", "message": "Yêu cầu xác nhận từ người dùng đã được kích hoạt."})
        
    return json.dumps({"error": "Tool không tồn tại"})

# Sidebar shopping cart view
st.sidebar.markdown("---")
st.sidebar.subheader("🛒 Giỏ hàng hiện tại")
if not st.session_state.cart:
    st.sidebar.caption("Giỏ hàng của bạn đang trống.")
else:
    total_cost = 0.0
    for pid, qty in st.session_state.cart.items():
        p = MOCK_PRODUCTS.get(pid, {"name": "Sản phẩm không rõ", "price": 0.0})
        item_total = p["price"] * qty
        total_cost += item_total
        st.sidebar.markdown(f"**{p['name']}** x{qty}  \n*{item_total:.2f} USD*")
    st.sidebar.markdown(f"**Tổng tiền:** `{total_cost:.2f} USD`")

# Render message history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle confirmation gate callback
if st.session_state.pending_action:
    action = st.session_state.pending_action
    p = MOCK_PRODUCTS.get(action["product_id"])
    
    if p:
        # Display the confirmation box inside the chatbot flow
        with st.chat_message("assistant"):
            st.warning(f"🛡️ **Confirmation Gate:** Bạn có đồng ý thêm **{action['quantity']}x {p['name']}** vào giỏ hàng với giá `{p['price'] * action['quantity']:.2f} USD` không?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Đồng ý và Thêm vào giỏ", key="confirm_yes"):
                    pid = action["product_id"]
                    qty = action["quantity"]
                    st.session_state.cart[pid] = st.session_state.cart.get(pid, 0) + qty
                    st.session_state.pending_action = None
                    st.session_state.messages.append({"role": "assistant", "content": f"Đã thêm thành công {qty}x {p['name']} vào giỏ hàng!"})
                    st.rerun()
            with col2:
                if st.button("❌ Hủy bỏ lệnh", key="confirm_no"):
                    st.session_state.pending_action = None
                    st.session_state.messages.append({"role": "assistant", "content": "Đã hủy bỏ hành động thêm vào giỏ hàng."})
                    st.rerun()

# Accept chat inputs
if prompt := st.chat_input("Hỏi Copilot: 'Tìm tai nghe dưới $50' hoặc 'Tóm tắt review Celestron'"):
    
    # Display user query
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Build Bedrock messages history
    bedrock_messages = []
    for msg in st.session_state.messages:
        # Converse API expects 'user' and 'assistant' roles
        role = "user" if msg["role"] == "user" else "assistant"
        bedrock_messages.append({
            "role": role,
            "content": [{"text": msg["content"]}]
        })
        
    # Call AWS Bedrock Converse
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        try:
            # First LLM Call
            response = bedrock_runtime.converse(
                modelId=model_option,
                messages=bedrock_messages,
                system=[{"text": SYSTEM_PROMPT}],
                toolConfig={"tools": tools_definition}
            )
            
            output_msg = response["output"]["message"]
            response_content = output_msg.get("content", [])
            
            # Check if LLM requested Tool Call
            tool_calls = [c["toolUse"] for c in response_content if "toolUse" in c]
            
            if tool_calls:
                # Append assistant's request for tool
                st.session_state.messages.append({"role": "assistant", "content": "Đang gọi các tool hệ thống để xử lý..."})
                
                # Execute tools and build response messages
                tool_results = []
                for tool in tool_calls:
                    tool_name = tool["name"]
                    tool_args = tool["input"]
                    tool_id = tool["toolUseId"]
                    
                    st.caption(f"🔧 Gọi tool: `{tool_name}` với tham số `{tool_args}`")
                    result_text = exec_tool(tool_name, tool_args)
                    
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"text": result_text}]
                        }
                    })
                
                # Append assistant message with tool calls and tool result message back to Bedrock history
                bedrock_messages.append(output_msg)
                bedrock_messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Second LLM Call to synthesize response with tool results
                second_response = bedrock_runtime.converse(
                    modelId=model_option,
                    messages=bedrock_messages,
                    system=[{"text": SYSTEM_PROMPT}],
                    toolConfig={"tools": tools_definition}
                )
                
                final_text = second_response["output"]["message"]["content"][0]["text"]
                response_placeholder.markdown(final_text)
                st.session_state.messages.append({"role": "assistant", "content": final_text})
                st.rerun()
                
            else:
                # No tools requested, output text response directly
                text_response = response_content[0]["text"]
                response_placeholder.markdown(text_response)
                st.session_state.messages.append({"role": "assistant", "content": text_response})
                
        except Exception as e:
            st.error(f"Lỗi xử lý Bedrock: {e}")
