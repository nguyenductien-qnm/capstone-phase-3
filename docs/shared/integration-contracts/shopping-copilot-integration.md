# Hợp Đồng Tích Hợp Kỹ Thuật (Integration Contract) — Shopping Copilot Service

* **Đơn vị sở hữu**: AI Team (AIO03) & Platform Team (CDO)
* **Trạng thái**: Draft
* **Ngày cập nhật**: 2026-07-09

Tài liệu này đặc tả cam kết tích hợp kỹ thuật cho dịch vụ **Shopping Copilot** (Python gRPC Server trên cổng `50051`) để phục vụ tính năng hội thoại mua sắm thông minh (AI Agent) trực tiếp trên storefront.

---

## 1. Cổng Dịch Vụ & Định Tuyến (Port & Envoy Routing)

Để tích hợp gRPC service Shopping Copilot vào hệ thống chung của TechX Corp:

1. **Cổng Dịch Vụ**: Pod `shopping-copilot` sẽ lắng nghe các kết nối gRPC trên cổng **`50051`**.
2. **Định tuyến Envoy Proxy**: Nhóm CDO có trách nhiệm cấu hình Envoy (`frontend-proxy`) để giải mã và định tuyến các request gRPC-Web từ client.
   - Thêm cụm dịch vụ (cluster) mới tên là `shopping-copilot` trỏ tới cổng `50051`.
   - Định tuyến các request có prefix `/oteldemo.ShoppingCopilotService/` sang cluster `shopping-copilot`.
   - Bật hỗ trợ gRPC-Web filter trong Envoy để chuyển tiếp chính xác dữ liệu từ trình duyệt của khách hàng.

---

## 2. Thông Số Môi Trường & Kết Nối (Env Variables)

Dịch vụ `shopping-copilot` nhận các biến môi trường cấu hình kết nối sau:

| Tên biến | Kiểu dữ liệu | Giá trị mặc định / Mô tả |
| :--- | :--- | :--- |
| `SHOPPING_COPILOT_PORT` | Integer | `50051` (Cổng chạy gRPC của Agent) |
| `LLM_HOST` | String | `llm` (Host chạy dịch vụ Mock LLM) |
| `LLM_PORT` | Integer | `8000` (Cổng của dịch vụ Mock LLM) |
| `LLM_BASE_URL` | String | `http://llm:8000/v1` (Địa chỉ API OpenAI-compatible của LLM) |
| `LLM_MODEL` | String | `techx-llm` (Tên model mặc định) |
| `OPENAI_API_KEY` | String | `dummy` (API key gọi Mock LLM) |
| `PRODUCT_CATALOG_ADDR` | String | `product-catalog:8080` (Địa chỉ gRPC phục vụ công cụ tra cứu catalog) |
| `CART_ADDR` | String | `cart:8080` (Địa chỉ gRPC phục vụ công cụ quản lý giỏ hàng) |
| `PRODUCT_REVIEWS_ADDR` | String | `product-reviews:3551` (Địa chỉ gRPC phục vụ công cụ lấy review) |
| `FLAGD_HOST` | String | `flagd` (Host của OpenFeature Flagd) |
| `FLAGD_PORT` | Integer | `8013` (Cổng kết nối Flagd) |

---

## 3. Ràng Buộc Tài Nguyên K8s (Kubernetes Resource Limits)

Do Shopping Copilot là một Agent chạy các luồng xử lý và gọi công cụ phức tạp (Multi-turn Tool Calling), cấu hình tài nguyên được thống nhất như sau:

* **CPU Request**: `200m`
* **CPU Limit**: `1000m`
* **Memory Request**: `256Mi`
* **Memory Limit**: `1024Mi`

---

## 4. Đặc Tả Telemetry (Prometheus & Jaeger Contract)

Cam kết tích hợp OpenTelemetry phục vụ việc giám sát hoạt động của Agent:

### 4.1. Trace Context Propagation (Jaeger)
* **W3C Trace Context**: Shopping Copilot cam kết truyền nhận đầy đủ trace context (`traceparent`, `tracestate`) từ client storefront đi qua Envoy, vào dịch vụ Copilot và lan truyền tiếp sang các microservice hạ nguồn (`product-catalog`, `cart`, `product-reviews`) và dịch vụ LLM.
* **Span Attributes**: Các span gọi LLM của Copilot Agent bắt buộc chứa:
  - `gen_ai.system`: `"openai"` (hoặc `"bedrock"` khi chuyển sang LLM thật).
  - `gen_ai.model_id`: Tên model sử dụng.
  - `gen_ai.usage.prompt_tokens`: Số lượng token đầu vào.
  - `gen_ai.usage.completion_tokens`: Số lượng token đầu ra.

### 4.2. Prometheus Custom Metrics
Dịch vụ sẽ export các metric sau phục vụ hệ thống Dashboard giám sát của CDO:

1. **`copilot_chat_requests_total`** (Counter):
   - Đếm tổng số lượt yêu cầu hội thoại gửi tới Shopping Copilot.
   - Nhãn (Labels): `status` (`success`, `error`).
2. **`copilot_tool_calls_total`** (Counter):
   - Thống kê số lần Agent gọi các công cụ (tool calling) hạ nguồn.
   - Nhãn (Labels): `tool_name` (`search_products`, `get_product_reviews`, `add_item_to_cart`, `get_cart`), `status` (`success`, `error`).
3. **`copilot_chat_latency_seconds`** (Histogram):
   - Đo thời gian phản hồi tổng thể của một phiên hội thoại chat (từ lúc gửi request tới khi trả về text cuối cùng cho khách hàng).
   - Buckets đề xuất: `[0.5, 1.0, 2.5, 5.0, 7.5, 10.0]`.

---

## Phụ lục 14/07/2026 — Cập nhật AWS Bedrock & Model Gateway (Đua Top)

Các cập nhật liên quan tới triển khai AWS Bedrock và A/B Testing:

1. **Chuyển dịch sang AWS Bedrock:** `shopping-copilot` sử dụng SDK boto3 để gọi trực tiếp Amazon Bedrock thay vì gọi Mock LLM (`http://llm:8000/v1`). 
   - **Yêu cầu hệ thống (CDO):** Cấp quyền IAM Role for Service Accounts (IRSA) với Policy `bedrock:InvokeModel` cho pod `shopping-copilot`. Thiếu quyền này ứng dụng sẽ không thể hoạt động trên môi trường EKS.
2. **Routing qua Model Gateway:** `shopping-copilot` hiện sử dụng component `ModelRouter` để lấy cấu hình model từ OpenFeature/flagd.
   - **Biến flagd mới:** Cờ `llmModelRouting` (kiểu JSON Object) dùng chung với `product-reviews` để xác định tỷ lệ % traffic A/B.
3. **Môi trường & Biến Cấu hình:**
   - Cần đảm bảo có biến `AWS_REGION` (vd: `us-east-1`).
   - Cần biến `AWS_BEDROCK_MODEL` hoặc để Router tự điều phối. Các biến cũ `LLM_BASE_URL` và `OPENAI_API_KEY` chỉ giữ lại làm Fallback nếu sử dụng chế độ Mock.



