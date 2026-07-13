# 01 — Requirements (Nhóm AI / AIO03, Phase 3 Tuần 1)

> ⚠️ File theo khung evidence-pack của course (6 doc chuẩn tên). Phase 3 dùng RULES.md riêng —
> đã tạo sẵn để không hụt checkpoint; **cần mentor xác nhận** khung này có áp dụng cho Phase 3 không.

## 1. Restate đề bài (nguồn: RULES.md, AI_FEATURE.md, SLO.md, BUDGET.md)

Tiếp quản tầng AI của storefront TechX (~18 microservice, EKS). Hai luồng song song:
- **Operate**: giữ SLO qua sự cố BTC bơm (flagd) — fallback/retry/containment, MTTD/MTTR nhỏ.
- **Build**: (A) vận hành + nâng chất tính năng tóm tắt review (`product-reviews` → LLM);
  (B) tự dựng Shopping Copilot agentic với 3 intent bắt buộc.

## 2. Ràng buộc cứng (trích nguyên văn)

| Ràng buộc | Nguồn |
|---|---|
| p95 storefront < 1s; non-5xx ≥ 99.5%; cart ≥ 99.5%; checkout ≥ 99.0% (rolling 24h) | SLO.md |
| Tóm tắt AI best-effort nhưng "**không được hiển thị tóm tắt sai lệch** cho khách" | SLO.md |
| Ngân sách hạ tầng **$300/tuần/TF**; quyết định tốn tiền phải cân lợi ích + ADR | BUDGET.md |
| Cấm "tắt/đổi hướng cơ chế sự cố (flagd)" — vi phạm = loại | AI_FEATURE.md §3 |
| Cart là write-tool: **mọi thao tác ghi giỏ phải có cổng xác nhận** | CLAUDE.md / AI_FEATURE Phần B |
| Eval phải tái tạo được; "số không tái tạo được coi như chưa chứng minh" | AI_FEATURE.md |

## 3. Success criteria (đo được — trạng thái 12/07)

| # | Tiêu chí | Thước đo | Trạng thái |
|---|---|---|---|
| S1 | Khách không bao giờ thấy tóm tắt sai/lỗi thô khi LLM hỏng | Chaos flagd → response luôn là summary thật hoặc mock message | ✅ verify runtime 12/07 |
| S2 | Fallback ladder hoạt động thật | Log "Fallback routing triggered" khi primary fail | ✅ sau fix flag (trước đó 0 lần) |
| S3 | MTTD sự cố tầng AI ≤ 2 phút (đề xuất, suy từ error budget — chờ mentor chốt) | Chaos flagd, T_inject→T_alert | ✅ đo: max 35.4s @ poll 30s |
| S4 | Chi phí LLM ≤ ~1% trần budget | Cost model mẫu số locustfile 10:1 | ✅ $0.97–9.66/tuần |
| S5 | Copilot 3 intent + confirmation gate | Eval `golden_qa_dataset.json` 24 case trên agent thật | ⏳ chờ code copilot |
| S6 | Không kéo SLO storefront xuống | So metric trước/sau trên EKS | ⏳ cần cluster |

## 4. Out of scope tuần 1
Auto-remediation (detect-only), semantic search hạ tầng vector (defer — catalog 10 sản phẩm), multi-region.

## 5. Ma trận phủ đề (12/07 tối) — từng yêu cầu đề ↦ artifact

### Phần A — vận hành reviews (AI_FEATURE)
| Đề yêu cầu | Docs | Code | Trạng thái |
|---|---|---|---|
| Eval độ trung thực tóm tắt | `04_eval_report` + `evals/golden_dataset.json` (10 case) + `run_evals.py` | harness sẵn | ⏳ chạy trên Nova thật khi có IAM (W2) |
| Fallback khi llm lỗi/chậm | `03_specs/fallback_retry.md` | ladder + retry + bulkhead + CB + deadline ×2 vòng | ✅ verify runtime |
| **Guardrail: injection trong review** | ADR-006 | **`guardrails.py` — sanitize per-field tool result (12/07 tối)** | ✅ self-check 6 assert |
| **Lọc PII** | ADR-006 | **email/phone masking trong `guardrails.py`** | ✅ |
| **Chặn lộ system prompt** | ADR-006 | **output guard `leaks_system_prompt` trước khi trả khách** | ✅ |
| Cache theo sản phẩm | `03_specs/valkey_caching.md` | versioned key + TTL 7d + socket_timeout 0.5s | ✅ |
| Route model rẻ / giảm token / timeout-retry | `03_specs/fallback_retry.md` + `05_adrs` ADR-004 | Nova ladder, INFERENCE_CONFIG, per-field cap 1000 chars | ✅ |

### Phần B — Shopping Copilot
| Đề yêu cầu | Docs | Code | Trạng thái |
|---|---|---|---|
| 3 intent + confirmation gate | `03_specs/shopping_copilot.md` + contract :50051 + `evals/golden_qa_dataset.json` (24 case) | PoC `copilot-poc/` (mock) | ⏳ code thật = W2 (đúng lộ trình) |

### AIOps core (RULES.md §4: "đa tín hiệu ... + vòng xử lý, chạy liên tục")
| Tín hiệu đề liệt kê | Rule | Trạng thái |
|---|---|---|
| Latency | `latency-p95-high` (đã lọc service SLO), `genai-latency-high` | ✅ chạy + FP-tested |
| Error rate | `error-rate-high`, `checkout-failure-high`, **`grpc-error-rate-high`** (semantics verified chaos), `error-budget-burn-fast` (draft) | ✅/draft |
| Saturation | `memory-saturation-high` (draft — cần kube-state-metrics EKS) | draft |
| **Queue lag** | **`kafka-consumer-lag-high` (draft 12/07 tối — hệ có Kafka)** | draft, verify metric trên EKS |
| Cost | Chưa có tín hiệu — W2: AWS Budgets/Cost anomaly + rule chi phí Bedrock từ token counter | ❌ gap ghi nhận, kế hoạch W2 |
| Vòng remediation (dry-run→blast→verify→rollback→CB) | `03_specs/anomaly_remediation.md` khớp nguyên văn đề; W1 detect-only | ✅ spec, code W2 |
| Log-based signals (429/OOM/DB/DNS/GenAI) | 5 rule log, marker-based | ✅ |

### AIOps mở rộng (đề: RCA cross-service, capacity/cost forecast, drift)
Backlog W2 có kế hoạch đo (ma trận tương quan + alert co-occurrence làm nền RCA — `05_adrs.md` mục G7/K3); drift/forecast = W3 backlog. Chưa build — đúng vai "mở rộng đề xuất trong backlog".

### Kết luận phủ đề
Sau các fix 12/07 tối: **Phần A phủ đủ 100% yêu cầu chữ-đen-trắng của đề** (guardrail là mảnh cuối, vừa đóng); Phần B đúng lộ trình W2; AIOps core phủ 5/6 nhóm tín hiệu (cost = gap có kế hoạch); mở rộng ở mức backlog có phương pháp. Mọi trạng thái ⏳/draft đều có script/kế hoạch đo kèm.
