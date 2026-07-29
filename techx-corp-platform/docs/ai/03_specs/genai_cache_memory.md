# GenAI Cache & Memory Specification (MANDATE-23 Updated)

## 1. Kiến trúc 3 tầng cache (Multi-tier AI Caching)
- **L1 (Exact Match Cache)**: Cache nguyên vẹn kết quả vào Valkey 8.2 với Key băm content-addressed 7 phần:
  `copilot:answer:{user_id}:{model_ver}:{code_fp}:{catalog_fp}:{mem_fp}:{sess_fp}:{question_fp}`. Độ trễ < 2ms.
- **L2 (Semantic Match Cache)**: Valkey 8.2 FT.SEARCH (`copilot-semantic-idx` & `reviews-semantic-idx`) sử dụng HNSW Cosine Vector Search kết hợp **Deterministic Rule Guard** (`semantic_guard.py`) để loại bỏ hoàn toàn false-hits.
- **L3 (Bedrock Prompt Cache)**: Tận dụng cơ chế `cacheable: True` của Bedrock Converse API cho phần System Prompt tĩnh (giảm 50-90% token/trễ khi L1 và L2 miss).

## 2. Ngưỡng Similarity & Phạm vi tìm kiếm (Scope & Guard)
- **Scope Key**: `copilot:{user_id}:{model_ver}:{prompt_ver}:{catalog_fp}` (Tự động invalidation khi nguồn đổi).
- **Similarity Threshold (`SEMANTIC_CACHE_MIN_SIM`)**: `0.85` kết hợp với Rule-Guard (`same_question`). Rule-Guard bắt buộc kiểm tra các dấu hiệu phủ định, mốc giá, con số và tên sản phẩm để đạt **False Hit = 0%**.
- **Cache Envelope**: Lưu trữ dưới dạng JSON `{v: 1, text: "...", citations: [...], tool_actions: [...]}` nhằm bảo toàn thông tin grounding metadata khi hit cache.

## 3. Quản lý Memory hai tầng
- **Short-term Memory (Session)**: Lưu trữ tạm thời trong Valkey (`copilot:session:{session_id}`) với TTL = `3600s` và cờ `owner_user_id` để phòng chống mượn bối cảnh chéo user.
- **Long-term Memory (Persistent)**: Lưu trữ trong PostgreSQL `ai.user_memory`. Không lưu ở Valkey để tránh rủi ro LRU eviction làm mất thông tin lâu dài của user.

## 4. Bảo vệ quyền riêng tư & An toàn (PII & Isolation)
- **Cờ `cache_status`**: Báo cáo rõ `hit_exact`, `hit_semantic`, `miss`, `bypass` trong response.
- **Bypass giỏ hàng**: Tất cả các lệnh chạm giỏ hàng (`add_item_to_cart`, `get_cart`) đều bị từ chối cache (`cache_status: bypass`).
- **Cô lập ranh giới User**: Gắn chặt `user_id` ở mọi scope cache & session key. Đảm bảo Zero Cross-user leak.
- **Làm mờ PII**: Thông tin cá nhân nhạy cảm (email, SĐT) phải chạy qua ML guardrail `redact_pii` làm mờ trước khi lưu vào kho nhớ dài hạn `ai.user_memory`.

