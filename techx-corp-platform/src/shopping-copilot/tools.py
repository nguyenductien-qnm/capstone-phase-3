"""gRPC tool layer for the Shopping Copilot agent (TF1-59).

Each function is a *tool* the LLM may call. They wrap the real downstream
microservices over gRPC:

    search_products        -> ProductCatalogService.SearchProducts
    get_product_reviews    -> ProductReviewService.GetProductReviews
    get_cart               -> CartService.GetCart
    add_item_to_cart       -> CartService.AddItem   (write; gated, see agent.py)
    list_recommendations   -> RecommendationService.ListRecommendations

Design rules (w4-agentic-rag):
- Fail LOUD. A failed RPC returns an explicit ``{"error": ...}`` payload, never
  an empty success — a silent ``[]`` would let the LLM invent numbers.
- Read tools are safe to call autonomously. The single write tool
  (``add_item_to_cart``) is executed here only via :func:`execute_add_item`,
  which the server calls *after* the confirmation gate, never from the LLM loop.

Ported from ``copilot-poc/grpc_clients.py`` and extended with ``get_cart`` and a
user-scoped ``add_item``.
"""

import json
import logging
import os

import grpc
import demo_pb2
import demo_pb2_grpc

logger = logging.getLogger(__name__)

PRODUCT_CATALOG_ADDR = os.environ.get("PRODUCT_CATALOG_ADDR", "product-catalog:8080")
PRODUCT_REVIEWS_ADDR = os.environ.get("PRODUCT_REVIEWS_ADDR", "product-reviews:3551")
CART_SERVICE_ADDR = os.environ.get(
    "CART_SERVICE_ADDR",
    os.environ.get("CART_ADDR", "cart:8080"),
)

# Per-RPC deadline. Spec §6: 2s for microservice calls, increased to 5s to prevent timeouts.
_RPC_TIMEOUT = float(os.environ.get("COPILOT_RPC_TIMEOUT", "25.0"))


def _error_json(message: str) -> str:
    return json.dumps({
        "error": message,
        "message": "Lỗi hệ thống hoặc quá thời gian. TUYỆT ĐỐI DỪNG GỌI TOOL và trả lời khách hàng ngay lập tức."
    })


def _money_to_float(money) -> float:
    return money.units + money.nanos / 1e9


def _product_to_dict(product) -> dict:
    return {
        "product_id": product.id,
        "name": product.name,
        "price": _money_to_float(product.price_usd),
        "category": product.categories[0] if product.categories else "",
        "description": product.description,
    }


def search_products(query: str, category: str | None = None) -> str:
    """Intent 1 — natural-language product search via ProductCatalogService."""
    try:
        with grpc.insecure_channel(PRODUCT_CATALOG_ADDR) as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
            response = stub.SearchProducts(
                demo_pb2.SearchProductsRequest(query=query), timeout=_RPC_TIMEOUT
            )
        products = [_product_to_dict(p) for p in response.results]
        if category:
            cat = category.lower()
            products = [p for p in products if p.get("category", "").lower() == cat]
        if not products:
            return json.dumps({
                "status": "not_found", 
                "message": "Không tìm thấy sản phẩm. TUYỆT ĐỐI DỪNG TÌM KIẾM và trả lời khách hàng ngay lập tức.", 
                "products": []
            })
        for p in products:
            p["price"] = f"${p['price']:.2f}"
        return json.dumps({"status": "ok", "count": len(products), "products": products})
    except grpc.RpcError as e:
        logger.error("SearchProducts RPC failed: %s", e)
        return json.dumps({
            "error": f"SearchProducts failed: {e.code().name} – {e.details()}",
            "message": "Lỗi hệ thống hoặc quá thời gian. TUYỆT ĐỐI DỪNG TÌM KIẾM và trả lời khách hàng ngay lập tức."
        })
    except Exception as e:
        logger.error("search_products error: %s", e)
        return json.dumps({
            "error": str(e),
            "message": "Lỗi hệ thống. TUYỆT ĐỐI DỪNG TÌM KIẾM và trả lời khách hàng ngay lập tức."
        })


