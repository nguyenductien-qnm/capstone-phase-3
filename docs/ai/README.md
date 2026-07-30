# docs/ai — bản đồ tài liệu Nhóm AI (AIO03)

Cập nhật 25/07/2026. Map theo khung evidence-pack của course (6 doc chuẩn) + tài liệu bổ trợ.
Quy ước: mọi con số trong docs phải là **số đo/tái tạo được** hoặc mang nhãn *assumption* —
xem "Sổ đăng ký con số" cuối `05_adrs.md`.

## Bộ doc chuẩn (evidence pack)

| Doc | File | Trạng thái |
|---|---|---|
| 01 Requirements | `01_requirements.md` | W1 — success criteria có trạng thái đo |
| 02 Solution Design | `02_solution_design.md` | W1 — kèm phương án đã loại |
| 03 AI Engine Spec | `03_specs/` (9 file, xem dưới) | Phân mảnh theo chủ đề — mỗi spec có "Phụ lục kiểm chứng 12/07" |
| 04 Eval Report | `04_eval_report.md` | Đã đo Eval cho cả Copilot và Reviews |
| 05 ADRs | `05_adrs.md` | ADR-001→015 + Phụ lục kiểm chứng + Sổ đăng ký con số. Mới nhất: ADR-014 (ML Guard cascade thay Bedrock Guardrails làm primary), ADR-015 (ml-guard v2 — async gRPC central policy service). Bedrock Guardrail flip **ON** 24/07 (`LLM_BEDROCK_GUARDRAIL=true`, layer-3). |
| 06 Contracts | `docs/shared/integration-contracts/` | product-reviews ✓; shopping-copilot (gRPC) ✓; recommendation ✓; ml-guard gRPC (`pb/ml_guard.proto`) |

## Specs (`03_specs/`) — index: `03_ai_engine_spec.md`
`fallback_retry` · `valkey_caching` · `semantic_search` (pgvector) · `shopping_copilot` (Đã có code thật) ·
`golden_signals_detection` · `log_clustering` · `anomaly_remediation` · `ai_recommendations` · `model_gateway_ab_testing`
> Đọc spec luôn kèm phụ lục cuối file — nhiều thông số thân bài đã được sửa bằng số đo.

## Bổ trợ
- `rubric_assessment.md` — **Tự đánh giá Rubric**: So sánh tài liệu AI với các tiêu chí chấm điểm của mentor.
- `system_audit_report.md` — **Báo cáo Audit Hệ thống & Gaps**: Đánh giá an toàn, regression và rò rỉ CI/CD.
- `ai-data-requirements-for-cdo.md` — **gửi CDO**: nhu cầu dữ liệu, thay thế OpenSearch, trả lời 4 câu hỏi 12/07
- `telemetry-audit.md` — TF1-51 + kết quả verify trace continuity 12/07
- `pitch.md` — slide + roleplay W1 + phụ lục cập nhật lập luận
- `00_backlog.md` — backlog TF1
- `evals/` — dataset (34 case) + 6 script đo/eval; chạy được từ repo sạch

## Code
- `techx-corp-platform/src/product-reviews/` — service chính (Bedrock Nova + resilience); guardrail gọi ml-guard qua shim `guardrails.py` → `pb/ml_guard_client.py`
- `techx-corp-platform/src/shopping-copilot/` — AI Agent gRPC (Bedrock Nova Pro, tool-calling, confirmation gate); guardrail chung ml-guard
- `techx-corp-platform/src/ml-guard/` — central trust-safety policy service (async gRPC, `pb/ml_guard.proto`: CheckInput/CheckOutput/SanitizeReviews; cascade regex → Presidio PII → NLI grounding → Nova judge). ADR-011/014/015
- `techx-corp-platform/src/recommendation/` — pgvector similarity (ADR-009)
- `copilot-poc/` — PoC Streamlit copilot (gom từ root 12/07)
- `aiops/detector/` + `aiops/remediation/` + `aiops/log_clustering/` — AIOps (detect → closed-loop remediation, ADR-012/013)
