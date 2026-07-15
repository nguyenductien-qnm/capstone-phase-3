#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import threading
import time
import unicodedata
import uuid
from concurrent import futures

import grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc
from openai import OpenAI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pythonjsonlogger import jsonlogger

import demo_pb2
import demo_pb2_grpc
import shopping_copilot_pb2
import shopping_copilot_pb2_grpc


RPC_TIMEOUT_SECONDS = float(os.environ.get("SHOPPING_COPILOT_RPC_TIMEOUT_SECONDS", "2"))
CONFIRMATION_TTL_SECONDS = int(os.environ.get("SHOPPING_COPILOT_CONFIRMATION_TTL_SECONDS", "600"))
MAX_SEARCH_RESULTS = int(os.environ.get("SHOPPING_COPILOT_MAX_SEARCH_RESULTS", "5"))
MAX_TOOL_CALLS = int(os.environ.get("SHOPPING_COPILOT_MAX_TOOL_CALLS", "5"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("SHOPPING_COPILOT_LLM_TIMEOUT_SECONDS", "10"))

COPILOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the live product catalog for shopping products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A short semantic search query, translated to English when helpful.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of products to return.",
                        "minimum": 1,
                        "maximum": MAX_SEARCH_RESULTS,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_reviews",
            "description": "Fetch live reviews and average rating for one product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID when the user mentioned one.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Product search query when product_id is not known.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": "Fetch the current user's cart.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Prepare adding a product to the current user's cart. This must return a confirmation request and must not write until the user confirms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID when known.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Product search query when product_id is not known.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantity to add.",
                        "minimum": 1,
                        "maximum": 99,
                    },
                },
            },
        },
    },
]

SYSTEM_PROMPT = """
You are Shopping Copilot, an AI shopping assistant inside TechX.
You must use tools for live data. Do not invent products, reviews, prices, or cart contents.
Available operations:
- search_products: search the live catalog.
- get_product_reviews: fetch live product reviews and average score.
- get_cart: read the user's cart.
- add_to_cart: prepare a cart write, but the backend will require user confirmation before writing.
Never checkout, place orders, ship orders, empty carts, or delete cart items.
If the user asks for a forbidden write, refuse briefly.
When the user speaks Vietnamese or mixes Vietnamese and English, infer the meaning semantically and choose the right tool.
Keep final answers concise.
""".strip()

_pending_lock = threading.Lock()
_pending_confirmations = {}
_completed_confirmations = {}


def configure_logger():
    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    return logging.getLogger("shopping-copilot")


logger = configure_logger()
tracer = trace.get_tracer("shopping-copilot")


def must_map_env(key: str) -> str:
    value = os.environ.get(key)
    if value is None:
        raise RuntimeError(f"{key} environment variable must be set")
    return value


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.lower()


def compact_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def effective_user_id(request) -> str:
    return (request.user_id or request.session_id or "anonymous").strip()


def money_to_text(money) -> str:
    if money is None:
        return "n/a"
    amount = money.units + money.nanos / 1_000_000_000
    return f"{money.currency_code or 'USD'} {amount:.2f}"


def product_label(product) -> str:
    name = product.name or product.id
    return f"{name} ({product.id})"


def grpc_error_text(exc: grpc.RpcError) -> str:
    try:
        return f"{exc.code().name}: {exc.details()}"
    except Exception:
        return str(exc)


class ToolContext:
    def __init__(self, request):
        self.request = request
        self.records = []

    def record(
        self,
        tool_name: str,
        arguments: dict,
        succeeded: bool,
        started_at_unix: int | None = None,
        duration_ms: int = 0,
        error: str | None = None,
        audit_extra: dict | None = None,
    ):
        if started_at_unix is None:
            started_at_unix = int(time.time())
        arguments_json = compact_json(arguments)
        record = shopping_copilot_pb2.ToolCallRecord(
            tool_name=tool_name,
            arguments_json=arguments_json,
            succeeded=succeeded,
            started_at_unix=started_at_unix,
            duration_ms=duration_ms,
        )
        self.records.append(record)

        audit_payload = {
            "event": "copilot_tool_call",
            "tool_name": tool_name,
            "arguments_json": arguments_json,
            "succeeded": succeeded,
            "started_at_unix": started_at_unix,
            "duration_ms": duration_ms,
            "user_id": effective_user_id(self.request),
            "session_id": self.request.session_id,
        }
        if error:
            audit_payload["error"] = error
        if audit_extra:
            audit_payload.update(audit_extra)
        logger.info(compact_json(audit_payload))

    def call(self, tool_name: str, arguments: dict, callback):
        started_at_unix = int(time.time())
        started = time.perf_counter()
        succeeded = False
        error = None

        try:
            result = callback()
            succeeded = True
            return result
        except grpc.RpcError as exc:
            error = grpc_error_text(exc)
            raise
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.record(
                tool_name=tool_name,
                arguments=arguments,
                succeeded=succeeded,
                started_at_unix=started_at_unix,
                duration_ms=duration_ms,
                error=error,
            )


