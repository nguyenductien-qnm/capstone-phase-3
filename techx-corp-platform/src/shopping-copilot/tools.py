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
import re
import urllib.request

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
        # Giữ ĐỦ nhãn: sản phẩm gắn nhiều category ("accessories,telescopes") mà chỉ
        # so khớp phần tử đầu thì bộ lọc dưới kia đánh rớt oan → agent báo "không có
        # sản phẩm nào" dù catalog có (đo 27/07 ở lượt 1-2 của phiên 3 lượt).
        "categories": list(product.categories),
        "description": product.description,
    }


_MAX_PRICE_RE = re.compile(
    r"(?:under|below|less than|dưới|<)\s*\$?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)


def _search_constraints(query: str, category: str | None):
    primary_category = (category or "").lower().rstrip("s")
    match = _MAX_PRICE_RE.search(query or "")
    max_price = float(match.group(1).replace(",", ".")) if match else None
    return primary_category, max_price


def search_products(query: str, category: str | None = None) -> str:
    """Intent 1 — natural-language product search via ProductCatalogService."""
    try:
        # Model hay gọi tool với query rỗng và chỉ đặt category. Catalog cần chữ để
        # embed (Titan từ chối chuỗi rỗng: "expected minLength: 1"), nên lấy category
        # làm câu truy vấn — nếu không, semantic search âm thầm rơi về keyword.
        effective_query = (query or "").strip() or (category or "").strip()
        primary_category, max_price = _search_constraints(query, category)
        with grpc.insecure_channel(PRODUCT_CATALOG_ADDR) as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)

            def fetch(search_query: str) -> list[dict]:
                response = stub.SearchProducts(
                    demo_pb2.SearchProductsRequest(query=search_query), timeout=_RPC_TIMEOUT
                )
                found = [_product_to_dict(p) for p in response.results]
                if primary_category:
                    # Catalog stores the product's primary type first. Secondary tags
                    # (e.g. accessories,telescopes) describe compatibility, not type.
                    found = [p for p in found
                             if p.get("category", "").lower().rstrip("s") == primary_category]
                if max_price is not None:
                    found = [p for p in found if p.get("price", float("inf")) <= max_price]
                return found

            products = fetch(effective_query)
            # Semantic queries such as "beginner stargazing" can be too narrow for
            # the tiny demo catalog. Retry once with the explicit category instead of
            # reporting no products while valid category items exist.
            if not products and category and effective_query.casefold() != category.casefold():
                products = fetch(category)
            if not products:
                fallback_text = " ".join(filter(None, (effective_query, category or "")))
                normalized_query = effective_query.casefold()
                if "kính viễn vọng" in normalized_query or "telescope" in normalized_query:
                    fallback_text += " telescopes"
                tokens = {token for token in re.findall(r"[\w-]+", fallback_text.lower()) if len(token) >= 4}
                listed = stub.ListProducts(demo_pb2.Empty(), timeout=_RPC_TIMEOUT)
                ranked = []
                for product in listed.products:
                    item = _product_to_dict(product)
                    haystack = " ".join([
                        item.get("name", ""), item.get("description", ""),
                        " ".join(item.get("categories", [])),
                    ]).lower()
                    score = sum(token in haystack for token in tokens)
                    if score:
                        ranked.append((score, item))
                products = [item for _, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:5]]
                if primary_category:
                    products = [p for p in products
                                if p.get("category", "").lower().rstrip("s") == primary_category]
                if max_price is not None:
                    products = [p for p in products if p.get("price", float("inf")) <= max_price]
        if not products:
            # message = câu khách được đọc; chỉ dẫn điều khiển agent để riêng ở
            # next_action, vì model từng chép nguyên chuỗi chỉ dẫn ra làm câu trả lời.
            return json.dumps({
                "status": "not_found",
                "message": "Không tìm thấy sản phẩm phù hợp trong danh mục.",
                "next_action": "stop_searching_and_answer",
                "products": []
            })
        for p in products:
            p["price"] = f"${p['price']:.2f}"
        return json.dumps({"status": "ok", "count": len(products), "products": products})
    except grpc.RpcError as e:
        logger.error("SearchProducts RPC failed: %s", e)
        return json.dumps({
            "error": f"SearchProducts failed: {e.code().name} – {e.details()}",
            "message": "Hệ thống tra cứu sản phẩm đang bận.",
            "next_action": "stop_searching_and_answer"
        })
    except Exception as e:
        logger.error("search_products error: %s", e)
        return json.dumps({
            "error": str(e),
            "message": "Hệ thống tra cứu sản phẩm đang gặp sự cố.",
            "next_action": "stop_searching_and_answer"
        })


