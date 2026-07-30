# ADR-018: LLM Observability — Valkey-backed trace store

**Status:** Accepted
**Date:** 2026-07-28
**Mandate:** AI MANDATE #24
**Author:** AIO Team — Task Force 1

## Context

MANDATE-24 yêu cầu mỗi lời gọi AI phải để lại dấu vết đủ 11 trường lõi (model, tokens,
cost, latency, outcome, trace_id, session_id, tool_calls, surface, prompt_hash, timestamp),
tái dựng được chuỗi lời gọi từ trace_id, và có aggregate view. Cần một tầng trace nhẹ,
không thêm dependency mới, không kéo latency đường chính.

Hiện trạng: OTEL + Jaeger đã trace ở mức span (latency, model name, tokens), nhưng:
- Không lưu cost
- Không có session index để dựng chain
- PII trong prompt chưa được mask trước khi export
- Jaeger không phải persistence store (TTL ngắn, không aggregate được)

## Decision

Dùng **Valkey** (Redis OSS compatible) làm trace store — cùng cluster đang dùng cho L1/L2
cache của MANDATE-23. Ghi fire-and-forget từ thread pool, không block đường chính.

**Architecture:**
```
Bedrock call → agent.py → build_trace_record() → executor.submit(record_trace) → Valkey
                                                                   SETEX trace:{id} 7d
                                                                   SADD trace:session:{sid}
```

**Data model (JSON, 11 fields):**
- `trace_id` — OTEL hex trace ID (nối được với Jaeger span)
- `session_id` — session người dùng
- `model_id` — model identifier (e.g. amazon.nova-pro-v1:0)
- `tokens_in`, `tokens_out` — token count
- `latency_ms` — round-trip latency
- `cost_usd` — estimated cost (pricing table từ docs/ai/03_specs)
- `outcome` — ok | error | fallback
- `tool_calls` — list of tool names called
- `surface` — copilot | reviews
- `prompt_hash` — SHA256 of PII-masked prompt
- `timestamp_utc` — ISO 8601

**PII masking:** Regex-based email/SSN/card detection → SHA256 hash trước khi lưu.
Nâng cấp sau: gọi ml-guard Presidio qua gRPC.

**Aggregate view:** `tools/trace_aggregate.py` quét `SCAN trace:*` → group by model+surface
→ output cost/latency table. Upgrade path: Postgres materialized view cho large-scale.

**Retrieval:** `GET trace:{trace_id}` trả JSON trực tiếp. Session chain: `SMEMBERS trace:session:{id}`.

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Postgres** | Persistent, SQL aggregate | Cần migration mới, thêm connection pool, latency cao hơn Valkey |
| **Langfuse** | Purpose-built, dashboard sẵn | Dependency mới, self-host hoặc paid cloud, 2 containers mới |
| **Jaeger only** | Đã có sẵn | Không persistence, không cost, không aggregate, span context ngắn |
| **Valkey** (chosen) | Zero new infra, async writes, đã có connection pool | TTL 7d (không permanent), scan-based aggregate không scale trên >100K traces |

## Consequences

- **Positive:** Không thêm dependency mới. Trace ghi không block đường chính. Session index
  cho phép dựng chain. PII được mask. Aggregate view có sẵn.
- **Negative:** Valkey TTL 7d — trace cũ hơn 7 ngày tự xóa. Scan-based aggregate không
  hiệu quả cho production >100K traces/ngày. Cần migrate sang Postgres khi traffic tăng.
- **Rủi ro:** Valkey memory pressure nếu trace volume cao. Giảm thiểu: TTL 7d, giới hạn
  trace size (prompt_hash thay vì full prompt).

## Compliance

- MANDATE-24 §1: ✅ 11 trường lõi
- MANDATE-24 §2: ✅ Session index → dựng chain
- MANDATE-24 §3: ✅ Aggregate view qua trace_aggregate.py
- MANDATE-24 §4: ✅ PII masked (prompt_hash)
- Nhẹ: ✅ Fire-and-forget từ thread pool
- Thật: ✅ Trace từ lời gọi thật qua gRPC
