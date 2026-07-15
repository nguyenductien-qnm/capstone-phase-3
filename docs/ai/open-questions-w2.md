# Câu hỏi chất vấn Mentor — Tuần 2 (15/07/2026)

Tài liệu tổng hợp các câu hỏi mở, giả định vận hành hoặc điểm kỹ thuật chưa chốt liên quan đến **MANDATE-06** (AI Trust & Safety), **MANDATE-02** (Tải Flash Sale & SLO), và **MANDATE-05** (Runtime Hardening) cần Mentor xác nhận để định hình tiêu chí đánh giá cuối cùng.

---

## 1. MANDATE-06: Đánh giá Độ tin cậy & An toàn AI (AI Trust & Safety)

### Q1 — Môi trường và cách thức Mentor thực hiện bắn phá (Adversarial Testing)
* **Bối cảnh:** Nhóm AI đã phát triển bộ offline eval (`eval_mandate06.py --mode offline`) chạy thành công 100% (6/6 injection, 3/3 hallucination, 1/1 action gate). Tuy nhiên, để chạy thật online trên Kubernetes (EKS), pod của `shopping-copilot` cần CDO thiết lập xong phân quyền IAM Role (IRSA) để gọi Bedrock API.
* **Câu hỏi:** Khi Mentor trực tiếp kiểm thử (bắn thử prompt-injection hoặc hỏi câu ngoài lề), Mentor sẽ:
  - **(a)** Tương tác trực tiếp trên giao diện Live Storefront web (đòi hỏi luồng frontend-gateway đã thông suốt trên EKS)?
  - **(b)** Chấp nhận kiểm thử thông qua API gRPC được port-forward từ pod (`localhost:50051`)?
  - **(c)** Chấp nhận kết quả báo cáo chạy offline eval từ script của nhóm?

### Q2 — Chỉ số SLO p95 Latency của gRPC API AI Agent
* **Bối cảnh:** Tài liệu `onboarding/SLO.md` yêu cầu *storefront p95 < 1s*. Tuy nhiên, do đặc thù gọi LLM Bedrock (Amazon Nova Pro) xử lý hội thoại mất trung bình **1.5s - 2.5s** (khi cache miss), bản thân các gRPC method của AI (`ChatWithCopilot` và `AskProductAIAssistant`) không thể đáp ứng p95 < 1s.
* **Giả định của nhóm:** Do giao diện AI (reviews Q&A và chatbot Copilot) được thiết kế bất đồng bộ ở client và nằm ngoài luồng render nóng (critical render path) của trang sản phẩm, chỉ số latency của các gRPC AI này **không** bị tính vào SLO storefront p95 < 1s. 
* **Câu hỏi:** Mentor có xác nhận giả định này không? Hay có một chỉ số SLO p95 latency riêng biệt dành cho các API AI (ví dụ: p95 < 3s)?

### Q3 — Bộ dữ liệu đánh giá độ trung thực (Fidelity Benchmark)
* **Bối cảnh:** Nhóm tự xây dựng golden dataset gồm 10 cases để eval tính chính xác của bản tóm tắt reviews và 24 cases cho Copilot.
* **Câu hỏi:** Khi chấm điểm, Mentor sẽ chỉ test ngẫu nhiên bằng tay vài câu (Manual Testing) hay sẽ chạy một bộ dataset ẩn (Black-box benchmarking) để càn quét và chấm điểm tự động (Auto-eval)?

---

## 2. MANDATE-02: Tải Flash Sale & Hiệu năng AI (Performance vs Budget)

### Q4 — Yêu cầu về degraded mode khi LLM bị nghẽn (Throttle 429) dưới tải cao
* **Bối cảnh:** Trong bài test flash sale (200 user đồng thời), API Bedrock có thể bị AWS rate limit (429) hoặc bị quá tải. Thiết kế của nhóm đã có cơ chế tự động chuyển sang degraded mode (trả về tóm tắt reviews mặc định/tĩnh có sẵn thay vì crash trang).
* **Câu hỏi:** Mentor có yêu cầu ghi nhận/alert cụ thể khi hệ thống rơi vào trạng thái degraded (ví dụ: đếm số lần degraded, tự động alert Slack/logs thông qua AIOps) để tính điểm Auditability và Operational Excellence không?

---

## 3. MANDATE-05: Runtime Hardening (Non-Root & Resource Limits)

### Q5 — Enforce Policy-as-Code ở mức Admission Control
* **Bối cảnh:** MANDATE-05 yêu cầu chặn các manifest vi phạm (chạy root, tag latest, thiếu resources limit) bằng cơ chế tự động (Admission Controller). Nhóm CDO đang thiết lập Gatekeeper/Kyverno.
* **Câu hỏi:** Mentor mong đợi cơ chế tự động này hoạt động ở cấp độ nào:
  - **(a)** Chặn ngay lập tức ở CI/CD pipeline (ví dụ: `conftest` quét helm chart trước khi apply)?
  - **(b)** Chặn ở mức Cluster Admission Webhook (Kyverno từ chối deploy thật và hiển thị thông báo lỗi kubectl)?
