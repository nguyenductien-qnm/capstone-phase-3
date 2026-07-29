# AI MANDATE #25

## 1. Link PR/commit
**Commit chính:** `5baa0d0a feat(ai): MANDATE-24 LLM observability + MANDATE-25 AI resilience`

## 2. Cách chạy lại (repro)
Sử dụng cờ (flag) mô phỏng lỗi dữ liệu rác để kiểm tra cơ chế kiểm tra đầu ra và dự phòng (degraded fallback):
1. Bật flag `llmFaultGarbageOutput` thành `true` trong file `src/flagd/demo.flagd.json`
2. Chạy script để xem hướng dẫn và vị trí log:
```bash
./repro_m25.sh
```
3. Khởi động lại service và gọi GRPC để thu thập log Circuit Breaker/Output Validator:
```bash
docker compose logs shopping-copilot | grep -E 'Garbage|degraded|Circuit Breaker'
```

## 3. Bằng chứng chạy thật
Sau khi kích hoạt flag `llmFaultGarbageOutput` và gửi request, hệ thống phát hiện đầu ra rác (Garbage output), chặn quá trình gọi công cụ và tự động chuyển về phản hồi dự phòng (degraded fallback), không gây lỗi toàn hệ thống và không lưu cache nội dung rỗng:

```text
shopping-copilot  | 2026-07-29 03:45:55,404 WARNING agent M25 fault injection: garbage output → testing output validator
shopping-copilot  | 2026-07-29 03:45:55,405 ERROR agent Garbage output blocked: toolUse missing required field: toolUseId — degraded fallback
shopping-copilot  | 2026-07-29 03:45:55,405 INFO shopping-copilot Không cache câu trả lời degraded/fallback/rỗng
```

## 4. ADR ký tên
- **[ADR-019](adr/ADR-019-ai-resilience-fallback.md)**: Quy chuẩn AI Resilience & Fallback.
Ký: **AIO Team**
