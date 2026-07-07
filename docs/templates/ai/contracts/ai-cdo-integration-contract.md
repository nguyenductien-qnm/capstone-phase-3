# Hợp Đồng Tích Hợp Kỹ Thuật (Integration Contract) — TF1 (AI & CDO)

* **Nhóm sở hữu:** AI Team (AIO03) & Platform Team (CDO05, CDO09)
* **Người phê duyệt:** [AI Lead Name] & [CDO Lead Name]
* **Trạng thái:** Draft | Accepted
* **Ngày cập nhật:** YYYY-MM-DD

---

## 1. Hợp Đồng Giao Tiếp gRPC (API Contract)

### 1.1 Khai báo cổng dịch vụ (Port Mapping):
- Dịch vụ **Shopping Copilot** (Python gRPC Server) sẽ chạy ở cổng: `[Cổng gRPC, e.g., 50051]`.
- Envoy Proxy (`frontend-proxy`) của CDO có trách nhiệm định tuyến các request từ Client qua giao thức gRPC-Web tới cổng này.

### 1.2 Protobuf Contract (`.proto`):
Chi tiết định nghĩa dịch vụ gRPC của Agent Shopping Copilot sẽ được lưu trữ tại `techx-corp-platform/proto/shopping_copilot.proto`. Hai bên cam kết không tự ý thay đổi file proto này nếu chưa có sự đồng thuận của cả hai nhóm.

---

## 2. Hợp Đồng Hạ Tầng (Infrastructure & Deployment Contract)

### 2.1 Cụm Cache Valkey (Redis-compatible):
- CDO có trách nhiệm deploy một pod/cluster **Valkey** (Redis) trong cùng namespace với ứng dụng.
- Thông tin kết nối sẽ được truyền vào service AI qua các biến môi trường:
  - `VALKEY_HOST`: Tên service của Valkey.
  - `VALKEY_PORT`: Cổng kết nối (mặc định: `6379`).

### 2.2 Ràng buộc Tài nguyên (Resource Limits) của Pod AI:
Hai bên thống nhất mức cấu hình tài nguyên cho các pod AI để đảm bảo nằm trong giới hạn ngân sách ($300/tuần):
- **`product-reviews`:** CPU request [X]m / limit [Y]m, Memory request [X]Mi / limit [Y]Mi.
- **`shopping-copilot`:** CPU request [X]m / limit [Y]m, Memory request [X]Mi / limit [Y]Mi.

---

## 3. Hợp Đồng Giám Sát Telemetry (Metrics & Tracing Contract)

### 3.1 Khai báo Trace Spans (Jaeger):
- Dịch vụ AI cam kết inject đầy đủ `TraceContext` cho mọi cuộc gọi gRPC và HTTP đi sang LLM.
- Các span gọi LLM bắt buộc chứa các attribute tiêu chuẩn:
  - `gen_ai.model_id`: ID của model Bedrock.
  - `gen_ai.usage.prompt_tokens`: Số lượng token đầu vào.
  - `gen_ai.usage.completion_tokens`: Số lượng token đầu ra.

### 3.2 Khai báo Custom Metrics (Prometheus):
Dịch vụ AI sẽ export các chỉ số metric đặc thù qua Prometheus exporter để CDO cấu hình Grafana:
- `llm_request_latency_seconds`: Đo độ trễ cuộc gọi LLM (histogram).
- `llm_token_consumption_total`: Đo số lượng token tiêu thụ lũy kế (counter).
- `llm_error_rate_total`: Đo số lượng lỗi 429/500 từ Bedrock (counter).
