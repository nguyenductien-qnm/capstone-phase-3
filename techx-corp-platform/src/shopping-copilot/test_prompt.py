import agent
agent.SYSTEM_PROMPT = agent.SYSTEM_PROMPT.replace(
    '4. CONFIRMATION GATE: khi gọi add_item_to_cart, KHÔNG được nói đã thêm thành công.\n   Phải nói: "Tôi đã chuẩn bị thêm [SP] vào giỏ. Vui lòng xác nhận để thực hiện."',
    '4. CONFIRMATION GATE: KHÔNG được nói đã thêm thành công. Bắt buộc phải gọi tool add_item_to_cart, sau đó trả lời: "Tôi đã chuẩn bị thêm [SP] vào giỏ. Vui lòng xác nhận để thực hiện."'
)
from bedrock_client import create_bedrock_runtime_client
client = create_bedrock_runtime_client(region_name="us-east-1")
res = agent.run_agent(client, "amazon.nova-pro-v1:0", [{"role": "user", "content": [{"text": "Thêm 1 kính thiên văn National Park Foundation Explorascope vào giỏ hàng"}]}], "test-user")
print(res)
