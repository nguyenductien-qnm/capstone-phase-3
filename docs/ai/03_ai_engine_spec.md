# 03 — AI Engine Spec (Nhóm AI / AIO03)

> Doc số 3 của evidence pack (mentor xác nhận 12/07: khung 6 doc ÁP DỤNG Phase 3).
> Spec chi tiết theo chủ đề nằm trong `03_specs/` — file này là bản đồ + các quyết định engine-level.

## Model & routing
| Tác vụ | Primary | Fallback | Timeout/call | Spec |
|---|---|---|---|---|
| Reviews summary | `amazon.nova-lite-v1:0` | `nova-micro` → mock | 4.0s / 2.0s | `03_specs/fallback_retry.md` |
| Shopping Copilot | `amazon.nova-pro-v1:0` | `nova-lite` → thông báo lỗi | 5.7s / 2.5s | `03_specs/shopping_copilot.md` |

Inference params: `INFERENCE_CONFIG` trong `product_reviews_server.py` (maxTokens 1024 = trần chống runaway; temp 0.1 = bám nguồn; topP 0.9 — justification trong code + Sổ đăng ký con số ở `05_adrs.md`).

## Resilience (đã verify runtime 12/07)
Retry (2/1) + full jitter → fallback ladder → mock; bulkhead non-blocking size 6; circuit breaker 3-fail/30s **theo lỗi quan sát được** (mentor xác nhận 12/07: đọc cờ sự cố flagd để bypass là PHẠM LUẬT — bản cũ đã gỡ trước đó); deadline fail-fast; marker `AI_SUMMARY_FALLBACK`.

## Safety
Confirmation gate cho cart-write (bắt buộc theo đề); guardrail prompt-injection/PII: `05_adrs.md` ADR-006, eval probe trong `evals/golden_qa_dataset.json` (4 case injection).

## Data & cache
PostgreSQL read-only (10 sản phẩm / 50 reviews — đo từ DB); Valkey cache 10 key, TTL phẳng 7d, versioned key theo model env + prompt hash (`03_specs/valkey_caching.md`).

## AIOps engine
Detector poll 30s (MTTD max 35.4s đo được), 13 rule (`aiops/detector/rules.yaml`); Drain3 clustering (`aiops/log_clustering/`, sim_th chờ chốt sau masking — grid 12/07: 0.3); remediation W1 detect-only (`03_specs/anomaly_remediation.md`).

## Hạng mục Đua Top (Đã triển khai - W2)
- **Model Gateway & A/B Testing**: Sử dụng `flagd` để chia traffic động giữa `amazon.nova-lite-v1:0` và `nova-pro-v1:0` (`03_specs/model_gateway_ab_testing.md`).
- **AI Recommendations (pgvector)**: Sử dụng khoảng cách Cosine Similarity trực tiếp trên PostgreSQL thay cho giải pháp Random mặc định (`03_specs/ai_recommendations.md`).
- **Semantic Search (pgvector)**: Giải pháp ban đầu nhét text vào prompt đã bị bác bỏ, chính thức nâng cấp sử dụng HNSW/pgvector chuẩn Enterprise (`03_specs/semantic_search.md`).
