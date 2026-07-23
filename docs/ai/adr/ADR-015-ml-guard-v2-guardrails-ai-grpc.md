# ADR 015: ml-guard v2 — Guardrails AI + Async gRPC

**Status:** Accepted
**Date:** 2026-07-23

## Context
The AI trust-safety guardrails (MANDATE-06) run in a self-hosted `ml-guard` service. The v1 implementation was a synchronous HTTP server (`ThreadingHTTPServer`) exposing `/v1/protect` (Presidio PII + ProtectAI injection) and `/v1/grounding` (mDeBERTa-XNLI). Model inference was serialized under a single lock; the callers (`product-reviews` and `shopping-copilot`) each wrapped the call in a `Semaphore(2)`. Under load, this became a severe bottleneck. 

Additionally, the orchestration logic (regex pre-filters, fallback mechanisms, leakage detection) was duplicated identically in both `product-reviews/guardrails.py` and `shopping-copilot/guardrails.py`.

## Decision
1. **Framework:** Adopt [Guardrails AI](https://github.com/guardrails-ai/guardrails) as the core engine.
2. **Architecture:** Migrate from a synchronous HTTP server to an asynchronous `grpc.aio` service.
3. **Validation logic:** Centralize all policies in `ml-guard/server.py`. Clients become thin gRPC callers.
4. **Custom Validator:** Wrap our `mDeBERTa-XNLI` grounding model as a custom `VietnameseMDeBERTaGrounding` validator rather than swapping to EN-only Hub alternatives.
5. **Concurrency:** Remove the `Semaphore(2)` bottleneck. Run CPU-bound torch/presidio inference in a `ThreadPoolExecutor` to unblock the gRPC async event loop.
6. **Infrastructure:** Update health checks to use `grpc_health_probe` and optimize CPU requests to 400m while keeping limits at 2000m for inference bursts.

## Consequences
- **Positive:**
  - Standardized interface and composability through Guardrails AI.
  - Significant latency reduction under concurrent load due to `grpc.aio` and thread pool delegation.
  - Single source of truth for policy (D.R.Y.), simplifying maintenance.
  - Thin clients are easier to test and scale.
- **Expectation Setting:** 
  - Guardrails AI's out-of-the-box injection/PII validators often wrap the exact same class of underlying models (e.g., ProtectAI / Presidio). The primary win is **the standard interface, composability, and the async server architecture**, *not* necessarily superior ML detection capabilities compared to the custom v1.
- **Negative:**
  - Adds `grpcio` and `grpcio-tools` dependency.
  - Requires maintaining `pb/ml_guard.proto` schemas.
