*-# Tầng AI - bạn đang vận hành & xây gì

Tài liệu onboarding cho nhóm AIO (hướng AIE). Đọc để hiểu bề mặt AI của sản phẩm và cái bạn phải dựng.

## 1. Bề mặt AI hiện có/

| Thành phần | Vai trò | Ngôn ngữ | Phụ thuộc |
|---|---|---|---|
| `product-reviews` | Review sản phẩm + **tóm tắt AI** + hỏi-đáp AI | Python | postgresql, `llm` |
| `llm` | Backend model (sinh tóm tắt / trả lời) | Python | mock mặc định; LLM thật khi bạn cắm |

- Tính năng AI đang chạy: khi khách mở trang sản phẩm, `product-reviews` gọi `llm` để **sinh tóm tắt review**.
- `llm` mặc định là **mock**. Cắm model thật (gpt-4o-mini / Bedrock…) qua `deploy/values-aio-llm.yaml` + secret `llm-api-key` (xem GETTING_STARTED).
- Telemetry GenAI đã đi qua OpenTelemetry → collector → Prometheus / Jaeger / OpenSearch: bạn **quan sát được** latency, lỗi, nội dung (trace) của lời gọi AI.

## 2. Việc AIE - hai phần

### Phần A - Vận hành & nâng chất tính năng có sẵn (tóm tắt review)
- **Đúng đắn:** eval độ trung thực (tóm tắt phải khớp review gốc), **fallback** khi `llm` lỗi/chậm → **không bao giờ show tóm tắt sai** cho khách.
- **An toàn:** guardrail chặn prompt-injection nhét trong nội dung review, lọc PII, chặn lộ system prompt.
- **Chi phí/độ trễ:** cache tóm tắt theo sản phẩm, route model rẻ, giảm token, timeout/retry.

### Phần B - Tự dựng "Shopping Copilot" agentic (BTC KHÔNG phát sẵn code agent)
Dựng một trợ lý biết **gọi công cụ** trên các service đang chạy để giúp khách. Bạn tự xây (framework tool-calling tuỳ chọn), wire vào các rpc có sẵn.

**Công cụ (tool) agent gọi được:** `product-catalog` (list/get/**search**) · `product-reviews` (review + tóm tắt) · `cart` (xem/thêm/sửa) · `recommendation` · `currency` · `quote`/`shipping`.

**Cốt lõi - phải làm được cả 3 intent:**

| # | Intent | Làm gì | Tool | "Done" |
|---|---|---|---|---|
| 1 | **Tìm sản phẩm NL** | *"tai nghe chống ồn dưới $50"* → tìm + lọc | product-catalog search | query tự nhiên ra đúng sản phẩm, không phải keyword cứng |
| 2 | **Hỏi-đáp grounded (RAG)** | *"pin dùng bao lâu?"* → trả lời từ review thật, dẫn nguồn | product-reviews (+catalog) | 0 hallucinate; **nói "không có thông tin"** khi review không đề cập |
| 3 | **Giỏ hàng có kiểm soát** | *"thêm 2 cái vào giỏ"* → thao tác giỏ | cart | thực thi đúng lệnh; **xác nhận trước khi ghi**; **không tự checkout/xoá giỏ** |

**Mở rộng (đua top):**
| # | Intent | Tool |
|---|---|---|
| 4 | **So sánh sản phẩm** (giá + sentiment review 2-3 SP) | catalog + reviews |
| 5 | **Gợi ý kèm / cross-sell** | recommendation + catalog |
| 6 | **Giá/ship/quy đổi tiền** | currency + quote/shipping |

**Yêu cầu xuyên suốt mọi intent (được chấm):**
- **Multi-turn:** nhớ ngữ cảnh ("nó", "cái đầu tiên").
- **Tool allow-list + confirmation gate** cho mọi hành động ghi; **không** hành động ngoài phạm vi (guardrail **excessive-agency**).
- **Grounded, không hallucinate**; không lộ PII / system prompt.
- **Fallback** khi LLM lỗi/chậm (không treo trang) + **giới hạn vòng lặp** + **audit log** mọi lời gọi tool.

## 3. Cách chấm - tầng AI

Chấm theo **judgment + vận hành thật**, không phải "viết được bao nhiêu code". Năm chiều:

1. **Ưu tiên & judgment** - chọn đúng việc đáng làm trên tầng AI, dám bỏ việc tác động thấp và giải thích được.
2. **Engineering & Ops** - xử lý đúng gốc, không tạo lỗi mới; có đo trước-sau.
3. **Business trade-off** - quy quyết định về chi phí / khách hàng / SLO.
4. **Năng lực AI** - AIOps (phát hiện-chẩn đoán-xử lý sự cố) và AIE (chất lượng, an toàn, chi phí của tính năng AI + trợ lý agentic).
5. **Communication** - ADR / postmortem rõ ràng, quản lý được stakeholder khi bị phản biện.

**Được nhìn cụ thể ở tầng AI:**
- **Chạy thật, không mockup** - deploy và chạy trong hệ thống của TF (build → ECR → deploy).
- **Có eval, tái tạo được** - chứng minh bằng số đo (độ trung thực tóm tắt, tỉ lệ chặn tấn công, task-success của trợ lý…), tái tạo được từ dữ liệu + script bạn commit. Số không tái tạo được coi như chưa chứng minh.
- **Đo được** - before/after cho mỗi cải tiến (latency, cost, tỉ lệ lỗi, MTTD/MTTR…).
- **An toàn** - guardrail, xác nhận trước hành động ghi, fallback, rollback.
- **Grounded** - trợ lý AI không bịa, không lộ PII / system prompt.
- Quyết định lớn có **ADR** (truy được thay đổi), không phá SLO / ngân sách.

**Cần chuẩn bị để chấm:**
- Hệ thống của TF **đang chạy** trong lúc đánh giá (có thể được tương tác/kiểm tra trực tiếp).
- **Khai rõ endpoint** trong bản nộp: tính năng AI (trợ lý/tóm tắt) và kênh cảnh báo/nhật ký của hệ AIOps.
- Bộ **eval + script tái tạo** (`repro`) đi kèm.

**Bar để được đánh giá cao:**
- Hệ AIOps **chạy liên tục** trong lúc vận hành và **xử lý được sự cố thật** (không phải demo một lần).
- Trợ lý AI hoạt động **trong phạm vi cho phép**, có **eval task-success** - không tính "trả lời trôi chảy".

**Vi phạm = loại (disqualify):** tắt/đổi hướng cơ chế sự cố (flagd); mượn kết quả TF khác; vượt ngân sách hoặc phá SLO của nhau.

## 4. Bắt đầu từ đâu
1. Cắm `llm` sang model thật (`values-aio-llm.yaml`) → xem tính năng tóm tắt chạy thật.
2. Dựng eval + guardrail cho tóm tắt (Phần A) trước - đây là nền.
3. Xây trợ lý agentic (Phần B): chọn framework tool-calling của bạn, wire vào các rpc ở trên, thêm guardrail + eval task-success.
4. Đưa eval vào CI để mỗi thay đổi không làm rớt chất lượng.

> Đầu mối kỹ thuật (rpc/proto, cấu hình `llm`) nằm trong `techx-corp-platform/` (xem `src/product-reviews`, `src/llm`, và proto của các service). Khám phá source là một phần của việc tiếp quản.
