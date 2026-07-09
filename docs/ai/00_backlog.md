# Backlog ưu tiên - TF1 / AI Team (AIO03)

## 1. Đánh giá hệ thống hiện tại
Hệ thống hiện tại chạy trên K8s (EKS) với dịch vụ tóm tắt review (`product-reviews`) gọi trực tiếp API `llm` (mặc định là mock). Khi tích hợp API LLM thật (AWS Bedrock) và chạy dưới tải thực tế, hệ thống đối mặt với 3 rủi ro lớn nhất:
1. **Rủi ro vỡ trần chi phí Bedrock & Latency tăng cao (SLO p95 < 1s):** Việc gọi API LLM trực tiếp cho mỗi lượt duyệt sản phẩm mà không có bộ đệm (caching) sẽ làm phát sinh chi phí token khổng lồ và kéo dài thời gian phản hồi (p95 > 2s do độ trễ mạng API).
2. **Rủi ro gián đoạn dịch vụ khi API chính gặp lỗi (Reliability):** Nếu model chính (Claude 3.0 Sonnet) bị lỗi hoặc chạm ngưỡng giới hạn băng thông (Rate Limit - 429), tính năng tóm tắt review sẽ sập hoàn toàn nếu không có cơ chế tự động chuyển đổi sang model dự phòng (Fallback Routing).
3. **Rủi ro an toàn thông tin (Security & Excess Agency):** Trợ lý Shopping Copilot tự ý thực hiện các hành động ghi phá hoại giỏ hàng của khách (hoặc tự ý checkout) do bị Prompt Injection qua review sản phẩm, hoặc tự động hóa hành động không có sự xác nhận của người dùng.

---

## 2. Backlog xếp hạng (AI Team - 10 Tasks)

| # | Mã Task JIRA | Tên Công Việc | Trụ | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Cost Δ/tuần | Effort | Vì sao ưu tiên bậc này |
|---|---|---|---|---|---|---|---|---|
| 1 | **TF1-44** | Thiết lập Backlog ưu tiên & phân tích rủi ro (`00_backlog.md`) | Reliability / Governance | Cao × Cao (5×5 = 25) | Định hình toàn bộ phạm vi công việc và quản lý rủi ro | $0 | Thấp | Bắt buộc phải hoàn thiện làm kim chỉ nam để phân rã công việc cho 10 thành viên ngày đầu tiên. |
| 2 | **TF1-45** | Biên soạn Slide Pitching bảo vệ kế hoạch & Cost Model | Governance / Cost | Trung bình × Cao (3×4 = 12) | Bảo vệ ngân sách $300/tuần và cam kết SLO | $0 | Thấp | Cần thiết để chuẩn bị kịch bản phản biện, chứng minh ROI của giải pháp trước buổi bảo vệ thứ Sáu. |
| 3 | **TF1-51** | Audit hạ tầng Telemetry & Phân tích trace context | Observability | Cao × Cao (5×5 = 25) | Phát hiện đứt gãy trace và nợ kỹ thuật (INC-3) | $0 | Thấp | Phải làm sớm để đảm bảo các metric và trace GenAI thông suốt từ UI tới Collector/Jaeger. |
| 4 | **TF1-46** | Thiết kế Spec Valkey Caching & Model Fallback Routing | Cost / Reliability | Cao × Cao (4×4 = 16) | Giảm 90% chi phí token Bedrock; bảo vệ SLO trễ < 1s | $0 | Thấp | Bản thiết kế kiến trúc kỹ thuật cốt lõi (ADR-001/002) thống nhất biến ENV với nhóm CDO. |
| 5 | **TF1-47** | Thiết kế Spec Shopping Copilot Agent & Hợp đồng CDO | Functional / Compliance | Trung bình × Cao (3×4 = 12) | Chốt hợp đồng tài nguyên K8s và đặc tả gRPC `:50051` | $0 | Trung bình | Ký phê duyệt hợp đồng tích hợp giúp CDO đóng gói hạ tầng EKS đồng bộ. |
| 6 | **TF1-48** | Phát triển Shopping Copilot PoC (Streamlit) & Thiết lập Evals | Functional / Quality | Trung bình × Cao (3×4 = 12) | Demo chatbot với Confirmation Gate và script python tính accuracy | ~$5 | Trung bình | Xây dựng core logic chatbot an toàn (chống excessive agency) và tool evals golden dataset. |
| 7 | **TF1-49** | Thiết kế Spec Golden Signal Anomaly Detection | Observability | Trung bình × Cao (3×4 = 12) | Thiết lập cơ chế phát hiện bất thường EWMA | $0 | Thấp | Cơ sở lý thuyết lọc nhiễu metrics trước khi tích hợp vào cảnh báo vận hành. |
| 8 | **TF1-52** | Nghiên cứu & Xây dựng Log Clustering sử dụng Drain3 | Observability | Trung bình × Trung bình (3×3 = 9) | Tự động hóa gom cụm log lỗi GenAI (OOM, timeout) | $0 | Trung bình | Giải pháp AIOps để nhanh chóng gom các sự cố cascading từ hàng triệu dòng log thô. |
| 9 | **TF1-50** | Thiết kế Spec Auto-Remediation closed-loop & Safety boundary | Reliability | Trung bình × Trung bình (3×3 = 9) | Thiết lập an toàn cho vòng tự khắc phục (Dry-run, Blast Radius, CB) | $0 | Trung bình | Định hình kịch bản tự động xử lý sự cố an toàn cấp công nghiệp trước khi code ở tuần sau. |
| 10 | **TF1-53** | Xây dựng script/tool phát hiện lỗi và cảnh báo vận hành | Observability | Thấp × Cao (2×4 = 8) | Gửi alert cảnh báo sớm về lỗi pool DB, OOM, DNS | $0 | Trung bình | Tích hợp các script kiểm tra tự động phát hiện lỗi và gửi alert cứu hộ tức thời cho on-call. |
| 11 | **TF1-54** | Triển khai Option 1 giải quyết xung đột Eviction Policy Valkey | Reliability / Cost | Cao × Cao (4×4 = 16) | Đảm bảo an toàn giỏ hàng dưới ngân sách $300 | $0 | Trung bình | Chốt kiến trúc Option 1: volatile-lru + Bỏ Cart TTL + Cron GC dọn dẹp hàng đêm. |


---

## 3. Cố ý bỏ (lúc này)
1. **Tích hợp chính thức Copilot vào Next.js Frontend:** Chưa làm tuần này vì cần chốt file `.proto` và giao diện Envoy proxy với Platform Team trước để tránh xung đột code.
2. **Triển khai tự động hóa xử lý sự cố (Auto-remediation engine) chạy trên EKS:** Hoãn sang Tuần 3 vì cần kiểm chứng độ chính xác của metrics Prometheus và Jaeger trong Tuần 2 trước khi kích hoạt vòng lặp tự động sửa lỗi thật.

---

## 4. Ký tên
*Trình bày bởi:* **Nhóm AI (AIO03)** - Task Force 1  
*Ngày trình:* **2026-07-08**
