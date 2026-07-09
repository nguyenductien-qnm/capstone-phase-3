"""
gRPC Client Layer for Shopping Copilot
=======================================
Connects the Streamlit-based Shopping Copilot to real microservices
running on EKS via gRPC.  Falls back gracefully when proto stubs are
not yet generated or service addresses are not configured.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Proto stub imports (graceful fallback)
# ---------------------------------------------------------------------------
try:
    import grpc
    import demo_pb2
    import demo_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as exc:
    logger.warning("gRPC stubs not available (%s). Run generate_proto_stubs.sh first.", exc)
    GRPC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Service addresses from environment variables
# ---------------------------------------------------------------------------
PRODUCT_CATALOG_ADDR = os.environ.get("PRODUCT_CATALOG_ADDR", "")
PRODUCT_REVIEWS_ADDR = os.environ.get("PRODUCT_REVIEWS_ADDR", "")
CART_SERVICE_ADDR = os.environ.get("CART_SERVICE_ADDR", "")

# Per-RPC deadline (seconds)
_RPC_TIMEOUT = 3


def is_grpc_available() -> bool:
    """Return True only when proto stubs are importable **and** all three
    service addresses are configured via environment variables."""
    return (
        GRPC_AVAILABLE
        and bool(PRODUCT_CATALOG_ADDR)
        and bool(PRODUCT_REVIEWS_ADDR)
        and bool(CART_SERVICE_ADDR)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _money_to_float(money) -> float:
    """Convert a ``Money`` protobuf message to a Python float."""
    return money.units + money.nanos / 1e9


def _product_to_dict(product) -> dict:
    """Transform a ``Product`` protobuf message into the JSON-friendly dict
    used by the mock tool layer."""
    return {
        "product_id": product.id,
        "name": product.name,
        "price": _money_to_float(product.price_usd),
        "category": product.categories[0] if product.categories else "",
        "in_stock": True,  # catalog proto doesn't track stock
        "description": product.description,
    }


def _error_json(message: str) -> str:
    """Return a standardised error payload as a JSON string."""
    return json.dumps({"error": message})


# ---------------------------------------------------------------------------
# gRPC client functions
# ---------------------------------------------------------------------------

def grpc_search_products(query: str, category: str | None = None) -> str:
    """Search the ProductCatalogService and return matching products as JSON.

    Parameters
    ----------
    query : str
        Free-text search term forwarded to ``SearchProducts`` RPC.
    category : str, optional
        If provided, results are filtered client-side to this category.

    Returns
    -------
    str
        JSON array of product dicts, or an error object on failure.
    """
    if not GRPC_AVAILABLE:
        return _error_json("gRPC stubs not available. Run generate_proto_stubs.sh first.")

    if not PRODUCT_CATALOG_ADDR:
        return _error_json("PRODUCT_CATALOG_ADDR environment variable not set.")

    try:
        with grpc.insecure_channel(PRODUCT_CATALOG_ADDR) as channel:
            stub = demo_pb2_grpc.ProductCatalogServiceStub(channel)
            request = demo_pb2.SearchProductsRequest(query=query)
            response = stub.SearchProducts(request, timeout=_RPC_TIMEOUT)

        products = [_product_to_dict(p) for p in response.results]

        # Optional client-side category filter
        if category:
            cat_lower = category.lower()
            products = [
                p for p in products
                if p.get("category", "").lower() == cat_lower
            ]

        return json.dumps(products)

    except grpc.RpcError as rpc_err:
        logger.error("SearchProducts RPC failed: %s", rpc_err)
        return _error_json(f"SearchProducts RPC failed: {rpc_err.code().name} – {rpc_err.details()}")
    except Exception as exc:
        logger.error("Unexpected error in grpc_search_products: %s", exc)
        return _error_json(f"Unexpected error: {exc}")


def grpc_get_product_reviews(product_id: str) -> str:
    """Fetch reviews for a product from the ProductReviewService.

    Returns a JSON object with ``product_id``, ``average_score``, and a
    ``summary`` string that joins all review descriptions.

    Parameters
    ----------
    product_id : str
        Identifier of the product whose reviews to fetch.

    Returns
    -------
    str
        JSON object, or an error object on failure.
    """
    if not GRPC_AVAILABLE:
        return _error_json("gRPC stubs not available. Run generate_proto_stubs.sh first.")

    if not PRODUCT_REVIEWS_ADDR:
        return _error_json("PRODUCT_REVIEWS_ADDR environment variable not set.")

    try:
        with grpc.insecure_channel(PRODUCT_REVIEWS_ADDR) as channel:
            stub = demo_pb2_grpc.ProductReviewServiceStub(channel)
            request = demo_pb2.GetProductReviewsRequest(product_id=product_id)
            response = stub.GetProductReviews(request, timeout=_RPC_TIMEOUT)

        reviews = response.product_reviews

        # Compute average score (scores are strings in the proto)
        scores = []
        for r in reviews:
            try:
                scores.append(float(r.score))
            except (ValueError, TypeError):
                pass
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        # Summarise review descriptions
        summary = " | ".join(r.description for r in reviews if r.description)

        result = {
            "product_id": product_id,
            "average_score": avg_score,
            "review_count": len(reviews),
            "summary": summary or "No reviews available.",
        }
        return json.dumps(result)

    except grpc.RpcError as rpc_err:
        logger.error("GetProductReviews RPC failed: %s", rpc_err)
        return _error_json(f"GetProductReviews RPC failed: {rpc_err.code().name} – {rpc_err.details()}")
    except Exception as exc:
        logger.error("Unexpected error in grpc_get_product_reviews: %s", exc)
        return _error_json(f"Unexpected error: {exc}")


def grpc_add_to_cart(user_id: str, product_id: str, quantity: int) -> str:
    """Add an item to the user's cart via the CartService.

    Parameters
    ----------
    user_id : str
        Identifier for the shopping cart owner.
    product_id : str
        Product to add.
    quantity : int
        Number of units to add.

    Returns
    -------
    str
        JSON success/error object.
    """
    if not GRPC_AVAILABLE:
        return _error_json("gRPC stubs not available. Run generate_proto_stubs.sh first.")

    if not CART_SERVICE_ADDR:
        return _error_json("CART_SERVICE_ADDR environment variable not set.")

    try:
        with grpc.insecure_channel(CART_SERVICE_ADDR) as channel:
            stub = demo_pb2_grpc.CartServiceStub(channel)
            cart_item = demo_pb2.CartItem(
                product_id=product_id,
                quantity=int(quantity),
            )
            request = demo_pb2.AddItemRequest(
                user_id=user_id,
                item=cart_item,
            )
            stub.AddItem(request, timeout=_RPC_TIMEOUT)

        result = {
            "status": "success",
            "message": f"Added {quantity}x {product_id} to cart for user {user_id}.",
        }
        return json.dumps(result)

    except grpc.RpcError as rpc_err:
        logger.error("AddItem RPC failed: %s", rpc_err)
        return _error_json(f"AddItem RPC failed: {rpc_err.code().name} – {rpc_err.details()}")
    except Exception as exc:
        logger.error("Unexpected error in grpc_add_to_cart: %s", exc)
        return _error_json(f"Unexpected error: {exc}")
