# AI MANDATE #24

## 1. Link PR/commit
Branch: `feat/mandates-23-to-25-and-ui-refactoring`

| Commit | Nội dung |
|---|---|
| `5baa0d0a` | feat(ai): MANDATE-24 LLM observability + MANDATE-25 AI resilience |

**PR chính:** [#488 — feat(ai+ui): MANDATE 23 to 25 and UI styled-components refactoring](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/488) *(OPEN, nhánh `feat/mandates-23-to-25-and-ui-refactoring`)*

---

## 2. Cách chạy lại (repro)
Chạy script tự động nghiệm thu (khởi động lại container và gọi service sinh trace ID):
```bash
./repro_m24.sh
```

---

## 3. Bằng chứng chạy thật
Lần chạy lúc nghiệm thu sinh trace ID lưu trữ trên Valkey và ghi nhận log session thành công:

```text
=== MANDATE-24 Repro ===
>>> Sending request...
Trace ID: e441a800b590d730630f3e3674012b15
>>> Trace content:
{
    "trace_id": "e441a800b590d730630f3e3674012b15",
    "session_id": "repro-m24",
    "model_id": "amazon.nova-pro-v1:0",
    "tokens_in": 5731,
    "tokens_out": 132,
    "latency_ms": 2350,
    "cost_usd": 5.01e-06,
    "outcome": "ok",
    "tool_calls": [],
    "surface": "copilot",
    "prompt_hash": "07fd6c5349c3daef",
    "timestamp_utc": "2026-07-29T03:44:39.559274+00:00"
}

>>> Session chain:
e441a800b590d730630f3e3674012b15

=== Done ===
```

---

## 4. ADR ký tên
- **[ADR-018](adr/ADR-018-llm-observability.md)**: Quy chuẩn Observability cho LLM. 

Ký: **AIO Team — dinh144**