def get_product_reviews(product_id: str) -> str:
    """Intent 2 — grounded review Q&A via ProductReviewService.

    Returns the joined review text and average score so the LLM answers *from
    context*. When the product has no reviews, ``review_count`` is 0 and the
    agent must say it has no information (no fabrication).
    """
    try:
        with grpc.insecure_channel(PRODUCT_REVIEWS_ADDR) as channel:
            stub = demo_pb2_grpc.ProductReviewServiceStub(channel)
            response = stub.GetProductReviews(
                demo_pb2.GetProductReviewsRequest(product_id=product_id),
                timeout=_RPC_TIMEOUT,
            )
        reviews = response.product_reviews
        scores = []
        for r in reviews:
            try:
                scores.append(float(r.score))
            except (ValueError, TypeError):
                pass
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        summary = " | ".join(r.description for r in reviews if r.description)
        # demo.proto's ProductReview has no numeric id (see database.py fetch
        # query) -- username is the only per-review identifier available end to
        # end, kept here so citations can point back to a specific review
        # without a wider demo.proto/product-reviews schema change.
        citations = [
            {"review_id": r.username, "snippet": r.description, "score": r.score}
            for r in reviews if r.description
        ]
        return json.dumps({
            "status": "ok",
            "product_id": product_id,
            "average_score": avg,
            "review_count": len(reviews),
            "summary": summary or "No reviews available.",
            "citations": citations,
        })
    except grpc.RpcError as e:
        logger.error("GetProductReviews RPC failed: %s", e)
        return _error_json(f"GetProductReviews failed: {e.code().name} – {e.details()}")
    except Exception as e:
        logger.error("get_product_reviews error: %s", e)
        return _error_json(str(e))


def get_cart(user_id: str) -> str:
    """Intent 3 (read) — current cart contents via CartService.GetCart."""
    try:
        with grpc.insecure_channel(CART_SERVICE_ADDR) as channel:
            stub = demo_pb2_grpc.CartServiceStub(channel)
            cart = stub.GetCart(
                demo_pb2.GetCartRequest(user_id=user_id), timeout=_RPC_TIMEOUT
            )
        items = [{"product_id": i.product_id, "quantity": i.quantity} for i in cart.items]
        return json.dumps({"status": "ok", "user_id": user_id, "items": items})
    except grpc.RpcError as e:
        logger.error("GetCart RPC failed: %s", e)
        return _error_json(f"GetCart failed: {e.code().name} – {e.details()}")
    except Exception as e:
        logger.error("get_cart error: %s", e)
        return _error_json(str(e))


def execute_add_item(user_id: str, product_id: str, quantity: int) -> str:
    """Intent 3 (write) — CartService.AddItem.

    NOT a tool the LLM may invoke directly. The server calls this only after the
    user approves the confirmation gate (ADR-006 Tier-2 write). See agent.py.
    """
    try:
        with grpc.insecure_channel(CART_SERVICE_ADDR) as channel:
            stub = demo_pb2_grpc.CartServiceStub(channel)
            stub.AddItem(
                demo_pb2.AddItemRequest(
                    user_id=user_id,
                    item=demo_pb2.CartItem(product_id=product_id, quantity=int(quantity)),
                ),
                timeout=_RPC_TIMEOUT,
            )
        return json.dumps({
            "status": "success",
            "message": f"Added {quantity}x {product_id} to cart.",
        })
    except grpc.RpcError as e:
        logger.error("AddItem RPC failed: %s", e)
        return _error_json(f"AddItem failed: {e.code().name} – {e.details()}")
    except Exception as e:
        logger.error("execute_add_item error: %s", e)
        return _error_json(str(e))


def list_recommendations(product_ids: list[str]) -> str:
    """Intent 5 (read) — get AI recommendations for given product IDs via RecommendationService."""
    try:
        RECOMMENDATION_ADDR = os.environ.get("RECOMMENDATION_ADDR", "recommendation:8080")
        with grpc.insecure_channel(RECOMMENDATION_ADDR) as channel:
            stub = demo_pb2_grpc.RecommendationServiceStub(channel)
            response = stub.ListRecommendations(
                demo_pb2.ListRecommendationsRequest(product_ids=product_ids),
                timeout=_RPC_TIMEOUT,
            )
        return json.dumps({
            "status": "ok",
            "recommended_product_ids": list(response.product_ids)
        })
    except grpc.RpcError as e:
        logger.error("ListRecommendations RPC failed: %s", e)
        return _error_json(f"ListRecommendations failed: {e.code().name} – {e.details()}")
    except Exception as e:
        logger.error("list_recommendations error: %s", e)
        return _error_json(str(e))
