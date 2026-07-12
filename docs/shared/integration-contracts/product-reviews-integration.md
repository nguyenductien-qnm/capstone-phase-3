# Hợp Đồng Tích Hợp Kỹ Thuật (Integration Contract) — Product Reviews Service

* **Đơn vị sở hữu**: AI Team (AIO03) & Platform Team (CDO)
* **Trạng thái**: Draft
* **Ngày cập nhật**: 2026-07-09

Tài liệu này đặc tả cam kết tích hợp kỹ thuật cho dịch vụ **Product Reviews** (Python gRPC Server trên cổng `3551`) để phục vụ tính năng lưu trữ cache đánh giá và khả năng tự phục hồi (resiliency) khi gọi dịch vụ LLM.

---

## 1. Thông Số Môi Trường & Kết Nối (Connection & Env Variables)

Dịch vụ `product-reviews` nhận các biến môi trường cấu hình kết nối sau:

| Tên biến | Kiểu dữ liệu | Giá trị mặc định / Mô tả |
| :--- | :--- | :--- |
| `PRODUCT_REVIEWS_PORT` | Integer | `3551` (Cổng chạy gRPC của service) |
| `DB_CONNECTION_STRING` | String | Chuỗi kết nối tới cơ sở dữ liệu PostgreSQL của Reviews |
| `LLM_HOST` | String | `llm` (Host chạy dịch vụ Mock LLM) |
| `LLM_PORT` | Integer | `8000` (Cổng của dịch vụ Mock LLM) |
| `LLM_BASE_URL` | String | `http://llm:8000/v1` (Địa chỉ API OpenAI-compatible của LLM) |
| `LLM_MODEL` | String | `techx-llm` (Tên model mặc định) |
| `OPENAI_API_KEY` | String | `dummy` (API key phục vụ việc gọi thư viện OpenAI client) |
| `PRODUCT_CATALOG_ADDR` | String | `product-catalog:8080` (Địa chỉ gRPC của danh mục sản phẩm) |
| `FLAGD_HOST` | String | `flagd` (Host của OpenFeature Flagd) |
| `FLAGD_PORT` | Integer | `8013` (Cổng kết nối Flagd) |
| `VALKEY_HOST` | String | `valkey-cart` hoặc service cache chung của CDO cung cấp |
| `VALKEY_PORT` | Integer | `6379` (Cổng kết nối Valkey/Redis) |

---

## 2. Ràng Buộc Tài Nguyên K8s (Kubernetes Resource Limits)

Để đảm bảo tối ưu hóa chi phí vận hành cụm EKS của dự án, pod của dịch vụ `product-reviews` phải tuân thủ giới hạn tài nguyên:

* **CPU Request**: `100m`
* **CPU Limit**: `500m`
* **Memory Request**: `128Mi`
* **Memory Limit**: `512Mi`

---

## 3. Cơ Chế Tự Phục Hồi & Lưu Trữ Cache (Resilience & Caching Contract)

Để đối phó với các kịch bản lỗi giả định từ OpenFeature (như `llmRateLimitError`), dịch vụ `product-reviews` cam kết triển khai các cơ chế sau:

### 3.1. Bộ nhớ Cache Valkey (Redis-compatible)
* **Chiến lược Caching**: Khi có yêu cầu tóm tắt đánh giá sản phẩm (`AskProductAIAssistant`), hệ thống sẽ kiểm tra trong Valkey cache trước:
  - Nếu tồn tại dữ liệu (`Cache Hit`): Trả ngay phản hồi mà không cần gọi sang Mock LLM.
  - Nếu không tồn tại dữ liệu (`Cache Miss`): Gọi LLM để sinh phản hồi, sau đó ghi kết quả vào Valkey cache với **Dynamic TTL (4 giờ – 7 ngày)**, key `reviews:summary:{product_id}:{model_ver}:{prompt_ver}`. Xem `specs/valkey_caching.md` §5, §6.
  - ⚠️ **Trạng thái LLM backend:** hiện `product-reviews` gọi **mock LLM in-cluster** (`http://llm:8000/v1`, OpenAI SDK), *không phải* Bedrock. Việc chuyển sang Amazon Bedrock Nova Lite (theo ADR-004) được theo dõi ở **TF1-58 Bước 1**. Cho tới khi đó, cost model ở `pitch.md` chỉ áp dụng cho Shopping Copilot.
* **Key format**: `reviews:summary:{product_id}`.

### 3.2. Cơ chế Fallback và Isolation (Circuit Breaker)
* **Fallback**: Khi Mock LLM trả về mã lỗi HTTP `429` (Rate limit exceeded) hoặc không khả dụng:
  - Hệ thống sẽ tìm trong cache. Nếu cache trống, trả về nội dung tĩnh local được biên soạn trước dựa trên điểm đánh giá trung bình từ database (ví dụ: *"Sản phẩm có đánh giá tốt, điểm trung bình là X/5 sao"*).
