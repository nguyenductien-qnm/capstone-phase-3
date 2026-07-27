# 06 — Contracts (pointer)

Hợp đồng tích hợp ký chéo với CDO đã chuyển về vị trí dùng chung:
**`docs/shared/integration-contracts/`** (`product-reviews-integration.md` — có phụ lục 12/07 chờ re-sign; `shopping-copilot-integration.md`; `recommendation-integration.md`; `README.md`).

Lý do vị trí: contracts là tài sản 2 nhóm — đặt trong `docs/shared/` để CDO cùng own; evidence pack tham chiếu qua file này.

## Contract nội bộ AI-team — gRPC protobuf (source of truth)

Các `.proto` là hợp đồng máy-đọc-được, sinh stub cho mọi service tiêu thụ (`techx-corp-platform/pb/`):

| Proto | Service | RPC | Người gọi |
|---|---|---|---|
| `pb/shopping_copilot.proto` | `ShoppingCopilotService` (pkg `oteldemo`) | `ChatWithCopilot` | frontend/storefront qua Envoy gRPC-Web |
| `pb/ml_guard.proto` | `MLGuardService` (pkg `techx.mlguard.v1`) | `CheckInput`, `CheckOutput`, `SanitizeReviews` | `product-reviews` + `shopping-copilot` qua `pb/ml_guard_client.py` (ADR-015) |

`ml-guard` là policy engine tập trung (ADR-011/014/015): async `grpc.aio`, port `8090`, cascade regex → Presidio PII → NLI grounding (mDeBERTa-XNLI) → Nova judge. Client là shim mỏng `guardrails.py` re-export `ml_guard_client` — import path của service không đổi.
