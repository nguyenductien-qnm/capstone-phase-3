# 02 — Solution Design (Nhóm AI / AIO03)

> ⚠️ Cùng caveat khung evidence-pack như `01_requirements.md`. Chi tiết từng quyết định: 05_adrs.md
> (kèm "Phụ lục kiểm chứng 12/07" + "Sổ đăng ký con số"); spec chi tiết: `03_specs/`.

## 1. Kiến trúc tầng AI

```
storefront ──► frontend-proxy(Envoy) ──► product-reviews ──► Bedrock Nova Lite ──fallback──► Nova Micro ──► mock summary
                     │                        │  ▲cache Valkey (10 key, TTL 7d, versioned)
                     └─► shopping-copilot(:50051, tuần 2) ──► Nova Pro ──► catalog/reviews/cart gRPC (cart: confirmation gate)
observability: OTel → Prometheus/OpenSearch/Jaeger ──► aiops-detector (poll 30s, 13 rule) ──► webhook alert
                                                    └─► Drain3 log clustering (CronJob)
```

## 2. Quyết định chính + phương án đã loại (tóm tắt — chi tiết trong ADR tương ứng)

| Quyết định | Chọn | Loại + lý do |
|---|---|---|
| Model routing | Tích hợp OpenFeature/flagd Model Gateway (A/B testing % traffic). Nova Lite→Micro (reviews), Nova Pro→Lite (copilot) | Claude (chốt bỏ 11/07; đắt ~50×); single-model (không có fallback) |
| Resilience | retry+jitter, bulkhead non-blocking(6), CB 3-fail/30s, deadline fail-fast, mock cuối | SDK adaptive retry (retry kép); bulkhead blocking (no-op — chứng minh bằng thí nghiệm); CB đọc flag (vi phạm §3) |
| Cache | Valkey cache-aside, TTL phẳng 7d, key versioned theo model+prompt hash | Dynamic TTL (data tĩnh — không có gì để phản ứng); CDN (thừa) |
| Tìm sản phẩm NL | Dùng Amazon Titan Embeddings V2 + pgvector | Bác bỏ phương án Catalog-in-prompt vì là anti-pattern. |
| AI Recommendations | Dùng item-to-item cosine similarity qua pgvector, thay cho thuật toán random cũ | LLM Re-ranking (đắt đỏ, tăng latency); Amazon Personalize (cần cold start interaction data lớn) |
| Reviews QA | Fetch trực tiếp 5 review/sản phẩm vào context | Vector RAG (thừa ở quy mô này) |
| Detection | Poll 30s (đo: MTTD max 35.4s, vùng hợp lệ [10,60]s) + hybrid static/EWMA + burn-rate (draft) | Realtime stream (mua ≤30s bằng cả 1 consumer service — sai trade-off) |
| Log backend | Đề xuất CDO cân nhắc Loki/bóp OpenSearch — nhu cầu AI chỉ là phrase-count 5m + batch read | Chi tiết: `ai-data-requirements-for-cdo.md` |

## 3. Rủi ro mở
~~J1 valkey-cart (maxmemory/TTL — chờ CDO), IAM Bedrock chưa có (chặn deploy thật), copilot chưa có code (chart disabled).~~
**[CẬP NHẬT 14/07]** J1 **đóng** — CDO migrate sang **Amazon ElastiCache** (Valkey), **Amazon RDS PostgreSQL 16.14** (native pgvector support), và **Amazon MSK** (Kafka). Copilot **đã có code** — servicer thật trên `:50051`, PR #47 (TF1-59); chart vẫn `enabled: false` chờ CDO build image + flip (J2). Còn mở: **IAM Bedrock (IRSA)** cho `product-reviews` + `shopping-copilot` — blocker deploy thật duy nhất (open-questions B1); MANDATE-06 (hạn 18/07) yêu cầu demo chặn injection/hallucination trước mentor.