def get_product_reviews(product_id: str) -> str:
    """Intent 2 — grounded review Q&A via ProductReviewService.

    Returns the joined review text and average score so the LLM answers *from
    context*. When the product has no reviews, ``review_count`` is 0 and the
    agent must say it has no information (no fabrication).
    """
    # Model hay truyền TÊN sản phẩm vào product_id ("Roof Binoculars"); service trả
    # 0 review và model nói với khách là "chưa có đánh giá nào" trong khi sản phẩm
    # có 5 review (đo 28/07). Bắt sớm và bảo model đi tra id trước.
    if not re.fullmatch(r"[A-Z0-9]{10}", (product_id or "").strip()):
        return json.dumps({
            "status": "invalid_product_id",
            "message": f"'{product_id}' không phải mã sản phẩm.",
            "next_action": "search_products_first",
        })
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
        recommended_ids = list(response.product_ids)
        recommended_products = []
        if recommended_ids:
            with grpc.insecure_channel(PRODUCT_CATALOG_ADDR) as channel:
                catalog = demo_pb2_grpc.ProductCatalogServiceStub(channel).ListProducts(
                    demo_pb2.Empty(), timeout=_RPC_TIMEOUT,
                )
            by_id = {product.id: _product_to_dict(product) for product in catalog.products}
            recommended_products = [by_id[product_id] for product_id in recommended_ids if product_id in by_id]
            for product in recommended_products:
                product["price"] = f"${product['price']:.2f}"
        return json.dumps({
            "status": "ok",
            "recommended_product_ids": recommended_ids,
            "recommended_products": recommended_products,
        })
    except grpc.RpcError as e:
        logger.error("ListRecommendations RPC failed: %s", e)
        return _error_json(f"ListRecommendations failed: {e.code().name} – {e.details()}")
    except Exception as e:
        logger.error("list_recommendations error: %s", e)
        return _error_json(str(e))


def convert_currency(amount, from_code, to_code):
    try:
        CURRENCY_ADDR = os.environ.get("CURRENCY_ADDR", "currency:7001")
        with grpc.insecure_channel(CURRENCY_ADDR) as channel:
            stub = demo_pb2_grpc.CurrencyServiceStub(channel)
            request = demo_pb2.CurrencyConversionRequest(
                to_code=to_code,
                **{"from": demo_pb2.Money(
                    currency_code=from_code, 
                    units=int(amount), 
                    nanos=int((amount % 1) * 1e9)
                )}
            )
            response = stub.Convert(request, timeout=_RPC_TIMEOUT)
        converted = _money_to_float(response)
        if float(amount) != 0 and converted == 0:
            return _error_json(
                f"Currency conversion from {from_code} to {to_code} is unavailable."
            )
        return json.dumps({
            "status": "ok",
            "amount": converted,
            "currency": to_code
        })
    except grpc.RpcError as e:
        logger.error("Convert RPC failed: %s", e)
        return _error_json(f"Convert failed: {e.code().name} – {e.details()}")
    except Exception as e:
        logger.error("convert_currency error: %s", e)
        return _error_json(str(e))


def get_shipping_quote(items=None, address=None):
    """Return a read-only quote from the deployed Shipping HTTP endpoint."""
    try:
        shipping_addr = os.environ.get("SHIPPING_ADDR", "http://shipping:50050").rstrip("/")
        defaults = {"street_address": "1600 Amphitheatre Parkway", "city": "Mountain View", "state": "CA", "country": "US", "zip_code": "94043"}
        normalized_address = {key: (address or {}).get(key) or value for key, value in defaults.items()}
        is_estimate = not items
        normalized_items = items or [{"product_id": "OLJCESPC7Z", "quantity": 1}]
        payload = json.dumps({"items": normalized_items, "address": normalized_address}).encode("utf-8")
        request = urllib.request.Request(f"{shipping_addr}/get-quote", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=_RPC_TIMEOUT) as response:
            quote = json.loads(response.read().decode("utf-8"))
        cost = quote.get("cost_usd") or {}
        amount = float(cost.get("units", 0)) + float(cost.get("nanos", 0)) / 1_000_000_000
        result = {"status": "ok", "quote": quote, "formatted_cost": f"${amount:.2f} {cost.get('currency_code') or 'USD'}"}
        if is_estimate:
            result.update({"is_estimate": True, "note": "Estimated quote for one sample product because no cart items were provided."})
        return json.dumps(result)
    except Exception as e:
        logger.error("get_shipping_quote error: %s", e)
        return _error_json(str(e))
