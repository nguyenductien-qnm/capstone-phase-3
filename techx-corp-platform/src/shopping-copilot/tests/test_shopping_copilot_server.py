import json
import sys
import time
import unittest
from pathlib import Path

import grpc


SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

import demo_pb2  # noqa: E402
import shopping_copilot_pb2  # noqa: E402
import shopping_copilot_server as server  # noqa: E402


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = json.dumps(arguments)


class FakeToolCall:
    def __init__(self, name, arguments, call_id="call-1"):
        self.id = call_id
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeLLMResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Fake LLM received more calls than expected")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeLLMClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


class FakeProductCatalogStub:
    def __init__(self):
        self.search_queries = []
        self.get_product_ids = []
        self.products = {
            "TEL1234567": demo_pb2.Product(
                id="TEL1234567",
                name="Travel Telescope",
                description="Compact telescope for sky watching.",
                price_usd=demo_pb2.Money(currency_code="USD", units=49, nanos=990000000),
                categories=["telescopes"],
            ),
            "CAM1234567": demo_pb2.Product(
                id="CAM1234567",
                name="Action Camera",
                description="Water resistant action camera.",
                price_usd=demo_pb2.Money(currency_code="USD", units=89, nanos=0),
                categories=["cameras"],
            ),
        }

    def SearchProducts(self, request, timeout=None):
        self.search_queries.append((request.query, timeout))
        response = demo_pb2.SearchProductsResponse()
        query = request.query.lower()
        if "camera" in query:
            response.results.append(self.products["CAM1234567"])
        elif query:
            response.results.append(self.products["TEL1234567"])
        return response

    def GetProduct(self, request, timeout=None):
        self.get_product_ids.append((request.id, timeout))
        return self.products[request.id]


class FakeProductReviewsStub:
    def __init__(self):
        self.review_product_ids = []
        self.average_product_ids = []

    def GetProductReviews(self, request, timeout=None):
        self.review_product_ids.append((request.product_id, timeout))
        response = demo_pb2.GetProductReviewsResponse()
        response.product_reviews.add(
            username="linh",
            description="Clear view and easy setup.",
            score="5",
        )
        response.product_reviews.add(
            username="tai",
            description="Good for beginners.",
            score="4",
        )
        return response

    def GetAverageProductReviewScore(self, request, timeout=None):
        self.average_product_ids.append((request.product_id, timeout))
        return demo_pb2.GetAverageProductReviewScoreResponse(average_score="4.5")


class FakeCartStub:
    def __init__(self):
        self.get_cart_user_ids = []
        self.add_item_requests = []

    def GetCart(self, request, timeout=None):
        self.get_cart_user_ids.append((request.user_id, timeout))
        cart = demo_pb2.Cart(user_id=request.user_id)
        cart.items.add(product_id="TEL1234567", quantity=2)
        return cart

    def AddItem(self, request, timeout=None):
        self.add_item_requests.append((request, timeout))
        return demo_pb2.Empty()


class FakeRpcError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.UNAVAILABLE

    def details(self):
        return "cart service unavailable"


class FailingCartStub(FakeCartStub):
    def GetCart(self, request, timeout=None):
        raise FakeRpcError()


def llm_tool(name, arguments, call_id="call-1"):
    return FakeLLMResponse(FakeMessage(tool_calls=[FakeToolCall(name, arguments, call_id)]))


def llm_final(content):
    return FakeLLMResponse(FakeMessage(content=content, tool_calls=[]))


def request(question="", user_id="user-1", session_id="session-1", confirmation_token=""):
    return shopping_copilot_pb2.ChatWithCopilotRequest(
        user_id=user_id,
        session_id=session_id,
        question=question,
        confirmation_token=confirmation_token,
    )


