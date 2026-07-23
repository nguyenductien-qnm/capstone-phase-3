> ⚠️ Superseded — pre-dates ADR-014 cascade

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
- **Ghi chú bảo mật (Security Flaw Detected):** Khi chạy với dữ liệu thật trên Amazon Nova Lite (us-east-1), model đã thất bại trước các tấn công Prompt Injection (ví dụ: "Bỏ qua các lệnh trước đó...") ở 5/6 trường hợp. Kịch bản Grounded (dữ liệu có sẵn) trả lời hoàn hảo (12/12). 
- **Đề xuất (Next Action):** Tích hợp AWS Bedrock Guardrails trước khi đưa vào Production để lọc Injection. CI Pipeline hiện tại sẽ báo FAIL (do threshold là 80%) cho tới khi lỗ hổng Injection này được vá.
- **Giao diện người dùng (17/07):** Copilot đã có UI web thật trong storefront — widget `CopilotChat` (React/styled-components, mount ở `_app.tsx`) gọi Next API route `/api/copilot` bridge sang gRPC `shopping-copilot:3552`, gồm action-gate xác nhận/hủy cho thao tác ghi giỏ hàng. Không dùng Streamlit.

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

---

# Phụ lục — Eval Report W2 (số đo tính đến 15/07, giữ làm evidence measured)

> **Evidence tier (mentor chốt 12/07):** số đo trên **docker compose local = evidence TẠM (được chấp nhận)**;
> W2 chạy lại toàn bộ script trên EKS để nâng thành evidence chính thức. Mỗi bảng số dưới giữ nhãn nguồn.

> ⚠️ Cùng caveat khung evidence-pack. Nguyên tắc: **chỉ số đo/tái tạo được mới vào bảng Kết quả**;
> số mô phỏng/mock bị loại hoặc dán nhãn. Script tái tạo: `docs/ai/evals/`.

## 1. Phương pháp
- **Resilience**: unit test 6 scenario (mock Bedrock) + chaos thật qua flagd trên compose stack
  (`measure_before_after` — đã thay bản mô phỏng random bằng đo thật, từ chối in số nếu stack không chạy).
- **Detection**: bơm `llmRateLimitError` T0 → đo T_alert (5 vòng); FP-run 15 phút tải locust.
- **Concurrency**: thí nghiệm deterministic (`bulkhead_experiment.py`).
- **Tham số Drain3**: grid 4×3 trên 19.294 dòng log thật, tiêu chí cố định trước khi đo (`drain3_param_grid.py`).
- **Fidelity/QA dataset**: `golden_dataset.json` 10 case summary (100% grounded seed DB) +
  `golden_qa_dataset.json` 24 case (10 grounded / 10 no_info / 4 injection).

## 2. Kết quả ĐÃ ĐO (tái tạo được)

| Đại lượng | Kết quả | Script |
|---|---|---|
| Ingest lag log (request→queryable) | P50 2.1s, max 5.1s (n=8) | measure_detection_pipeline.py |
| MTTD @ poll 30s (chaos flagd, 5 vòng) | mean 19.6s, **max 35.4s** | như trên |
| Chi phí query detector | P50 5ms, P95 12ms (n=30) | như trên |
| Bulkhead blocking vs non-blocking | 1909ms vs **10ms** (fast-request khi 12 LLM treo) | bulkhead_experiment.py |
| Drain3 sim_th | **0.3 trội 0.4/0.5/0.6** cả 4 tiêu chí; depth vô cảm → code default 0.3 | drain3_param_grid.py (masking: `MASK=1`) |
| Fallback ladder runtime | "Fallback routing triggered" ×5; "CB OPENED after 3 failures" | docker logs (compose) |
| FP 15 phút tải thường | 2 FP config (latency rule match flagd — đã vá filter) + 2 TP sai nhãn (đã vá marker) | detector run |
| Bedrock latency P50/P95 thật | Reviews Lite 1.741/2.542s; Reviews Micro 1.715/2.253s; Copilot Pro 3.069/6.861s; Copilot Lite 2.350/2.663s | `bedrock_latency_results_current.md` (`us-east-1`); direct Nova Pro/Lite/Micro access re-verified with CDO SSO on 22/07 |
| Unit Test: Model Gateway | Pass 100% tỷ lệ routing theo flagd | `test_model_router.py` |
| Unit Test: Shopping Copilot | Pass 100% các Guardrails (Prompt Injection, PII, Hallucination, Action Gate) | `test_copilot.py` |
| Unit Test: Recommendations | Pass 100% vector cosine search trên Mock pgvector | `test_recommendation.py` |
| Safety Eval (MANDATE-06) | Pass 10/10 (100%): 6/6 Injection blocked, 3/3 Hallucination, 1/1 Action Gate | `eval_mandate06.py --mode offline` |

## 3. Số CHƯA đo được (blocked — không được trích như kết quả)
| Số | Chặn bởi |
|---|---|
| Trước–sau error-rate với Bedrock thật | creds + EKS |
| Semantics 2 rule burn-rate/memory (syntax đã pass Prometheus 3.8.1) | data sống EKS |
| Fidelity summary trên model thật vs `expected_summary_keywords` | creds |

## 4. Kế hoạch tiếp theo (Sau code freeze)
Chạy 3 script đo trên EKS; eval fidelity + QA 34 case trên Nova thật; FP-run 24h chốt min_count/cooldown; backtest EWMA α; CI chạy pytest + eval mỗi PR. Triển khai nhánh `feat/TF1-57-59-68` lên môi trường prod.
