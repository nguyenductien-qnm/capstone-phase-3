# ADR 015: ml-guard v2 — Async gRPC central policy service

**Status:** Accepted (amended 2026-07-24 — dropped Guardrails AI framework)
**Date:** 2026-07-23

## Context
The AI trust-safety guardrails (MANDATE-06) run in a self-hosted `ml-guard` service. The v1 implementation was a synchronous HTTP server (`ThreadingHTTPServer`) exposing `/v1/protect` (Presidio PII + ProtectAI injection) and `/v1/grounding` (mDeBERTa-XNLI). Model inference was serialized under a single lock; the callers (`product-reviews` and `shopping-copilot`) each wrapped the call in a `Semaphore(2)`. Under load, this became a severe bottleneck.

Additionally, the orchestration logic (regex pre-filters, fallback mechanisms, leakage detection) was duplicated identically in both `product-reviews/guardrails.py` and `shopping-copilot/guardrails.py`.

## Decision
1. **Architecture:** Migrate from a synchronous HTTP server to an asynchronous `grpc.aio` service (`pb/ml_guard.proto`: `CheckInput`, `CheckOutput`, `SanitizeReviews`).
2. **Validation logic:** Centralize all policies in `ml-guard/server.py`. Clients become thin sync gRPC callers in a single shared module `pb/ml_guard_client.py` (re-exported qua shim `guardrails.py` của từng service — import path không đổi).
3. **Engine:** Keep the custom cascade — regex pre-filter → Presidio PII → NLI grounding (mDeBERTa-XNLI) → Nova judge — chạy 1 lần trong `ThreadPoolExecutor`, không block event loop.
4. **Guardrails AI framework: evaluated and REJECTED** (amendment 2026-07-24). Bản tích hợp ban đầu wrap NLI trong custom `Validator`; kết quả đo:
   - Wrapper nuốt `action` metadata → phải gọi NLI lần 2 để lấy action ⇒ **double inference** trên service từng CPU-thrash, lần 2 chạy sync trên event loop.
   - Hub validators (DetectJailbreak, GuardrailsPII…) chỉ wrap đúng class model đang dùng (ProtectAI deberta, Presidio) và **không có model tiếng Việt** — không thêm năng lực phát hiện.
   - Thêm dependency nặng vào image + 2 bước `guardrails hub install` lúc build.
   - MANDATE-06 chấm **kết quả eval tái tạo được**, không chấm framework.
5. **Concurrency:** Remove the `Semaphore(2)` bottleneck. Run CPU-bound torch/presidio inference in a `ThreadPoolExecutor` to unblock the gRPC async event loop.
6. **Infrastructure:** Health check dùng `grpc_health_probe`; health servicer có thread-pool riêng (không tranh thread torch) và chỉ báo `SERVING` **sau khi model load xong** (`NOT_SERVING` lúc boot). CPU requests 400m, limits 2000m cho inference bursts.
7. **Bedrock Guardrail:** layer 3 feature-gated (`LLM_BEDROCK_GUARDRAIL`) **bật ON** (2026-07-24, theo xác nhận vận hành) — `crbxw41dbmxp` áp ở us-east-1 cho `product-reviews` + `shopping-copilot`. Đánh đổi đã cân: Bedrock grounding **không hỗ trợ tiếng Việt** (ADR-014) nên có thể false-block các câu abstention/apology không có context — theo dõi false-block-rate ở eval; tắt lại chỉ cần đổi 1 dòng values về `"false"`.

## Consequences
- **Positive:**
  - Significant latency reduction under concurrent load due to `grpc.aio` and thread pool delegation; NLI chạy đúng 1 lần mỗi request.
  - Single source of truth for policy (server) **và** cho client helpers (`pb/ml_guard_client.py`) — hết drift giữa 2 bản copy.
  - Health check phản ánh model-ready thật → `depends_on: service_healthy` hoạt động đúng.
  - Image ml-guard nhẹ hơn (bỏ guardrails-ai + hub install).
- **Negative:**
  - Adds `grpcio` and `grpcio-tools` dependency.
  - Requires maintaining `pb/ml_guard.proto` schemas.
  - Không có "standard interface" của framework — đổi lại là cascade tự đo, tự kiểm soát; đánh giá lại nếu hub có validator tiếng Việt đáng dùng.
