# Hợp Đồng Tích Hợp Dịch Vụ: Product Reviews

* **Dịch vụ tích hợp:** `product-reviews` (Python gRPC Server)
* **Nhóm sở hữu:** AI Team (AIO03) & Platform Team (CDO05/CDO09)
* **Người phê duyệt:** [AI Lead Name] & [CDO Lead Name]
* **Trạng thái:** Draft | Accepted
* **Ngày cập nhật:** YYYY-MM-DD

---

## 1. Hạ Tầng Caching (Valkey)
Để tối ưu hóa chi phí token và giảm độ trễ dưới tải cao, dịch vụ Reviews sẽ sử dụng cache Valkey:
- **CDO cam kết:** Deploy một cụm/pod **Valkey** (Redis-compatible) trong namespace chung của cụm EKS.
- **Biến môi trường tiêm vào Reviews pod:**
  - `VALKEY_HOST`: Tên service K8s của Valkey (ví dụ: `valkey-cart` hoặc `valkey-reviews-service`).
  - `VALKEY_PORT`: Cổng kết nối (mặc định: `6379`).

---

## 2. Giới Hạn Tài Nguyên (Kubernetes Resource Limits)
Thống nhất giới hạn tài nguyên cho pod `product-reviews` trên môi trường EKS:
- **CPU:** Request: `100m` · Limit: `500m`
- **Memory:** Request: `128Mi` · Limit: `512Mi`
- **Replicas:** Minimum: `2` · Maximum: `5` (Autoscaling dựa trên CPU usage > 70%).

---

## 3. Giám Sát Telemetry (Metrics & Tracing)
- **Jaeger Tracing:** Dịch vụ Reviews cam kết bắt và lan truyền đầy đủ `TraceContext` cho mọi cuộc gọi LLM. Các span bắt buộc có attribute:
  - `gen_ai.model_id`: ID model Bedrock.
  - `gen_ai.usage.prompt_tokens`: Tokens đầu vào.
  - `gen_ai.usage.completion_tokens`: Tokens đầu ra.
- **Prometheus Metrics:** Dịch vụ Reviews export các chỉ số:
  - `llm_request_latency_seconds`: Độ trễ cuộc gọi API LLM (Histogram).
  - `llm_error_rate_total`: Số lượng lỗi 429/500 từ Bedrock (Counter).
