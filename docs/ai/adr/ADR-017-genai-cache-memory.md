# ADR-017: GenAI Caching & Memory cho tầng AI (MANDATE-23)

**Status:** Accepted (đã cập nhật 28/07 sau nghiệm thu liên tục 10+ vòng eval)
**Date:** 2026-07-27 (viết), 2026-07-28 (đính chính)
**Author:** Nguyễn Hữu Dinh — AIO03, Task Force 1 (ký tên)
**Liên quan:** ADR-015 (ml-guard v2 gRPC), ADR-016 (eval framework MANDATE-14)

## Context

Directive #23 đòi tầng AI chạy như sản phẩm thật: không đốt token cho yêu cầu lặp,
nhớ ngữ cảnh trong phiên và xuyên phiên, và **không nhớ nhầm sang người khác** —
chứng minh bằng số đo, không bằng lời. Hạ tầng sẵn có: ElastiCache for Valkey **8.2** (`cache.t4g.micro`,
`maxmemory-policy=volatile-lru`, **SnapshotRetentionLimit = 0**) và RDS `db.t4g.micro`
20 GB **không autoscale**.

## Decision

### 1. Ba tầng cache, mỗi tầng một việc
| Tầng | Nơi ở | Vì sao |
|---|---|---|
| **L1 exact** | Valkey, key content-addressed | Rẻ nhất (<2 ms), đã chạy sẵn cho review-summary |
| **L2 semantic** | Valkey Search FT.SEARCH (copilot + product-reviews, index riêng) | Valkey 8.2 có vector search HNSW cosine; cả hai service đều đã kết nối Valkey sẵn |
| **L3 prompt cache** | Bedrock `cacheable=True` | Miễn phí, chỉ cần ghi nhận |

### 2. Key L1 gồm 7 phần — mỗi phần chặn một kiểu trả sai
`copilot:answer:{user_id}:{model_ver}:{code_fp}:{catalog_fp}:{mem_fp}:{sess_fp}:{question_fp}`

- `user_id` — **ranh giới người dùng**: cache của A không bao giờ phục vụ B.
- `code_fp` — băm `copilot_server.py|agent.py|tools.py|memory.py`. Deploy bản mới mà
  key không đổi thì cache phục vụ câu trả lời của build cũ; đo 27/07: sau khi vá bộ
  lọc category, câu hỏi cũ vẫn trả kết quả sinh lúc search còn hỏng.
- `catalog_fp` — fingerprint sống của catalog + review: **nguồn đổi → key đổi → miss**.
- `mem_fp` — memory đổi thì câu trả lời cá nhân hoá cũng phải đổi.
- `sess_fp` — băm lịch sử phiên. Câu phụ thuộc ngữ cảnh ("Nó có phù hợp không?") mà
  chỉ băm chữ thì phiên khác hỏi y hệt sẽ nhận lại câu của phiên trước — "nó" trỏ sản
  phẩm khác. Đo 27/07: lượt 3 ra `hit_exact` với nội dung phiên cũ.
- `question_fp` — băm câu hỏi **thuần**, không băm câu đã nối memory (nối vào thì key
  đổi mỗi lượt, không bao giờ hit).

### 3. L2 semantic: ngưỡng **không đủ**, phải có rule-guard
Sweep đo thật (`docs/ai/evals/param_sweep_m23.md`, Titan v2, 4 cặp cùng ý + 5 cặp
khác nghĩa):

- cặp **khác nghĩa** cao nhất **0.9191** ("dưới 200 USD" ↔ "trên 200 USD")
- cặp **cùng ý** thấp nhất **0.6587**

Hai nhóm **chồng lấn hoàn toàn** → mọi ngưỡng bắt được paraphrase đều kéo theo
false-hit 20%. Vì vậy thêm `pb/semantic_guard.py`: hai câu chỉ là một khi trùng ở
**phủ định · toán tử so sánh · con số · tên riêng**. Guard đưa false-hit về **0% ở mọi
ngưỡng**; chọn `SEMANTIC_CACHE_MIN_SIM = 0.85` theo luật viết trước khi chạy —
*recall cao nhất trong nhóm false-hit = 0, hoà thì lấy ngưỡng CAO NHẤT* (lấy thấp
nhất thì cosine mất tác dụng, an toàn phó mặc hết cho guard).

Tìm kiếm L2 chỉ trong `scope` hash của `scope_key` đã ghim trạng thái nguồn, nên similarity chỉ quyết
định *"có cùng một câu hỏi không"*, còn *"câu trả lời còn đúng không"* do fingerprint lo.

### 4. Bypass thay vì cache câu chạm giỏ hàng
Câu chạm `get_cart` / `add_item_to_cart` → `cache_status: bypass`. Cache sai trạng
thái giỏ tệ hơn không cache.

