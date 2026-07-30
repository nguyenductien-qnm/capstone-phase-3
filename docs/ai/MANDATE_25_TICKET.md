# AI MANDATE #25

## 1. Link PR/commit
Branch: `feat/mandates-23-to-25-and-ui-refactoring`

| Commit | Nội dung |
|---|---|
| `5baa0d0a` | feat(ai): MANDATE-24 LLM observability + MANDATE-25 AI resilience |

**PR chính:** [#488 — feat(ai+ui): MANDATE 23 to 25 and UI styled-components refactoring](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/488) *(OPEN, nhánh `feat/mandates-23-to-25-and-ui-refactoring`)*

---

## 2. Cách chạy lại (repro)
Script tự backup/restore flag, build đúng image hiện tại, bật fault injection, gửi gRPC thật, assert `degraded=true` + không có tool action và chỉ lưu log evidence đã lọc:
```bash
./repro_m25.sh
```

---

## 3. Bằng chứng chạy thật
Sau khi kích hoạt flag `llmFaultGarbageOutput` và gửi request, hệ thống phát hiện đầu ra rác (Garbage output), chặn quá trình gọi công cụ và tự động chuyển về phản hồi dự phòng (degraded fallback), không gây lỗi toàn hệ thống và không lưu cache nội dung rỗng:

```text
shopping-copilot  | 2026-07-29 03:45:55,404 WARNING agent M25 fault injection: garbage output → testing output validator
shopping-copilot  | 2026-07-29 03:45:55,405 ERROR agent Garbage output blocked: toolUse missing required field: toolUseId — degraded fallback
shopping-copilot  | 2026-07-29 03:45:55,405 INFO shopping-copilot Không cache câu trả lời degraded/fallback/rỗng
```

---

## 4. ADR ký tên
- **[ADR-019](adr/ADR-019-ai-resilience-fallback.md)**: Quy chuẩn AI Resilience & Fallback.

Ký: **AIO Team — dinh144**
