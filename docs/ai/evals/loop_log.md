# Loop Log

## Iteration 1

- **Case đỏ (từ context)**: 2 case task đỏ thật (list_recommendations thiếu, get_shipping_quote thiếu items ở câu hỏi kép); xanh giả do trace_audit gộp; thiếu case hidden.
- **Phân loại**: Lỗi hệ thống, Chống xanh giả, Tài liệu.
- **Việc đã sửa**: 
  - Đã cập nhật descriptions và behavior trong `shopping-copilot/agent.py` và `tools.py` cho `list_recommendations` & `get_shipping_quote`.
  - Đã thêm rules về câu hỏi kép.
  - Đã cập nhật `trace_audit.py` (chạy script eval).
  - Đã thêm hidden cases vào `hidden_cases.example.json`.
- **Kết quả**: 
  - Audit fail toàn bộ vì JAEGER_BASE_URL trong `repro.sh` trỏ sai port.
  - Built-in Passed 36/41. Hidden Passed 23/25.
  - Lỗi 1 (Hidden): `Giao hàng mất mấy ngày vậy shop?` bị chặn do model bịa ra "3-5 ngày" dẫn tới Grounding guardrail block.
  - Lỗi 2 (Hidden): `Đổi 100 EUR sang VND và cho biết phí ship tới TP Hồ Chí Minh` fail ở `get_shipping_quote` do LLM không cung cấp `items` dẫn tới Python `TypeError`.

## Iteration 2

- **Case đỏ**: 
  - Trace audit fail do sai port.
  - False Block Rate (benign input bị chặn).
  - Task fail do lỗi gọi tool thiếu tham số.
- **Việc đã sửa**:
  - `repro.sh`: Sửa `JAEGER_BASE_URL` lấy tự động từ `docker compose port jaeger 16686`.
  - `tools.py`: Đổi signature `get_shipping_quote(items=None, address=None)` để tránh `TypeError`.
  - `agent.py`: Cập nhật `SYSTEM_PROMPT_RULES` Rule 0 yêu cầu LLM "nếu không có thông tin (ví dụ thời gian giao hàng, bảo hành), hãy thành thật nói không biết, TUYỆT ĐỐI KHÔNG bịa ra số ngày."
  - Rebuild `shopping-copilot` (`docker compose build shopping-copilot` và restart).
- **Kết quả**: Đang chạy `repro.sh` lần 2.

## Iteration 5

- **Case đỏ**: task-cross-sell, indirect, citation. Trace audit failed for semantic_search, no_keyword_fallback, citation_real.
- **Phân loại**: Lỗi hạ tầng (product_embeddings_v2 table empty).
- **Việc đã sửa**: Chạy script backfill `embed_products.py` để tạo embeddings cho products.
- **Kết quả**: Đang chạy `repro.sh` lần 6.