class ShoppingCopilotService(shopping_copilot_pb2_grpc.ShoppingCopilotServiceServicer):
    def __init__(self, product_catalog_stub, product_reviews_stub, cart_stub, llm_client, llm_model):
        self.product_catalog_stub = product_catalog_stub
        self.product_reviews_stub = product_reviews_stub
        self.cart_stub = cart_stub
        self.llm_client = llm_client
        self.llm_model = llm_model

    def ChatWithCopilot(self, request, context):
        span = trace.get_current_span()
        span.set_attribute("app.user.id", effective_user_id(request))
        span.set_attribute("app.session.id", request.session_id)
        tool_ctx = ToolContext(request)

        try:
            if request.confirmation_token:
                return self._handle_confirmation(request, tool_ctx)

            question = (request.question or "").strip()
            if not question:
                return self._response("Please ask a shopping question.", tool_ctx.records)

            return self._run_llm_agent(request, question, tool_ctx, span)
        except grpc.RpcError as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, grpc_error_text(exc)))
            return self._response(
                f"Downstream service error while handling the request: {grpc_error_text(exc)}",
                tool_ctx.records,
                degraded=True,
            )
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.exception("Unhandled Shopping Copilot error")
            return self._response(
                "Shopping Copilot could not process the request. Please try again later.",
                tool_ctx.records,
                degraded=True,
            )

    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(status=health_pb2.HealthCheckResponse.SERVING)

    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)

    def _contains_forbidden_write(self, question: str) -> bool:
        normalized = normalize_text(question)
        blocked_terms = (
            "checkout", "place order", "ship order", "empty cart", "delete cart",
            "xoa gio", "xoa het gio", "thanh toan", "dat hang", "giao hang",
        )
        return any(term in normalized for term in blocked_terms)

    def _run_llm_agent(self, request, question: str, tool_ctx: ToolContext, span):
        if self._contains_forbidden_write(question):
            return self._response(
                "I can search products, review products, view carts, and prepare add-to-cart confirmations. "
                "I will not checkout, place orders, ship orders, or empty carts.",
                tool_ctx.records,
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"user_id={effective_user_id(request)} session_id={request.session_id}\n"
                    f"Question: {question}"
                ),
            },
        ]

        for loop_index in range(MAX_TOOL_CALLS):
            span.set_attribute("app.copilot.loop_index", loop_index)
            llm_response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                tools=COPILOT_TOOLS,
                tool_choice="auto",
                timeout=LLM_TIMEOUT_SECONDS,
            )
            response_message = llm_response.choices[0].message
            tool_calls = response_message.tool_calls or []

            logger.info(
                compact_json(
                    {
                        "event": "copilot_llm_turn",
                        "model": self.llm_model,
                        "tool_call_count": len(tool_calls),
                        "loop_index": loop_index,
                        "user_id": effective_user_id(request),
                        "session_id": request.session_id,
                    }
                )
            )

            if not tool_calls:
                content = response_message.content or "I could not produce an answer for that request."
                return self._response(content, tool_ctx.records)

            messages.append(response_message)
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                if tool_name == "add_to_cart":
                    return self._prepare_add_to_cart_from_args(request, arguments, tool_ctx)

                tool_result = self._execute_read_tool(request, tool_name, arguments, tool_ctx)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_result,
                    }
                )

        return self._response(
            "I could not finish the request within the tool-call limit. Please try a more specific shopping question.",
            tool_ctx.records,
            degraded=True,
        )

    def _execute_read_tool(self, request, tool_name: str, arguments: dict, tool_ctx: ToolContext) -> str:
        if tool_name == "search_products":
            return self._search_products_json(arguments, tool_ctx)
        if tool_name == "get_product_reviews":
            return self._get_product_reviews_json(arguments, tool_ctx)
        if tool_name == "get_cart":
            return self._get_cart_json(request, tool_ctx)
        raise ValueError(f"Unsupported tool call requested by LLM: {tool_name}")

    def _response(self, text: str, actions, pending_confirmation=None, degraded=False):
        response = shopping_copilot_pb2.ChatWithCopilotResponse(
            response=text,
            degraded=degraded,
        )
        response.actions_taken.extend(actions)
        if pending_confirmation is not None:
            response.pending_confirmation.CopyFrom(pending_confirmation)
        return response

    def _find_products(self, question: str, tool_ctx: ToolContext):
        response = tool_ctx.call(
            "search_products",
            {"query": question},
            lambda: self.product_catalog_stub.SearchProducts(
                demo_pb2.SearchProductsRequest(query=question),
                timeout=RPC_TIMEOUT_SECONDS,
            ),
        )
        return list(response.results)

    def _product_to_dict(self, product) -> dict:
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": money_to_text(product.price_usd),
            "categories": list(product.categories),
        }

    def _search_products_json(self, arguments: dict, tool_ctx: ToolContext) -> str:
        query = str(arguments.get("query") or "").strip()
        limit = int(arguments.get("limit") or MAX_SEARCH_RESULTS)
        limit = max(1, min(limit, MAX_SEARCH_RESULTS))
        if not query:
            return compact_json({"error": "query is required"})

        products = self._find_products(query, tool_ctx)
        return compact_json(
            {
                "products": [self._product_to_dict(product) for product in products[:limit]],
                "count": min(len(products), limit),
            }
        )

    def _get_product(self, product_id: str, tool_ctx: ToolContext):
        return tool_ctx.call(
            "get_product",
            {"product_id": product_id},
            lambda: self.product_catalog_stub.GetProduct(
                demo_pb2.GetProductRequest(id=product_id),
                timeout=RPC_TIMEOUT_SECONDS,
            ),
        )

    def _resolve_product_from_args(self, arguments: dict, tool_ctx: ToolContext):
        product_id = str(arguments.get("product_id") or "").strip()
        if product_id:
            product = self._get_product(product_id, tool_ctx)
            return product.id, product

        query = str(arguments.get("query") or "").strip()
        if not query:
            return None, None

        products = self._find_products(query, tool_ctx)
        if not products:
            return None, None
        product = products[0]
        return product.id, product

    def _get_product_reviews_json(self, arguments: dict, tool_ctx: ToolContext) -> str:
        product_id, product = self._resolve_product_from_args(arguments, tool_ctx)
        if not product_id:
            return compact_json({"error": "product_id or query is required"})

        reviews_response = tool_ctx.call(
            "get_product_reviews",
            {"product_id": product_id},
            lambda: self.product_reviews_stub.GetProductReviews(
                demo_pb2.GetProductReviewsRequest(product_id=product_id),
                timeout=RPC_TIMEOUT_SECONDS,
            ),
        )
        avg_response = tool_ctx.call(
            "get_average_product_review_score",
            {"product_id": product_id},
            lambda: self.product_reviews_stub.GetAverageProductReviewScore(
                demo_pb2.GetAverageProductReviewScoreRequest(product_id=product_id),
                timeout=RPC_TIMEOUT_SECONDS,
            ),
        )

        return compact_json(
            {
                "product": self._product_to_dict(product) if product else {"id": product_id},
                "average_score": avg_response.average_score,
                "reviews": [
                    {
                        "username": review.username,
                        "description": review.description,
                        "score": review.score,
                    }
                    for review in reviews_response.product_reviews
                ],
            }
        )

    def _get_cart_json(self, request, tool_ctx: ToolContext) -> str:
        user_id = effective_user_id(request)
        cart = tool_ctx.call(
            "get_cart",
            {"user_id": user_id},
            lambda: self.cart_stub.GetCart(
                demo_pb2.GetCartRequest(user_id=user_id),
                timeout=RPC_TIMEOUT_SECONDS,
            ),
        )
        return compact_json(
            {
                "user_id": user_id,
                "items": [
                    {"product_id": item.product_id, "quantity": item.quantity}
                    for item in cart.items
                ],
            }
        )

    def _prepare_add_to_cart_from_args(self, request, arguments: dict, tool_ctx: ToolContext):
        product_id, product = self._resolve_product_from_args(arguments, tool_ctx)
        if not product_id:
            tool_ctx.record(
                "add_to_cart",
                arguments,
                False,
                error="product_not_found",
                audit_extra={"pending_confirmation_required": True},
            )
            return self._response(
                "I could not find a live catalog product to add. Please specify the product more clearly.",
                tool_ctx.records,
            )

        try:
            quantity = int(arguments.get("quantity") or 1)
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(1, min(quantity, 99))

        user_id = effective_user_id(request)
        args = {
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
        }
        token = uuid.uuid4().hex
        expires_at = int(time.time()) + CONFIRMATION_TTL_SECONDS
        human_prompt = f"Do you agree to add {quantity} x {product_label(product)} to your cart?"

        pending = {
            "tool_name": "add_item_to_cart",
            "arguments": args,
            "user_id": user_id,
            "session_id": request.session_id,
            "human_prompt": human_prompt,
            "expires_at_unix": expires_at,
        }
        with _pending_lock:
            _pending_confirmations[token] = pending

        pending_confirmation = shopping_copilot_pb2.PendingConfirmation(
            tool_name="add_item_to_cart",
            arguments_json=compact_json(args),
            human_prompt=human_prompt,
            confirmation_token=token,
            expires_at_unix=expires_at,
        )
        tool_ctx.record(
            "add_to_cart",
            args,
            True,
            audit_extra={
                "pending_confirmation_required": True,
                "confirmation_token": token,
                "write_deferred": True,
            },
        )
        logger.info(
            compact_json(
                {
                    "event": "copilot_pending_confirmation_created",
                    "tool_name": "add_item_to_cart",
                    "arguments_json": compact_json(args),
                    "confirmation_token": token,
                    "expires_at_unix": expires_at,
                    "user_id": user_id,
                    "session_id": request.session_id,
                }
            )
        )
        return self._response(
            "Confirmation is required before I modify the cart.",
            tool_ctx.records,
            pending_confirmation=pending_confirmation,
        )

    def _handle_confirmation(self, request, tool_ctx: ToolContext):
        token = request.confirmation_token.strip()
        user_id = effective_user_id(request)
        now = int(time.time())

        with _pending_lock:
            completed = _completed_confirmations.get(token)
            if completed:
                return self._response(completed["response"], tool_ctx.records)

            pending = _pending_confirmations.get(token)
            if not pending:
                return self._response("The confirmation token is unknown or already expired.", tool_ctx.records)
            if pending["expires_at_unix"] < now:
                del _pending_confirmations[token]
                return self._response("The confirmation token expired. Please ask me to prepare the cart update again.", tool_ctx.records)
            if pending["user_id"] != user_id:
                return self._response("The confirmation token belongs to a different user/session.", tool_ctx.records)

        if pending["tool_name"] != "add_item_to_cart":
            return self._response("This confirmation token is not for an allowed cart action.", tool_ctx.records)

        args = pending["arguments"]
        tool_ctx.call(
            "add_item_to_cart",
            args,
            lambda: self.cart_stub.AddItem(
                demo_pb2.AddItemRequest(
                    user_id=args["user_id"],
                    item=demo_pb2.CartItem(
                        product_id=args["product_id"],
                        quantity=args["quantity"],
                    ),
                ),
                timeout=RPC_TIMEOUT_SECONDS,
            ),
        )

        text = f"Confirmed. Added {args['quantity']} x {args['product_id']} to the cart."
        with _pending_lock:
            _pending_confirmations.pop(token, None)
            _completed_confirmations[token] = {
                "response": text,
                "completed_at_unix": int(time.time()),
            }

        return self._response(text, tool_ctx.records)


