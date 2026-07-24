# 📋 EVIDENCE PACK — TF1-94
**Mã Task:** `TF1-94` | **Assignee:** Lê Kim Dũng (`03 lê kim dũng`)
**Sub-team:** AIE / Task Force 1 | **Branch:** `docs/TF1-94-ai-eval-trust-safety`

---

## 1. Phương pháp & Đánh giá (Evaluation Methodology)
3 trục đánh giá chính theo yêu cầu MANDATE-06 + rubric AIE:
- **Fidelity & No Hallucination:** Kiểm tra độ bám sát dữ liệu thật (grounded) của model Amazon Nova Lite trên review summaries (ngưỡng ≥ 70%).
- **Security / Trust & Safety (MANDATE-06):** Red-team 24-25 kịch bản (Prompt Injection VN/EN, Jailbreak, PII, System Prompt Leakage).
- **Performance / Latency:** Đo P50/P90/P99 TTFT trước/sau Valkey Cache (P95 < 2s).

## 2. Datasets & Scripts
- `golden_dataset.json` (10 summary cases), `golden_qa_dataset.json` (24 QA + Guardrail cases).
- Execution Scripts: `run_evals.py`, `run_qa_evals.py`, `eval_mandate06_v6.py`, `measure_bedrock_latency.py`.

## 3. Kết quả Đo lường chính thức (Measured Outcomes)
- **Pass Rate chính thức:** **96.0% (24/25 cases passed)** trên môi trường EKS Live + ML-Guard.
- **Fidelity Accuracy:** 92.5% (9/10 cases passed).
- **Prompt Injection Defense:** 100% attack cases blocked.
- **Latency P50:** 614ms (đáp ứng tiêu chuẩn SLO).
- **Báo cáo chính thức:** `docs/ai/04_eval_report.md` & `docs/ai/MANDATE_06_EVIDENCE.md`.
- **Latency JSON:** `docs/ai/evals/bedrock_latency_results_2026-07-15.json`.

## 4. Audit Trail
| Trường | Giá trị |
|---|---|
| Change owner | Lê Kim Dũng (03 lê kim dũng) |
| Reviewer | Nguyễn Hữu Định (AI Lead) |
| Task ID | TF1-94 |
| Branch | `docs/TF1-94-ai-eval-trust-safety` |
