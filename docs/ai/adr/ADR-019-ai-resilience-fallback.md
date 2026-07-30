# ADR-019: AI Resilience — Controlled Degradation with Output Validation

**Status:** Accepted
**Date:** 2026-07-28
**Mandate:** AI MANDATE #25
**Author:** AIO Team — Task Force 1

## Context

MANDATE-25 yêu cầu tầng AI degrade có kiểm soát khi model provider lỗi hoặc trả rác:
fallback model, capped retries, circuit-breaker tự hồi, output validation (chặn tool
args rác), honest degradation (không bịa nội dung).

Hiện trạng: hầu hết infrastructure đã có từ MANDATE-23:
- Circuit breaker `_cb_state` pattern trong cả `agent.py` và `product_reviews_server.py`
- `invoke_bedrock_converse_with_fallback` với retry+jitter+fallback ladder
- `bedrock_bulkhead` Semaphore(6) ngăn resource exhaustion
- Dynamic deadline check từ gRPC context
- Cache fallback L1 exact + L2 semantic cho phép serve cached khi model lỗi

Thiếu: output validation chặn tool args rác, fault injection endpoint để test.

## Decision

**Reuse toàn bộ CB/retry/fallback đã có. Thêm 2 component mới tối thiểu:**
1. `pb/output_validator.py` — validate toolUse blocks ở biên (sau converse, trước khi xử lý tool)
2. Fault injection qua feature flag `llmFaultGarbageOutput` — bơm output rác để test validator

**Architecture:**
```
Bedrock converse → response blocks
  → [llmFaultGarbageOutput?] → inject malformed toolUse
  → output_validator.validate_tool_calls()
    → FAIL: return degraded fallback (không crash, không exec args rác)
    → PASS: process normally
```

**Degradation ladder (existing, verified):**
1. Primary model (Nova Pro/Lite) — CB check trước mỗi call
2. Fallback model (Nova Lite/Micro) — retry với jitter
3. Cache hit (L1 exact hoặc L2 semantic)
4. Abstain — `_fallback_text()` + `degraded=True`

**Output validation rules:**
- toolUse block phải có đủ `name`, `toolUseId`, `input`
- `input` phải là dict (không phải string/list/null)
- `name` không được rỗng
- Fail → degraded fallback, không crash, không gọi tool

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **JSON Schema validation** | Chính xác từng field | Cần maintain schema cho mỗi tool, heavy |
| **Retry on bad output** | Có thể tự sửa | Tốn token, không guarantee |
| **Pydantic model** | Type-safe | Dependency thừa, chỉ cần check 3 field |
| **Minimal dict check** (chosen) | Nhẹ, không dependency, đủ chặn garbage | Không check semantic correctness |

## Consequences

- **Positive:** Chặn được tool execution với args rác. Fault injection testable qua flag.
  Reuse toàn bộ CB/retry/fallback đã proven. Honest degradation — không bịa.
- **Negative:** Output validator chỉ check structural (có field, đúng type), không check
  semantic (tool name có tồn tại không, args có hợp lệ không).
- **Rủi ro:** False positive — validator chặn output hợp lệ nếu format thay đổi.

## Compliance

- MANDATE-25 §1: ✅ Fallback path (fallback model → cache → abstain)
- MANDATE-25 §2: ✅ Bounded retries (capped, jitter)
- MANDATE-25 §3: ✅ Circuit-breaker (observation-based, tự hồi)
- MANDATE-25 §4: ✅ Honest degradation (không bịa)
- MANDATE-25 §5: ✅ Output validation (chặn garbage args)
