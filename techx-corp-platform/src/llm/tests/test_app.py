import json
import sys
import unittest
from pathlib import Path


LLM_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LLM_DIR))

import app as llm_app  # noqa: E402


SHOPPING_TOOLS = [
    {"type": "function", "function": {"name": "search_products"}},
    {"type": "function", "function": {"name": "get_product_reviews"}},
    {"type": "function", "function": {"name": "get_cart"}},
    {"type": "function", "function": {"name": "add_to_cart"}},
]


class LLMShoppingCopilotTest(unittest.TestCase):
    def setUp(self):
        self.client = llm_app.app.test_client()

    def post_chat(self, messages):
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "techx-llm",
                "messages": messages,
                "tools": SHOPPING_TOOLS,
                "tool_choice": "auto",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def tool_call(self, question):
        payload = self.post_chat(
            [
                {"role": "system", "content": "You are Shopping Copilot."},
                {"role": "user", "content": f"user_id=user-1 session_id=session-1\nQuestion: {question}"},
            ]
        )
        return payload["choices"][0]["message"]["tool_calls"][0]

    def test_vietnamese_search_maps_to_search_products(self):
        tool_call = self.tool_call("Tôi muốn tìm kính thiên văn du lịch")

        self.assertEqual(tool_call["function"]["name"], "search_products")
        self.assertEqual(json.loads(tool_call["function"]["arguments"])["query"], "telescope")

    def test_reviews_maps_to_get_product_reviews(self):
        tool_call = self.tool_call("Review của TEL1234567 thế nào?")

        self.assertEqual(tool_call["function"]["name"], "get_product_reviews")
        self.assertEqual(json.loads(tool_call["function"]["arguments"])["product_id"], "TEL1234567")

    def test_cart_question_maps_to_get_cart(self):
        tool_call = self.tool_call("Giỏ hàng của tôi đang có gì?")

        self.assertEqual(tool_call["function"]["name"], "get_cart")

    def test_add_to_cart_maps_to_confirmation_tool(self):
        tool_call = self.tool_call("Thêm 2 cái camera vào giỏ")
        arguments = json.loads(tool_call["function"]["arguments"])

        self.assertEqual(tool_call["function"]["name"], "add_to_cart")
        self.assertEqual(arguments["query"], "camera")
        self.assertEqual(arguments["quantity"], 2)

    def test_tool_result_is_summarized(self):
        payload = self.post_chat(
            [
                {"role": "system", "content": "You are Shopping Copilot."},
                {"role": "user", "content": "user_id=user-1 session_id=session-1\nQuestion: Find telescope"},
                {
                    "role": "tool",
                    "name": "search_products",
                    "content": json.dumps(
                        {
                            "products": [
                                {"id": "TEL1234567", "name": "Travel Telescope"},
                            ]
                        }
                    ),
                },
            ]
        )

        content = payload["choices"][0]["message"]["content"]
        self.assertIn("Travel Telescope", content)


if __name__ == "__main__":
    unittest.main()
