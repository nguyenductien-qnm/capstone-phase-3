# GenAI Cache & Memory Specification

## 1. Kiến trúc 3 tầng cache
- **L1 (Exact Match)**: Cache nội dung nguyên vẹn vào Valkey với key `copilot:answer:{user_id}:{model_ver}:{prompt_ver}:{catalog_fp}:{question_fp}`. Độ trễ cực thấp.
- **L2 (Semantic Match)**: Sử dụng pgvector kết hợp Amazon Titan Embeddings để bắt các câu tương đồng về ý nghĩa.
- **L3 (Bedrock Prompt Cache)**: Tận dụng cơ chế `cacheable: True` của Bedrock cho phần prefix.

## 2. Ngưỡng Similarity & Phạm vi tìm kiếm (Scope)
- **Scope Key**: `copilot:{user_id}:{model_ver}:{prompt_ver}:{catalog_fp}`
- **Similarity Threshold**: `0.93`. Không chọn thấp hơn vì rủi ro "lỗi im lặng" (false hits) từ câu phủ định hoặc sai mốc giá.

## 3. Quản lý Memory hai tầng
- **Short-term Memory (Session)**: Lưu trữ tạm thời (chính sách `volatile-lru`) trong Valkey thông qua key `copilot:session:{session_id}`. Các ngữ cảnh hội thoại được giữ theo TTL nhất định.
- **Long-term Memory (Persistent)**: Lưu trữ trong PostgreSQL `ai.user_memory`. Khác với Valkey, DB không có eviction policy rủi ro mất mát, đảm bảo độ tin cậy để truy xuất sở thích lâu dài của user.

## 4. Bảo vệ quyền riêng tư & An toàn (PII)
- Cờ `cache_status`: Báo cáo rõ hit/miss, tránh che dấu nguồn gốc dữ liệu. Tránh cache các lệnh nhạy cảm như thêm giỏ hàng.
- Ranh giới user: Tách bạch `user_id` ở mọi scope cache. Không có hiện tượng cross-user leak.
- Thông tin cá nhân phải chạy qua ML guardrail `redact_pii` làm mờ email/số ĐT... trước khi đưa vào kho nhớ dài hạn `ai.user_memory`.
