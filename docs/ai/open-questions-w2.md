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

---

## 4. VẬN HÀNH PRODUCTION: Rủi ro Log Pipeline & OpenSearch (AIOps)

### Q6 — Chỉ số Ingest Lag và Thời gian trễ Log dưới tải cao (Flash Sale)
* **Bối cảnh:** Dưới tải cực đại của đợt Flash Sale (200+ users), luồng logs đi qua: `Pod -> OTel Collector -> Kafka -> Log Forwarder -> OpenSearch` thường bị trễ (Ingest Lag tăng từ ~2s lên nhiều phút do nghẽn I/O). Bộ detector của nhóm quét logs định kỳ mỗi 30s sẽ bị sai lệch vì lúc quét log lỗi chưa kịp ghi vào OpenSearch index.
* **Câu hỏi:** Mentor đánh giá chỉ số **MTTD (Mean Time to Detect)** dựa trên thời điểm log thực tế sinh ra tại Pod (timestamp trong body log) hay dựa trên thời điểm log xuất hiện trên OpenSearch index? Nhóm có được phép tăng `lookback_window` (ví dụ từ 5 phút lên 10-15 phút) để bù đắp Ingest Lag mà không bị trừ điểm không?

### Q7 — Vấn đề "Log thưa" (Sparse Logs) gây lọt sự cố (False Negatives)
* **Bối cảnh:** Một số sự cố chí mạng như lỗi kết nối Database (`db-pool-exhaustion`) hay lỗi phân giải tên miền (`dns-resolution-error`) có thể chỉ xuất hiện 1 hoặc 2 dòng log thưa thớt trước khi Pod crash hoàn toàn. Nếu cấu hình mặc định yêu cầu `min_count=3` dòng lỗi trong cửa sổ 5 phút để kích hoạt alert, detector chắc chắn sẽ bị **lọt sự cố (False Negative)**.
* **Câu hỏi:** Mentor mong đợi các rule alert được cấu hình động dựa trên mức độ nghiêm trọng của log (ví dụ: lỗi DNS/OOM chỉ cần `min_count=1` là alert ngay, còn các lỗi HTTP 5xx bình thường mới cần `min_count >= 3`) hay bắt buộc áp dụng chung một benchmark cố định?

### Q8 — Quản lý vòng đời dữ liệu OpenSearch (Index Lifecycle Management - ILM) để giảm cost
* **Bối cảnh:** Theo **MANDATE-02**, ngân sách hạ tầng bị giới hạn cực kỳ ngặt nghèo ($300/tuần cho toàn cụm EKS). OpenSearch là dịch vụ cực kỳ ngốn tài nguyên (chiếm >30% RAM/CPU và EBS storage của cụm).
* **Câu hỏi chất vấn CDO & Mentor:** Nhóm AI có được phép cấu hình chính sách tự động xóa logs (Purge Policy/ILM) cũ sau 24h hoặc 48h để tiết kiệm chi phí EBS không? Có quy định bắt buộc lưu trữ logs tối thiểu bao nhiêu ngày cho mục đích audit của hệ thống không?

### Q9 — Rủi ro "Silent Failure" khi Log Pipeline bị đứt
* **Bối cảnh:** Nếu đường truyền từ OTel Collector lên OpenSearch bị đứt, detector sẽ hoàn toàn im lặng (vì không thấy dòng log lỗi nào ghi nhận), dẫn đến việc hệ thống sập nhưng không có cảnh báo nào được gửi đi.
* **Câu hỏi:** Mentor có yêu cầu thiết lập **Heartbeat / Rate-of-change Alert** (giám sát lưu lượng log sống liên tục, nếu đột ngột về 0 dòng/phút $\rightarrow$ cảnh báo đứt pipeline) để tính điểm Operational Excellence không?

---

## 5. NÂNG CAO AIE & AIOPS (Đua Top & Kiến thức chuyên sâu)

### Q10 — [AIE] Dynamic Model Routing dựa trên Độ phức tạp đầu vào
* **Bối cảnh:** Hiện tại Model Router của nhóm đang chạy A/B testing theo tỷ lệ phần trăm tĩnh thông qua OpenFeature/flagd. Tuy nhiên, để tối ưu hóa chi phí (MANDATE-02) và giảm độ trễ, nhóm có thể tự động chuyển hướng câu hỏi: câu hỏi ngắn, đơn giản sẽ định tuyến sang model siêu rẻ và nhanh (`amazon.nova-lite-v1:0` hoặc `nova-micro-v1:0`), còn các câu hỏi so sánh phức tạp hoặc có nguy cơ injection cao mới đưa lên model đắt (`amazon.nova-pro-v1:0`).
* **Câu hỏi:** Mentor có đánh giá cao phương án **Định tuyến mô hình động (Dynamic Complexity Routing)** này không, hay chỉ cần hoàn thành A/B testing theo tỷ lệ phần trăm là đủ?

### Q11 — [AIE] Thiết lập Hard Budget Gate ở mức Application
* **Bối cảnh:** Khi chạy production, rủi ro hacker spam API hoặc mã nguồn rơi vào vòng lặp LLM vô hạn (infinite agent loop) có thể làm cạn kiệt credit AWS rất nhanh. 
* **Câu hỏi:** Mentor có khuyến khích thiết lập một **Hard Budget Gate** ngay trong code server (nếu tổng chi phí token tích lũy của service trong 1 giờ vượt quá $5, hệ thống tự ngắt kết nối Bedrock và trả về degraded mode local) như một cơ chế phòng vệ tài chính chủ động không?

### Q12 — [AIOps] Multi-Window Burn-Rate Alerting chống báo động giả (False Positives)
* **Bối cảnh:** Nếu cấu hình alert dựa trên một ngưỡng lỗi tĩnh (ví dụ: HTTP 5xx > 2% trong 5 phút), hệ thống sẽ rất dễ bị kích hoạt cảnh báo giả khi có một vài request lỗi ngẫu nhiên trong thời gian ngắn (flakiness). Chuẩn công nghiệp SRE khuyến nghị dùng **MWMT (Multi-Window Multi-Threshold) Burn-Rate Alerting** (chỉ alert khi error budget bị tiêu thụ nhanh ở cả cửa sổ ngắn 5m và cửa sổ dài 1h).
* **Câu hỏi:** Mentor có chấm điểm cộng cho việc thiết lập cảnh báo chuẩn SRE Multi-Window Burn-rate trên Prometheus/Grafana không, hay chỉ cần các cảnh báo tĩnh đơn giản?

### Q13 — [AIOps] Khống chế vùng ảnh hưởng (Blast Radius Control) của Auto-Remediation
* **Bối cảnh:** Vòng lặp tự động khắc phục sự cố (Auto-remediation closed-loop) rất nguy hiểm khi gặp lỗi cascading (lỗi dây chuyền). Ví dụ, nếu database bị sập, auto-remediation có thể liên tục gửi lệnh restart pod $\rightarrow$ làm nghẽn EKS control plane và làm sập luôn các dịch vụ khỏe mạnh khác.
* **Câu hỏi:** Mentor có yêu cầu bắt buộc thiết lập cơ chế khống chế **Blast Radius** (ví dụ: tối đa chỉ restart 1 pod/lần, không restart nếu tỷ lệ lỗi toàn cụm > 50%, có nút tắt khẩn cấp Manual Bypass) trong kịch bản tự động khắc phục sự cố không?


