# 04 — Eval Report (Nhóm AI / AIO03) — Cập nhật W2

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
| Unit Test: Model Gateway | Pass 100% tỷ lệ routing theo flagd | `test_model_router.py` |
| Unit Test: Shopping Copilot | Pass 100% các Guardrails (Prompt Injection, PII, Hallucination, Action Gate) | `test_copilot.py` |
| Unit Test: Recommendations | Pass 100% vector cosine search trên Mock pgvector | `test_recommendation.py` |

## 3. Số CHƯA đo được (blocked — không được trích như kết quả)
| Số | Chặn bởi |
|---|---|
| Bedrock latency P50/P95 thật (→ chốt timeout 3.0/2.0/5.0s) | AWS creds (`measure_bedrock_latency.py` sẵn) |
| Trước–sau error-rate với Bedrock thật | creds + EKS |
| Semantics 2 rule burn-rate/memory (syntax đã pass Prometheus 3.8.1) | data sống EKS |
| Task-success của Copilot | Đã pass Mock Test nội bộ, cần AWS creds chạy thật |
| Fidelity summary trên model thật vs `expected_summary_keywords` | creds |

## 4. Kế hoạch tiếp theo (Sau code freeze)
Chạy 3 script đo trên EKS; eval fidelity + QA 34 case trên Nova thật; FP-run 24h chốt min_count/cooldown; backtest EWMA α; CI chạy pytest + eval mỗi PR. Triển khai nhánh `feat/TF1-57-59-68` lên môi trường prod.
