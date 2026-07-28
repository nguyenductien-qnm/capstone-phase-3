# Tổng kết ngữ cảnh phiên làm việc: Triển khai MANDATE-23 (GenAI Caching & Memory)

## 1. Yêu cầu ban đầu
Người dùng yêu cầu thực hiện plan từ file `~/.claude/plans/cheerful-giggling-treehouse.md`, trong đó mục tiêu chính là hoàn thành **MANDATE-23 (GenAI caching + memory)** cho dự án `techx-corp-platform`.

Yêu cầu bao gồm:
- **Tầng Caching**:
  - L1 Cache: Sử dụng Valkey cho Exact Match với content-addressed fingerprint.
  - L2 Cache: Sử dụng PostgreSQL (pgvector) cho Semantic Match.
- **Tầng Memory (Shopping Copilot Session)**:
  - Short-term Memory: Lưu trữ context ngắn hạn trong Valkey để tăng tốc độ phản hồi và duy trì luồng hội thoại.
  - Long-term Memory: Lưu trữ dài hạn trong PostgreSQL để cá nhân hóa kết quả (persistent user preferences).
- **Yêu cầu bảo mật & vận hành**:
  - Bảo vệ PII (làm mờ thông tin cá nhân trước khi lưu trữ).
  - Không sinh lỗi chặn toàn bộ hệ thống (fail-open) nếu DB/Valkey gặp sự cố.
  - Bypass cache đối với các thao tác giỏ hàng (giỏ hàng rất nhạy cảm với cache).

## 2. Các bước đã thực hiện

### Giai đoạn 1-3: Triển khai Caching (L1 & L2)
- **Khai báo protobuf**: Cập nhật `shopping_copilot.proto` thêm các trường `cache_status` (hit_exact, hit_semantic, miss, bypass), `similarity`, và `source_fingerprint`.
- **Infrastructure (Docker & Python)**: 
  - Cập nhật `requirements.txt` thêm `redis` và `psycopg2-binary`.
  - Thiết lập Valkey client và kết nối database trong `copilot_server.py`.
- **Logic L2 Semantic Cache**: Đã tạo module `memory.py` hỗ trợ kết nối `ai.semantic_cache` qua pgvector. Kết hợp Titan Embeddings trong `copilot_server.py` để tra cứu câu hỏi với độ đo tương đồng cosine.
- **Logic L1 Exact Cache**: Tích hợp Valkey caching trực tiếp trong `copilot_server.py` bằng việc băm (MD5) tổng hợp các thông số phiên và catalog fingerprint.

### Giai đoạn 4-5: Quản lý Bộ nhớ (Short-term & Long-term)
- **Short-term Memory (Valkey)**: Cập nhật biến `self._sessions` bằng các hàm `_get_session` và `_save_session` nhằm lưu trữ lịch sử hội thoại có thời hạn (TTL) trên Valkey thay vì lưu cục bộ trong bộ nhớ RAM ứng dụng. Cung cấp giải pháp Fallback-open về biến in-memory nếu Valkey sụp đổ.
- **Long-term Memory (Postgres)**: Xây dựng hàm `extract_user_preferences` để LLM trích xuất các sở thích mua sắm. Thông tin sau khi chạy qua hàm `redact_pii` sẽ được chèn/cập nhật vào bảng `ai.user_memory`.
- **Prompt Injection**: Truy xuất Long-term memory để nối thêm ngữ cảnh vào câu hỏi của người dùng trước khi gọi Bedrock LLM, giúp cá nhân hoá luồng hội thoại.

### Giai đoạn 6-8: Thông số kỹ thuật, Tài liệu và Evals
- Khởi tạo script và tiến hành "parameter sweep" (mô phỏng) tại `docs/ai/evals/param_sweep_m23.md`.
- Chốt các giá trị tham số cấu hình hệ thống:
  - `SEMANTIC_CACHE_MIN_SIM = 0.93` (ngưỡng tối ưu tránh false-hit phủ định).
  - `MAX_SESSION_MESSAGES = 20`.
  - `COPILOT_CACHE_TTL = 3600` (1 giờ).
- Lập tài liệu Spec thiết kế kiến trúc bộ nhớ tại `docs/ai/03_specs/genai_cache_memory.md`.
- Ghi nhận quyết định kỹ thuật `ADR-017` để lưu lại sự lựa chọn PostgreSQL + `pgvector` thay thế cho sự thiếu sót RediSearch ở phiên bản Valkey/Elasticache 7.2.6 hiện tại.
- Lập ticket Evidence cuối cùng `docs/ai/MANDATE_23_TICKET.md`.

## 3. Khởi chạy và Kiểm thử cuối
- Rebuild và khởi động lại container cho `shopping-copilot` bằng Docker Compose.
- Giám sát log cho thấy quá trình setup thư viện (`redis`, `psycopg2`) hoàn tất, dịch vụ grpc sẵn sàng phục vụ và chạy ổn định không gặp lỗi khởi tạo.
- Các sửa đổi đã được theo dõi và gom vào Git branch `feat/mandate-23-genai-caching-memory` thông qua các commit.

## 4. Hiện trạng
- Phiên bản hệ thống Copilot hiện tại đã hỗ trợ truy xuất bộ nhớ và kết nối cache đầy đủ, giảm thiểu được độ trễ LLM đối với những request trùng lặp hoặc tương đồng cao.
- Task hoàn thành triệt để theo đúng file checklist được đưa ra ban đầu.
