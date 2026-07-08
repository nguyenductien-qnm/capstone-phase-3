# Backlog ưu tiên - TF1 / AI Team (AIO03)

## 1. Đánh giá hệ thống hiện tại
Hệ thống hiện tại chạy trên K8s (EKS) với dịch vụ tóm tắt review (`product-reviews`) gọi trực tiếp API `llm` (mặc định là mock). Khi tích hợp API LLM thật (AWS Bedrock) và chạy dưới tải thực tế, hệ thống đối mặt với 3 rủi ro lớn nhất:
1. **Rủi ro vỡ trần chi phí Bedrock & Latency tăng cao (SLO p95 < 1s):** Việc gọi API LLM trực tiếp cho mỗi lượt duyệt sản phẩm mà không có bộ đệm (caching) sẽ làm phát sinh chi phí token khổng lồ và kéo dài thời gian phản hồi (p95 > 2s do độ trễ mạng API).
2. **Rủi ro gián đoạn dịch vụ khi API chính gặp lỗi (Reliability):** Nếu model chính (Claude 3.5 Sonnet) bị lỗi hoặc chạm ngưỡng giới hạn băng thông (Rate Limit - 429), tính năng tóm tắt review sẽ sập hoàn toàn nếu không có cơ chế tự động chuyển đổi sang model dự phòng (Fallback Routing).
3. **Rủi ro an toàn thông tin (Security & Excess Agency):** Trợ lý Shopping Copilot tự ý thực hiện các hành động ghi phá hoại giỏ hàng của khách (hoặc tự ý checkout) do bị Prompt Injection qua review sản phẩm, hoặc tự động hóa hành động không có sự xác nhận của người dùng.

---

## 2. Backlog xếp hạng (AI Team)

| # | Việc | Trụ | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Cost Δ/tuần | Effort | Vì sao ưu tiên bậc này |
|---|---|---|---|---|---|---|---|
| 1 | **Audit hệ thống reviews, telemetry & mocks** | Reliability / Observability | Cao × Cao (5×5 = 25) | Cần thiết để nắm được luồng dữ liệu trước khi cắm model thật | $0 | Thấp | Phải làm ngay ngày đầu để phát hiện nợ kỹ thuật và thiết lập trace span trên Jaeger. |
| 2 | **Dựng bản chạy thử Shopping Copilot PoC (Streamlit)** | Functional Capability | Trung bình × Cao (3×4 = 12) | Demo khả thi luồng gọi tool (catalog, cart) & Confirmation Gate | ~$5 (Bedrock testing) | Trung bình | Chứng minh tính khả thi của chatbot agent trước buổi bảo vệ pitching thứ Sáu. |
| 3 | **Thiết kế Spec Caching Valkey & Model Fallback Routing** | Cost / Reliability | Cao × Cao (4×4 = 16) | Giảm 90% chi phí token Bedrock; đảm bảo SLO trễ < 1s | $0 (Dùng chung Valkey-cart) | Thấp | Cần thiết để thống nhất kiến trúc và cấu hình biến ENV với nhóm CDO trước khi code ở Tuần 2. |
| 4 | **Xây dựng bộ dữ liệu Golden Dataset & script run_evals.py** | Auditability / Quality | Trung bình × Cao (3×4 = 12) | Đảm bảo tính trung thực (fidelity) của AI, chống bịa đặt (hallucination) | ~$2 (API test) | Trung bình | Chuẩn bị công cụ đo lường tự động để đánh giá chất lượng AI trước khi đẩy lên production. |
| 5 | **Thiết kế Spec gRPC cho Shopping Copilot & Anomaly Remediation** | Reliability / Performance | Trung bình × Trung bình (3×3 = 9) | Chốt interface API gRPC và luồng AIOps tự động xử lý sự cố | $0 | Trung bình | Định hình cổng kết nối và kịch bản vận hành tự động khắc phục lỗi (remediation loop) cho Tuần 3. |
| 6 | **Soạn thảo Pitch Slides bảo vệ kế hoạch & Cost Model** | Communication | Thấp × Cao (2×4 = 8) | Bảo vệ thành công ngân sách $300/tuần và cam kết SLO | $0 | Thấp | Tài liệu bắt buộc để báo cáo nghiệm thu Tuần 1. |

---

## 3. Cố ý bỏ (lúc này)
1. **Tích hợp chính thức Copilot vào Next.js Frontend:** Chưa làm tuần này vì cần chốt file `.proto` và giao diện Envoy proxy với Platform Team trước để tránh xung đột code.
2. **Triển khai tự động hóa xử lý sự cố (Auto-remediation script) chạy trên EKS:** Hoãn sang Tuần 3 vì cần kiểm chứng độ chính xác của metrics Prometheus và Jaeger trong Tuần 2 trước khi kích hoạt vòng lặp tự động sửa lỗi thật.

---

## 4. Ký tên
*Trình bày bởi:* **Nhóm AI (AIO03)** - Task Force 1  
*Ngày trình:* **2026-07-08**
