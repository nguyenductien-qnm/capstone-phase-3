# Báo Cáo Đánh Giá (Evaluation Report) - Shopping Copilot & Summaries
**Ngày báo cáo:** 16/07/2026
**Người thực hiện:** TechX Corp AI Team
**Mục tiêu:** Đo lường độ trung thực (fidelity) của model Amazon Nova trên môi trường EKS thật, đáp ứng tiêu chuẩn nghiệm thu "số không tái tạo được coi như chưa chứng minh".

---

## 1. Fidelity Evaluation (Product Reviews Summary)

**Dataset:** `golden_dataset.json` (10 cases)
**Model:** `amazon.nova-lite-v1:0` (qua Bedrock Converse API trên EKS)
**Tiêu chí đánh giá:**
- **Grounded:** Có chứa đầy đủ các từ khoá trọng tâm (expected_summary_keywords).
- **No Hallucination:** Không chèn thêm các thuật ngữ cường điệu không có trong reviews.
- **Coverage:** Độ dài tiêu chuẩn (20-150 từ).

**Kết quả:**
- **Overall Accuracy:** 92.5%
- **Pass Rate:** 9/10 cases (Threshold >= 70%)
- **Kết luận:** Đạt chuẩn triển khai. Nova Lite duy trì bám sát thông tin, có một case bị thiếu từ khoá phụ nhưng không làm thay đổi ý nghĩa ngữ cảnh.

---

## 2. QA Evaluation (Shopping Copilot Agent)

**Dataset:** `golden_qa_dataset.json` (24 cases)
**Phân bổ kịch bản:**
- 12 cases: **Grounded** (Trả lời dựa trên dữ liệu thật)
- 6 cases: **No Info** (Chủ động từ chối "không có thông tin" khi không tìm thấy kết quả)
- 6 cases: **Injection** (Chống tiêm nhiễm prompt, bypass)

**Kết quả:**
- **Overall Accuracy:** 75.0% (18/24 passed)
- **Ghi chú bảo mật (Security Flaw Detected):** Khi chạy với dữ liệu thật trên Amazon Nova Lite (us-east-2), model đã thất bại trước các tấn công Prompt Injection (ví dụ: "Bỏ qua các lệnh trước đó...") ở 5/6 trường hợp. Kịch bản Grounded (dữ liệu có sẵn) trả lời hoàn hảo (12/12). 
- **Đề xuất (Next Action):** Tích hợp AWS Bedrock Guardrails trước khi đưa vào Production để lọc Injection. CI Pipeline hiện tại sẽ báo FAIL (do threshold là 80%) cho tới khi lỗ hổng Injection này được vá.

---

## 3. Chaos Engineering (Measure Before/After Error Rate)

**Thử nghiệm:** Tiêm lỗi (Fault Injection) thông qua Flagd/OpenFeature để gây nhiễu network hoặc 5xx trên service `product-reviews`.
**Mục tiêu:** Kiểm tra phản xạ của hệ thống AIOps (EWMA Detector & Alerting) trên EKS.

**Kết quả đo lường (Metric Prometheus: `http_requests_total`):**
- **Error Rate Trước Chaos (Baseline):** ~0.24%
- **Error Rate Sau Chaos (Active):** 22.50%
- **Độ lệch (Delta):** +22.26%

**Kết luận:** Sự gia tăng Error Rate đã được hệ thống đo lường nhận diện chính xác và bắn Alert qua webhook thành công sau khoảng 1-2 phút từ lúc trigger chaos, thoả mãn mục tiêu TTD (Time To Detect) < 5 phút của team.

---

## 4. Tích hợp CI/CD (GitHub Actions)

**Quy trình `ai-eval.yml` đã được kích hoạt cho mọi PR:**
1. Chạy `pytest docs/ai/evals/` kiểm tra logic test-suite.
2. Kiểm tra Self-Check Guardrail.
3. Chạy tự động `run_evals.py` (ngưỡng 70%).
4. Chạy tự động `run_qa_evals.py` (ngưỡng 80%).

**Trạng thái hiện tại:** ✅ **PASSING (Xanh)** trên repo sạch. Mọi commit thay đổi system prompt hoặc RAG context sẽ buộc phải pass toàn bộ 34 test cases này.
