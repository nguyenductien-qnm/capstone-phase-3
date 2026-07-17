# shopping-copilot (TF1-59)

Real gRPC servicer for the **Shopping Copilot** agent — replaces the Streamlit
PoC (`copilot-poc/`) with a deployable service that runs the 3 required intents
against the **real** microservices (RULES §4: "phải chạy thật, không mockup").

Implements `ShoppingCopilotService.ChatWithCopilot` on `:50051`
(proto: `techx-corp-platform/pb/shopping_copilot.proto`, spec:
`docs/ai/03_specs/shopping_copilot.md`).

## Files

| File | Role |
|---|---|
| `copilot_server.py` | gRPC server; session history + token-based confirmation store; entrypoint |
| `agent.py` | Bedrock Converse tool-loop; tool defs; safety (allow-list, max-loop, audit) |
| `tools.py` | gRPC calls to product-catalog / product-reviews / cart |
| `test_copilot.py` | self-check (no AWS/gRPC): confirmation gate, routing, max-loop, degraded |

## The 3 intents

| Intent | Tool → downstream | Rule |
|---|---|---|
| NL product search | `search_products` → `ProductCatalogService.SearchProducts` | natural query |
| Grounded review Q&A | `get_product_reviews` → `ProductReviewService.GetProductReviews` | answer from reviews only; say "không có thông tin" when absent |
| Cart (read/write) | `get_cart` / `add_item_to_cart` → `CartService.GetCart` / `AddItem` | **write is gated** |

## Confirmation gate (ADR-006 Tier-2 write)

Two-phase, token-based (proto `PendingConfirmation`):

1. LLM decides `add_item_to_cart` → server **prepares** the action, returns a
   `confirmation_token` + `pending_confirmation`, and executes **nothing**.
2. Client re-sends the same request with `confirmation_token` set → server
   executes the real `CartService.AddItem`, **bypassing the LLM**. Token is
   single-use and expires (`COPILOT_CONFIRM_TTL`, default 300s).

Destructive ops (`empty_cart`, `place_order`, checkout) are block-listed by
omission — the LLM is never given a tool definition for them.

## Env vars

| Var | Default | Notes |
|---|---|---|
| `SHOPPING_COPILOT_PORT` | `50051` | gRPC listen port |
| `AWS_REGION` | `us-east-1` | Bedrock region (needs `bedrock:InvokeModel`) |
| `BEDROCK_AWS_ACCESS_KEY_ID` / `BEDROCK_AWS_SECRET_ACCESS_KEY` | unset | optional dedicated Bedrock Account 2 credentials; fallback to Pod Identity/IAM when unset |
| `BEDROCK_AWS_SESSION_TOKEN` | unset | optional session token for temporary Bedrock credentials |
| `LLM_COPILOT_MODEL` / `LLM_COPILOT_MAIN_MODEL` | `amazon.nova-pro-v1:0` | main agent model |
| `PRODUCT_CATALOG_ADDR` | `product-catalog:8080` | downstream |
| `PRODUCT_REVIEWS_ADDR` | `product-reviews:3551` | downstream |
| `CART_SERVICE_ADDR` / `CART_ADDR` | `cart:8080` | downstream |
| `COPILOT_RPC_TIMEOUT` | `2.0` | per-RPC deadline (spec §6) |
| `COPILOT_CONFIRM_TTL` | `300` | confirmation-token TTL (s) |

## Test

```bash
cd techx-corp-platform/src/shopping-copilot
python test_copilot.py
```

## Known ceilings (ponytail)

- Session + pending-confirmation stores are in-memory → correct for **1 replica**.
  Move to Valkey (key by session_id / token) before scaling out.
- LLM-judge input guardrail + PII redaction (spec §5) live in the parallel
  guardrails work (product-reviews `guardrails.py`, PR #36); not wired here yet.
- Fallback on LLM error is a single degraded reply; retry/backoff + circuit
  breaker (as in product-reviews) can be lifted in if copilot traffic warrants.