### 5. Memory hai tầng, khác chỗ lưu
- **Ngắn hạn** → Valkey `copilot:session:{session_id}`, TTL 1h, kèm `owner_user_id`
  (session của người khác → bỏ ngữ cảnh, mở phiên mới).
- **Dài hạn** → **Postgres `ai.user_memory`**, KHÔNG để Valkey: ElastiCache có
  eviction (`volatile-lru`) và **không bật snapshot** — mất node là mất sạch, trong
  khi mandate đòi "thông tin bền".
- **PII redact trước khi ghi** (`redact_pii` trong `pb/ml_guard_client.py`).

### 6. Chủ đề câu hỏi KHÔNG phải sở thích
Extraction chỉ ghi `preferred_category`/`use_case` khi khách nói ở ngôi thứ nhất kèm
động từ ý muốn ("mình thích / đang tìm / muốn mua"). Ghi theo mọi câu hỏi gây hai
hỏng cùng lúc: memory sai người dùng, và `mem_fp` đổi mỗi lượt nên **hit-rate = 0**
(đo 27/07: 0/12 trên bộ 50% lặp).

## Consequences

- **Positive:** yêu cầu lặp không tốn token; nguồn đổi thì tự miss; ranh giới user là
  hard bar có ca đo; số trước-sau đo bằng **hai lần chạy thật** (một lần vô hiệu cache)
  chứ không ngoại suy.
- **Negative:** L2 chịu eviction như mọi cache và không phải memory bền; `code_fp` khiến **mọi lần deploy
  làm nguội cache** (đánh đổi có chủ đích: thà nguội còn hơn trả cũ sai); rule-guard là
  heuristic tiếng Việt, phải mở rộng khi thêm ngôn ngữ.
- **Prod cần một bước migration có người chạy:** bảng `ai.user_memory` trên RDS
  (`docs/ai/migrations/m23_ai_schema.sql`), chưa chạy trong vòng này.

## Đính chính sau nghiệm thu (28/07)

Các phát hiện từ 10+ vòng eval liên tục, đã sửa trong code:

### 1. Cache envelope — giữ provenance khi hit
Entry cache phải là JSON `{v:1, t:"câu trả lời", c:[...citations...], a:[...tool records...]}`.
Chỉ lưu text thuần → khi hit MANDATE-14 nhận `citations=[]`, `actionsTaken=[]` → chấm trượt
grounding/citation/task (đo 28/07: 7 ca fail trong một vòng đều là cache hit).
Áp dụng cho cả copilot L1+L2 lẫn product-reviews L1+L2.

### 2. `cacheable: False` cho câu trả lời thay thế
3 nhánh không được cache: output bị rail chặn (rơi về fallback), output rỗng sau khi strip
`<thinking>`, và vượt `MAX_TOOL_CALLS`. Cache những câu này thì một lần ml-guard chậm được phục
vụ lại suốt TTL.

### 3. L2 của product-reviews nằm ở Valkey (không phải Postgres)
Ban đầu dùng Postgres `ai.semantic_cache` (pgvector) vì audit ban đầu kết luận Valkey 7.2
không có vector search. Thực tế prod là Valkey **8.2** có FT.SEARCH đầy đủ, và
product-reviews đã kết nối Valkey cho L1. Ngày 28/07 migrate về Valkey (`reviews-semantic-idx`,
prefix `reviews:semantic:item:*`) — cùng backend với copilot, `clear_cache` chỉ cần quét một
backend.

### 4. Guard `product_id` ở tools.py
`get_product_reviews` phải từ chối tham số không khớp `[A-Z0-9]{10}` — model hay truyền
**tên** sản phẩm ("Roof Binoculars") vào `product_id`, service trả 0 review, model nói với
khách "chưa có đánh giá" trong khi có 5 review (đo 28/07). Trả `{status:"invalid_product_id",
next_action:"search_products_first"}` để model tự tra id trước.

### 5. Mô tả tool cũng là chỉ dẫn nội bộ
`SYSTEM_PROMPT_GUARDED` (needle của `leaks_system_prompt`) trước đây chỉ có phần RULES —
model in nguyên văn mô tả `get_shipping_quote` ra cho khách mà detector không bắt (hidden set
28/07). Ghép thêm `description` của `TOOLS_DEFINITION` vào needle.

## Alternatives Considered
- **Chỉ nâng ngưỡng similarity (0.93–0.95)** thay vì rule-guard: số đo bác bỏ — cặp
  khác nghĩa đạt 0.9191 còn cặp cùng ý 0.6587.
- **Memory dài hạn trong Valkey**: nhanh hơn nhưng có eviction và không backup → vi
  phạm yêu cầu "thông tin bền".
- **Cache cả câu chạm giỏ hàng**: hit-rate đẹp hơn, đổi lại trả sai trạng thái giỏ.
- **Tắt hẳn L2, nộp bằng L1** (sàn đạt theo memo): giữ làm phương án lùi nếu Valkey
  Search không khả dụng; hiện không cần vì false-hit đo được = 0.