def build_server():
    product_catalog_addr = must_map_env("PRODUCT_CATALOG_ADDR")
    product_reviews_addr = must_map_env("PRODUCT_REVIEWS_ADDR")
    llm_base_url = must_map_env("LLM_BASE_URL")
    llm_api_key = must_map_env("OPENAI_API_KEY")
    llm_model = must_map_env("LLM_MODEL")
    cart_addr = os.environ.get("CART_ADDR") or os.environ.get("CART_SERVICE_ADDR")
    if not cart_addr:
        raise RuntimeError("CART_ADDR environment variable must be set")

    product_catalog_channel = grpc.insecure_channel(product_catalog_addr)
    product_reviews_channel = grpc.insecure_channel(product_reviews_addr)
    cart_channel = grpc.insecure_channel(cart_addr)
    llm_client = OpenAI(base_url=llm_base_url, api_key=llm_api_key)

    service = ShoppingCopilotService(
        demo_pb2_grpc.ProductCatalogServiceStub(product_catalog_channel),
        demo_pb2_grpc.ProductReviewServiceStub(product_reviews_channel),
        demo_pb2_grpc.CartServiceStub(cart_channel),
        llm_client,
        llm_model,
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    shopping_copilot_pb2_grpc.add_ShoppingCopilotServiceServicer_to_server(service, server)
    health_pb2_grpc.add_HealthServicer_to_server(service, server)
    return server


if __name__ == "__main__":
    service_name = os.environ.get("OTEL_SERVICE_NAME", "shopping-copilot")
    tracer = trace.get_tracer_provider().get_tracer(service_name)

    server = build_server()
    port = os.environ.get("SHOPPING_COPILOT_PORT", "50051")
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logger.info(f"Shopping Copilot service started, listening on port {port}")
    server.wait_for_termination()