class ShoppingCopilotLLMTest(unittest.TestCase):
    def setUp(self):
        server._pending_confirmations.clear()
        server._completed_confirmations.clear()
        self.catalog = FakeProductCatalogStub()
        self.reviews = FakeProductReviewsStub()
        self.cart = FakeCartStub()

    def make_service(self, responses, cart_stub=None):
        llm_client = FakeLLMClient(responses)
        svc = server.ShoppingCopilotService(
            self.catalog,
            self.reviews,
            cart_stub or self.cart,
            llm_client,
            "techx-llm",
        )
        return svc, llm_client

    def test_llm_search_products_with_vietnamese_semantic_query(self):
        svc, llm = self.make_service(
            [
                llm_tool("search_products", {"query": "telescope", "limit": 3}),
                llm_final("I found Travel Telescope in the live catalog."),
            ]
        )

        response = svc.ChatWithCopilot(request("Tôi muốn tìm kính thiên văn du lịch"), None)

        self.assertEqual(response.response, "I found Travel Telescope in the live catalog.")
        self.assertEqual(self.catalog.search_queries[0][0], "telescope")
        self.assertEqual(response.actions_taken[0].tool_name, "search_products")
        self.assertTrue(response.actions_taken[0].succeeded)
        self.assertEqual(len(llm.chat.completions.calls), 2)
        self.assertEqual(llm.chat.completions.calls[0]["tool_choice"], "auto")

    def test_llm_product_reviews_by_product_id(self):
        svc, _ = self.make_service(
            [
                llm_tool("get_product_reviews", {"product_id": "TEL1234567"}),
                llm_final("Travel Telescope has a 4.5 average rating."),
            ]
        )

        response = svc.ChatWithCopilot(request("Review của TEL1234567 thế nào?"), None)

        self.assertEqual(response.response, "Travel Telescope has a 4.5 average rating.")
        self.assertEqual(self.catalog.get_product_ids[0][0], "TEL1234567")
        self.assertEqual(self.reviews.review_product_ids[0][0], "TEL1234567")
        self.assertEqual(self.reviews.average_product_ids[0][0], "TEL1234567")
        self.assertEqual(
            [record.tool_name for record in response.actions_taken],
            ["get_product", "get_product_reviews", "get_average_product_review_score"],
        )

    def test_llm_product_reviews_by_query_resolves_product_first(self):
        svc, _ = self.make_service(
            [
                llm_tool("get_product_reviews", {"query": "camera"}),
                llm_final("Action Camera reviews are positive."),
            ]
        )

        response = svc.ChatWithCopilot(request("Có ai đánh giá camera này chưa?"), None)

        self.assertEqual(response.response, "Action Camera reviews are positive.")
        self.assertEqual(self.catalog.search_queries[0][0], "camera")
        self.assertEqual(self.reviews.review_product_ids[0][0], "CAM1234567")

    def test_llm_get_cart_uses_effective_user_id(self):
        svc, _ = self.make_service(
            [
                llm_tool("get_cart", {}),
                llm_final("Your cart has 2 Travel Telescope items."),
            ]
        )

        response = svc.ChatWithCopilot(request("Giỏ hàng của tôi đang có gì?"), None)

        self.assertEqual(response.response, "Your cart has 2 Travel Telescope items.")
        self.assertEqual(self.cart.get_cart_user_ids[0][0], "user-1")
        self.assertEqual(response.actions_taken[0].tool_name, "get_cart")

    def test_add_to_cart_requires_confirmation_before_cart_write(self):
        svc, _ = self.make_service(
            [
                llm_tool("add_to_cart", {"product_id": "TEL1234567", "quantity": 2}),
            ]
        )

        prepare_response = svc.ChatWithCopilot(request("Thêm kính này vào giỏ giúp tôi"), None)

        self.assertEqual(prepare_response.response, "Confirmation is required before I modify the cart.")
        self.assertTrue(prepare_response.HasField("pending_confirmation"))
        self.assertEqual(len(self.cart.add_item_requests), 0)
        self.assertEqual(prepare_response.pending_confirmation.tool_name, "add_item_to_cart")

        token = prepare_response.pending_confirmation.confirmation_token
        confirm_response = svc.ChatWithCopilot(request(confirmation_token=token), None)

        self.assertEqual(confirm_response.response, "Confirmed. Added 2 x TEL1234567 to the cart.")
        self.assertEqual(len(self.cart.add_item_requests), 1)
        add_request, timeout = self.cart.add_item_requests[0]
        self.assertEqual(add_request.user_id, "user-1")
        self.assertEqual(add_request.item.product_id, "TEL1234567")
        self.assertEqual(add_request.item.quantity, 2)
        self.assertEqual(confirm_response.actions_taken[0].tool_name, "add_item_to_cart")
        self.assertTrue(confirm_response.actions_taken[0].succeeded)

    def test_confirmation_token_is_idempotent(self):
        svc, _ = self.make_service(
            [
                llm_tool("add_to_cart", {"product_id": "TEL1234567", "quantity": 1}),
            ]
        )

        prepare_response = svc.ChatWithCopilot(request("Add one telescope to my cart"), None)
        token = prepare_response.pending_confirmation.confirmation_token

        first = svc.ChatWithCopilot(request(confirmation_token=token), None)
        second = svc.ChatWithCopilot(request(confirmation_token=token), None)

        self.assertEqual(first.response, second.response)
        self.assertEqual(len(self.cart.add_item_requests), 1)

    def test_confirmation_token_cannot_be_used_by_different_user(self):
        svc, _ = self.make_service(
            [
                llm_tool("add_to_cart", {"product_id": "TEL1234567", "quantity": 1}),
            ]
        )

        prepare_response = svc.ChatWithCopilot(request("Add one telescope to my cart"), None)
        token = prepare_response.pending_confirmation.confirmation_token
        response = svc.ChatWithCopilot(
            request(user_id="attacker", session_id="session-1", confirmation_token=token),
            None,
        )

        self.assertIn("different user/session", response.response)
        self.assertEqual(len(self.cart.add_item_requests), 0)

    def test_forbidden_checkout_does_not_call_llm_or_cart(self):
        svc, llm = self.make_service([])

        response = svc.ChatWithCopilot(request("Checkout và thanh toán giỏ hàng cho tôi"), None)

        self.assertIn("will not checkout", response.response)
        self.assertEqual(len(llm.chat.completions.calls), 0)
        self.assertEqual(len(self.cart.add_item_requests), 0)

    def test_empty_question_short_circuits_without_llm(self):
        svc, llm = self.make_service([])

        response = svc.ChatWithCopilot(request("   "), None)

        self.assertEqual(response.response, "Please ask a shopping question.")
        self.assertEqual(len(llm.chat.completions.calls), 0)

    def test_loop_limit_returns_degraded_response(self):
        responses = [
            llm_tool("search_products", {"query": f"telescope {index}"}, call_id=f"call-{index}")
            for index in range(server.MAX_TOOL_CALLS)
        ]
        svc, llm = self.make_service(responses)

        response = svc.ChatWithCopilot(request("Tìm kính thiên văn cho tôi"), None)

        self.assertTrue(response.degraded)
        self.assertIn("tool-call limit", response.response)
        self.assertEqual(len(llm.chat.completions.calls), server.MAX_TOOL_CALLS)
        self.assertEqual(len(response.actions_taken), server.MAX_TOOL_CALLS)

    def test_downstream_grpc_failure_is_degraded_and_audited(self):
        svc, _ = self.make_service([llm_tool("get_cart", {})], cart_stub=FailingCartStub())

        response = svc.ChatWithCopilot(request("Show my cart"), None)

        self.assertTrue(response.degraded)
        self.assertIn("Downstream service error", response.response)
        self.assertEqual(response.actions_taken[0].tool_name, "get_cart")
        self.assertFalse(response.actions_taken[0].succeeded)

    def test_unsupported_llm_tool_is_rejected_as_degraded(self):
        svc, _ = self.make_service([llm_tool("delete_cart", {})])

        response = svc.ChatWithCopilot(request("Can you help me with my shopping account?"), None)

        self.assertTrue(response.degraded)
        self.assertIn("could not process", response.response)
        self.assertEqual(len(self.cart.add_item_requests), 0)

    def test_llm_failure_returns_degraded_response(self):
        svc, _ = self.make_service([TimeoutError("LLM timeout")])

        response = svc.ChatWithCopilot(request("Find me a telescope"), None)

        self.assertTrue(response.degraded)
        self.assertIn("could not process", response.response)
        self.assertEqual(len(response.actions_taken), 0)

    def test_add_to_cart_by_query_resolves_product_before_confirmation(self):
        svc, _ = self.make_service(
            [
                llm_tool("add_to_cart", {"query": "camera", "quantity": 3}),
            ]
        )

        response = svc.ChatWithCopilot(request("Thêm camera này vào giỏ"), None)

        self.assertTrue(response.HasField("pending_confirmation"))
        self.assertEqual(self.catalog.search_queries[0][0], "camera")
        self.assertIn("CAM1234567", response.pending_confirmation.arguments_json)
        self.assertEqual(len(self.cart.add_item_requests), 0)
        self.assertEqual(response.actions_taken[0].tool_name, "search_products")

    def test_add_to_cart_quantity_is_clamped(self):
        svc, _ = self.make_service(
            [
                llm_tool("add_to_cart", {"product_id": "TEL1234567", "quantity": 500}),
            ]
        )

        response = svc.ChatWithCopilot(request("Add many telescopes"), None)
        args = json.loads(response.pending_confirmation.arguments_json)

        self.assertEqual(args["quantity"], 99)

    def test_malformed_tool_arguments_do_not_crash_service(self):
        bad_tool = FakeLLMResponse(
            FakeMessage(
                tool_calls=[
                    FakeToolCall("search_products", {}, "call-bad"),
                ]
            )
        )
        bad_tool.choices[0].message.tool_calls[0].function.arguments = "{not-json"
        svc, _ = self.make_service([bad_tool, llm_final("Please provide a clearer product query.")])

        response = svc.ChatWithCopilot(request("Tìm sản phẩm gì đó"), None)

        self.assertEqual(response.response, "Please provide a clearer product query.")
        self.assertEqual(len(response.actions_taken), 0)

    def test_local_agent_path_latency_budget(self):
        svc, _ = self.make_service(
            [
                llm_tool("search_products", {"query": "telescope"}),
                llm_final("Found Travel Telescope."),
            ]
        )

        started = time.perf_counter()
        response = svc.ChatWithCopilot(request("Tôi cần kính thiên văn"), None)
        elapsed_ms = (time.perf_counter() - started) * 1000

        self.assertEqual(response.response, "Found Travel Telescope.")
        self.assertLess(elapsed_ms, 100)


if __name__ == "__main__":
    unittest.main()
