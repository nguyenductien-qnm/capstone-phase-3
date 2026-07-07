# Backlog ưu tiên - TF1 / AI Team (AIO03) & Platform Team (CDO05, CDO09)

---

## 1. Đánh giá hệ thống hiện tại
TechX Corp Platform là hệ thống thương mại điện tử microservices giao tiếp qua gRPC, database PostgreSQL và hàng đợi Kafka. Tầng AI hiện tại gồm `product-reviews` server và Mock `llm` completions service. 

Qua đánh giá sơ bộ baseline, nhóm AI xác định 4 rủi ro lớn nhất:
- **Rủi ro 1 (Reliability - SPOF):** Dịch vụ Mock LLM là điểm chết đơn lẻ (SPOF) chạy single-replica, chưa có cơ chế fallback. Nếu Bedrock gặp lỗi 429/500 hoặc timeout, luồng hiển thị review sản phẩm sẽ bị treo, trực tiếp vi phạm SLO của storefront.
- **Rủi ro 2 (Security - Prompt Injection):** Reviews đầu vào của khách hàng được gửi thẳng lên LLM mà không qua lọc hay chuẩn hóa, cho phép tin tặc thực hiện Prompt Injection/Jailbreak để lấy cắp System Prompt hoặc dữ liệu nhạy cảm PII.
- **Rủi ro 3 (Cost - Token Burn Rate):** Chưa có lớp cache cho bản tóm tắt review. Khi chạy các kịch bản load test của CDO, hệ thống sẽ gọi LLM liên tục, gây cháy ngân sách token trong trần $300/tuần.
- **Rủi ro 4 (Auditability - Telemetry Blindness):** Telemetry OpenTelemetry hiện tại chưa bắt các chỉ số token tiêu thụ và latency riêng của LLM, khiến đội vận hành bị mù thông tin khi giám sát sự cố AI.

---

## 2. Backlog xếp hạng (AI Team)

*Dưới đây là danh sách việc của AI Team được xếp hạng theo thứ tự ưu tiên (Rủi ro × Tác động Business) cho Tuần 1 và định hướng Tuần 2:*

| # | Việc | Trụ | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Cost Δ/tuần | Effort | Vì sao ưu tiên bậc này |
|---|------|-----|-------------------------------|-------------------|-------------|--------|------------------------|
| 1 | **[AIE-Plan] Cấu hình AWS Bedrock & Lập Cost Model** | Cost | Cao (4 × 4 = 16) | Tránh vượt ngân sách $300/tuần | Tiết kiệm token | Thấp | Cần thiết lập model thật và tính toán chi phí trước khi code |
| 2 | **[AIE-Plan] Thiết kế đặc tả Valkey Caching cho Review** | Cost & Performance | Cao (4 × 3 = 12) | Giảm latency p95 < 100ms, tiết kiệm 70% token | -$50 (giảm token) | Trung bình | Giải quyết trực tiếp bài toán quá tải chi phí khi CDO chạy load test |
| 3 | **[AIOps-Plan] Đặc tả cơ chế Fallback (Sonnet->Haiku), Timeout & Retry** | Reliability | Cao (3 × 4 = 12) | Đảm bảo tính sẵn sàng khi Bedrock lỗi 429/500 | Không đáng kể | Trung bình | Bảo vệ SLO của Storefront khỏi các lỗi timeout và nghẽn API LLM |
| 4 | **[AIE-Plan] Đặc tả bộ lọc Prompt Injection & PII Guardrails** | Security | Trung bình (2 × 5 = 10) | Chặn lộ System Prompt và rò rỉ dữ liệu PII | Không | Trung bình | Bảo vệ tính toàn vẹn và an toàn thông tin cho hệ thống AI |
| 5 | **[AIE-Demo] Xây dựng bản chạy thử (PoC) Shopping Copilot trên Streamlit** | Performance | Trung bình (3 × 3 = 9) | Demo trực quan cho buổi Pitching nghiệm thu | Không | Cao | Cần bản PoC chạy thật gọi Bedrock local để chứng minh giải pháp với Mentors |
| 6 | **[AIOps-Plan] Đặc tả giám sát OpenTelemetry & Prometheus Custom Metrics** | Auditability | Trung bình (3 × 3 = 9) | Trace lỗi latency và token dùng của LLM | Không | Trung bình | Cần cấu hình metric để hiển thị lên Grafana cho AIOps monitor |
| 7 | **[AIOps-Plan] Thiết kế Anomaly Detection (EWMA) & Log Mining (Drain3)** | Reliability | Thấp (2 × 3 = 6) | Phát hiện sớm sự cố (MTTD < 30s) bằng log/metrics | Không | Cao | Tạo nền tảng để AIOps tự động phân tích log và gửi cảnh báo Slack |
| 8 | **[AIOps-Plan] Thiết kế RCA Engine & Auto-Remediation loops** | Reliability | Thấp (2 × 3 = 6) | Chẩn đoán lỗi bằng causal tree, giảm MTTR | Không | Cao | Thiết lập cơ chế tự động sửa lỗi (restart pod, rollback config) |

*<!-- CDO Team Section: CDO leads will append their infrastructure tasks here -->*

---

## 3. Cố ý bỏ (lúc này)
- **Deploy Shopping Copilot EKS (Tuần 1):** Tạm thời chưa đưa Copilot lên EKS trong Tuần 1 vì cần tập trung hoàn thiện giao thức gRPC contract, cơ chế xác nhận giỏ hàng (Confirmation gate) và demo local trước để giảm thiểu rủi ro bảo mật hệ thống.
- **Dự báo dung lượng dài hạn (Capacity Forecasting):** Hoãn việc xây dựng mô hình dự báo dung lượng hệ thống vì hệ thống chưa tích lũy đủ dữ liệu logs/metrics trong 1 tuần đầu.

---

## 4. Ký tên
- **Trình bày:** Định Nguyễn (AI Team Lead AIO03) & AI Team members.
- **Ngày:** 2026-07-07.