* **Timeout & Retry**:
  - Thiết lập timeout tối đa cho mỗi yêu cầu gọi LLM là **3 giây**.
  - Áp dụng cơ chế **Retry** tối đa 3 lần với **Exponential Backoff** (độ trễ tăng dần `0.5s`, `1s`, `2s`) kèm theo độ nhiễu ngẫu nhiên (jitter) để tránh hiện tượng dồn ép yêu cầu (thundering herd).
* **Circuit Breaker**:
  - Theo dõi tỷ lệ lỗi gọi LLM trong cửa sổ trượt (sliding window). Nếu tỷ lệ lỗi vượt quá 50% trong 10 yêu cầu gần nhất, ngắt mạch (`Open`) ngay lập tức trong 30 giây để kích hoạt nhanh luồng Fallback mà không cần gửi yêu cầu lên LLM.

---

## 4. Đặc Tả Telemetry (Prometheus & Jaeger Contract)

Cam kết cung cấp đầy đủ thông tin telemetry phục vụ việc giám sát AIOps:

### 4.1. Prometheus Custom Metrics
Dịch vụ sẽ export các metric qua cổng OTel collector hoặc Prometheus exporter:

1. **`llm_request_latency_seconds`** (Histogram):
   - Đo độ trễ (latency) của các cuộc gọi thành công lên LLM.
   - Buckets đề xuất: `[0.1, 0.25, 0.5, 1.0, 2.5, 5.0]`.
2. **`llm_token_consumption_total`** (Counter):
   - Đo số lượng token tiêu thụ lũy kế của LLM.
   - Nhãn (Labels): `model`, `type` (`prompt_tokens` hoặc `completion_tokens`).
3. **`llm_error_rate_total`** (Counter):
   - Đếm số lượng cuộc gọi LLM bị lỗi.
   - Nhãn (Labels): `error_code` (VD: `429`, `500`, `timeout`), `model`.
4. **`reviews_cache_hit_ratio`** (Counter/Gauge):
   - Ghi nhận trạng thái cache hit/miss của Valkey.
   - Nhãn (Labels): `status` (`hit` hoặc `miss`).

### 4.2. Trace Context Spans (Jaeger)
* **Trace Context Propagation**: Mọi yêu cầu gọi từ dịch vụ sang LLM phải thực hiện inject HTTP headers để liên kết trace context.
* **Span Attributes**: Bắt buộc gắn các thông tin sau lên Span gọi LLM:
  - `gen_ai.system`: `"openai"` (hoặc `"bedrock"` khi chuyển sang LLM thật).
  - `gen_ai.model_id`: Tên model sử dụng (ví dụ: `techx-llm`).
  - `gen_ai.usage.prompt_tokens`: Số token đầu vào thực tế từ API response.
  - `gen_ai.usage.completion_tokens`: Số token đầu ra thực tế từ API response.
  - `error.type`: Ghi nhận mã lỗi cụ thể nếu có lỗi xảy ra.



---

## Phụ lục 12/07/2026 — đề xuất cập nhật hợp đồng (cần CDO re-sign)

Ba điểm đã lệch thực tế sau PR#26 (bảng trên giữ nguyên vì đã ký; bảng dưới là nội dung đề xuất thay thế):

1. **LLM backend:** `product-reviews` ĐÃ gọi AWS Bedrock (Converse API, boto3) — không còn "chờ TF1-58". Mock LLM chỉ còn dùng cho luồng sự cố `llmRateLimitError` (`LLM_MOCK_ENABLED=true`).
2. **Env không còn bắt buộc:** `LLM_BASE_URL`, `LLM_MODEL`, `OPENAI_API_KEY` — code đã bỏ khỏi `must_map_env` (chỉ còn cần `LLM_HOST/PORT` cho mock).
3. **Env/flag mới cần CDO cấp qua chart:**

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `AWS_REGION` / `AWS_BEDROCK_MODEL` | `us-east-1` / `amazon.nova-lite-v1:0` | + IAM `bedrock:InvokeModel` (IRSA hoặc node role) — **đang thiếu, chặn T2** |
| `LLM_REVIEWS_MAIN_MODEL` / `LLM_REVIEWS_FALLBACK_MODEL` | nova-lite / nova-micro | routing |
| `LLM_REVIEWS_TIMEOUT` / `LLM_REVIEWS_FALLBACK_TIMEOUT` | 3.0 / 2.0 | giây |
| `LLM_REVIEWS_MAX_RETRIES` / `LLM_REVIEWS_FALLBACK_RETRIES` | 2 / 1 | |
| `LLM_BULKHEAD_SIZE` | 6 | phải < gRPC max_workers (10) |
| `LLM_CB_THRESHOLD` / `LLM_CB_COOLDOWN` | 3 / 30 | circuit breaker |
| `VALKEY_HOST` / `VALKEY_PORT` | valkey-cart / 6379 | cache tóm tắt |
| flagd: `llmReviewsFallbackEnabled` (on), `llmReviewsCacheEnabled` | | đã thêm vào demo.flagd.json 12/07 |
