# Tiến Độ Chi Tiết — AI Team (TF1)

**Ngày cập nhật:** 16/07/2026 (Week 2 → Week 3)
**Project:** TechX Corp Storefront — Phase 3
**Repo:** [capstone-phase-3](https://github.com/nguyenductien-qnm/capstone-phase-3)

---

## 1. Tổng Quan AI Team

AI Team chịu trách nhiệm 2 mảng chính:
- **AIE (AI Engineering):** Vận hành + nâng cấp tính năng AI (tóm tắt review, Shopping Copilot agentic)
- **AIOps:** Xây dựng hệ thống phát hiện bất thường, alerting, log clustering tự động

### Thành viên

| Thành viên | GitHub | Role | Jira Tasks chính |
|-----------|--------|------|-------------------|
| **Định** | dinh144 | Tech Lead / AIE | TF1-57, TF1-59, TF1-68 |
| **Vinh** | nguyenductien-qnm | AIE Lead / PM | TF1-65, TF1-74 |
| **Tài** | PhanTai369 / thx2an | AIE | TF1-56, TF1-66 |
| **Công Thịnh** | Sylph-S | AIE | TF1-67 |
| **Giao** | Nguyenngocgiao | AIOps | TF1-61, TF1-69, TF1-79 |
| **Tiến Thành** | Cane-chaos / thx2an | AIOps Lead | TF1-62, TF1-71 |
| **Nhật Thành** | JaxTheDeveloper | AIOps | TF1-70, TF1-75, TF1-80 |
| **Hưng Thịnh** | Cane-chaos | AIOps | TF1-73 |
| **Dũng** | — | Support/Eval | TF1-64 |
| **Trường** | — | Support | TF1-76 |

---

## 2. Chi Tiết Từng Task & PR (Ai Làm Gì, Như Thế Nào)

### 📦 KHỐI AIE — AI Engineering

---

#### TF1-56 · Implement Real gRPC Adapters
- **Assignee:** Tài
- **Ưu tiên:** High
- **Trạng thái:** ✅ Done (Merged)
- **PRs:** [#28](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/28) (thx2an), [#6](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/6) (dinh144)
- **Mô tả chi tiết:**
  - Tích hợp gRPC client layer cho Shopping Copilot, kết nối thực tế tới các service: `product-catalog`, `product-reviews`, `cart`, `recommendation`, `currency`, `shipping`.
  - Trước đó Copilot chỉ dùng mock data cứng. Sau PR này, Copilot gọi được service thật qua gRPC.
  - Commit liên quan: `feat(copilot): integrate gRPC client layer + task-success eval [TF1-48, TF1-56]`
  - Đi kèm interactive Streamlit PoC demo (`demo_copilot_st.py`) để test thủ công.

---

#### TF1-57 · Semantic Search + AI Recommendations + Model Gateway
- **Assignee:** Định
- **Ưu tiên:** High
- **Trạng thái:** 🔄 In Progress (Open PR)
- **PR:** [#61](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/61) (dinh144) — branch `feat/TF1-57-59-68`
- **Mô tả chi tiết:**
  - Tích hợp AI Recommendations qua `pgvector` trong `recommendation_server.py`.
  - Semantic Search mapping sản phẩm vào `SYSTEM_PROMPT` (static catalog).
  - Cấu hình Valkey caching và Bedrock tool-use guardrails.
  - PR này gộp chung 3 task: TF1-57, TF1-59, TF1-68 (Copilot Agent + Guardrails + Model Gateway).
  - Trước đó đã có PR #12 merged (competitive research + ADR-008/009/010).

---

#### TF1-59 · Implement ShoppingCopilotServiceServicer
- **Assignee:** Định (Tech Lead) + Tài (hỗ trợ)
- **Ưu tiên:** 🔴 Highest — Đường găng
- **Trạng thái:** 🔄 In Progress (2 Open PRs song song)
- **PRs:**
  - [#61](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/61) (dinh144) — Copilot Server + Confirmation Gate + Guardrails
  - [#99](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/99) (PhanTai369 / Tài) — LLM Shopping Copilot Service
- **Mô tả chi tiết:**
  - **PR #61 (Định):** Implement Copilot Server gRPC servicer, wire vào Bedrock model, Confirmation Gate cho write actions, Guardrails (prompt injection, PII filtering).
  - **PR #99 (Tài):** Implement `ShoppingCopilotServiceServicer` hoàn chỉnh trên gRPC port `:50051`. Dùng LLM tool-calling (không dùng rule-based) cho 3 intent chính:
    1. `product-catalog search` — tìm kiếm sản phẩm bằng ngôn ngữ tự nhiên
    2. `product-reviews` — hỏi-đáp grounded từ review thật
    3. `cart` — thêm/sửa giỏ hàng (có confirmation gate)
  - Kết quả test local: **LLM tests 5/5 passed, Shopping Copilot tests 17/17 passed**.
  - Cart write luôn yêu cầu confirmation token. Checkout/delete cart bị chặn theo acceptance criteria.
  - Commit liên quan: `feat(copilot): real ShoppingCopilotService gRPC servicer (TF1-59)`, `feat: implement LLM shopping copilot service`

---

#### TF1-65 · Deploy Bedrock Lên EKS Thật
- **Assignee:** Vinh
- **Ưu tiên:** High
- **Trạng thái:** ✅ Merged (PR #35) + tiếp tục trên các commit mới
- **PR:** [#35](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/35) (dinh144) — branch `feat/aie-week2-hardening`
- **Mô tả chi tiết:**
  - Chuyển từ LLM mock sang Amazon Bedrock thật (Nova models).
  - Cấu hình `AWS_REGION` cho Bedrock (`ap-southeast-2` nơi model access active).
  - Fix Bedrock Converse API tool configuration và formatting errors.
  - Đăng ký `values-aio-llm.yaml` trong ArgoCD application.
  - PR bao phủ thêm: cart TTL restore (TF1-68), drain3 masked grid (TF1-71).
  - Commits chính: `feat(ai): switch product-reviews to Bedrock Nova and disable mock`, `feat(ai): configure AWS_REGION to ap-southeast-2`, `fix(ai): resolve Bedrock Converse API tool configuration`
  - Đo lường Bedrock latency timeout: `feat: measure bedrock latency timeouts` (commit `603087a`)

---

#### TF1-66 · Đo Bedrock Latency P50/P95
- **Assignee:** Tài
- **Ưu tiên:** High
- **Trạng thái:** ⏳ Blocked — Chờ Bedrock deploy ổn định
- **PR:** Chưa có PR riêng
- **Mô tả:** Cần Bedrock chạy ổn trên EKS trước (phụ thuộc TF1-65) mới đo được latency thực tế. Đã có commit `feat: measure bedrock latency timeouts` sơ bộ.

---

#### TF1-67 · Eval Fidelity Trên Nova + CI
- **Assignee:** Công Thịnh (Sylph-S)
- **Ưu tiên:** High
- **Trạng thái:** ✅ Done (Merged)
- **PR:** [#17](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/17) (Sylph-S)
- **Mô tả chi tiết:**
  - Xây dựng pipeline đánh giá độ trung thực (fidelity) của bản tóm tắt review khi chạy model Nova thật.
  - Golden dataset + eval scripts được commit vào `docs/ai/evals/`.
  - Commit: `feat(ai): add evals scripts and golden dataset`
  - Kiểm tra tóm tắt review có khớp nội dung review gốc không, đưa vào CI để mỗi lần thay đổi không làm rớt chất lượng.

---

#### TF1-68 · ADR-003 Valkey maxmemory + Cart TTL
- **Assignee:** Định
- **Ưu tiên:** High
- **Trạng thái:** ✅ Done (Merged)
- **PRs:** [#39](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/39) (Auzema), [#24](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/24) (dinh144)
- **Mô tả chi tiết:**
  - Cấu hình Valkey (Redis-compatible) với `maxmemory-policy volatile-lru` theo ADR-003.
  - Implement content-addressed cache invalidation cho review summaries (zero staleness).
  - Fix Valkey eviction policy, cart TTL restore.
  - Commits: `fix: align codebase with AI docs (Valkey eviction, flagd, cart TTL)`, `feat(cache): content-addressed invalidation for review summaries`
  - Cũng bao gồm ADR-003 ElastiCache addendum khi migrate sang AWS ElastiCache.

---

#### TF1-74 · Copilot Safety: Confirmation Gate + Guardrails
- **Assignee:** Vinh + Giao
- **Ưu tiên:** High
- **Trạng thái:** ✅ Phần lớn Done + 🔄 Open PR bổ sung
- **PRs:**
  - [#11](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/11) ✅ merged (dinh144) — guardrail valkey eviction + safety specs
  - [#36](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/36) 🔄 open (Nguyenngocgiao) — guardrail prompt module
- **Mô tả chi tiết:**
  - **Confirmation Gate:** Mọi hành động ghi (thêm/sửa cart) phải được người dùng xác nhận trước. Copilot không tự checkout/xóa giỏ.
  - **Guardrails đã implement:**
    - Chặn prompt injection nhét trong nội dung review
    - Lọc PII (thông tin cá nhân)
    - Chặn lộ system prompt
    - Tool allow-list (chỉ gọi tool trong phạm vi cho phép)
  - Commit: `feat(TF1-61): guardrail prompt-injection/PII/system-prompt (squashed)`, `feat(ai): add PII scrubbing and prompt injection guardrails`
  - PR #36 (Giao) bổ sung thêm guardrail prompt module trên branch `feat/TF1-61-guardrail-prompt`.
  - Đã implement Bulkhead + Circuit Breaker + Model Fallback Routing: `feat(ai): implement Bulkhead, Circuit Breaker, and Model Fallback Routing`

---

### 🔍 KHỐI AIOps — AI Operations

---

#### TF1-69 · Multi-window Burn-rate Alerting
- **Assignee:** Giao
- **Ưu tiên:** High
- **Trạng thái:** ✅ Done (Merged)
- **PR:** [#28](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/28) (thx2an)
- **Mô tả chi tiết:**
  - Cài đặt cảnh báo SLO burn-rate theo mô hình multi-window (short + long window).
  - Khi error rate tăng nhanh hơn ngưỡng cho phép (burn-rate > 1), hệ thống gửi cảnh báo.
  - Tích hợp với Prometheus/Grafana.

---

#### TF1-71 · Verify Rules + EWMA Backtest
- **Assignee:** Tiến Thành
- **Ưu tiên:** High
- **Trạng thái:** ✅ Done (Merged)
- **PR:** [#15](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/15) (Cane-chaos)
- **Mô tả chi tiết:**
  - Implement Drain3 log clustering cho GenAI anomaly detection.
  - Xây dựng EWMA (Exponential Weighted Moving Average) backtest cho alerting rules.
  - Kiểm chứng `drain3 sim_th = 0.3` (measured winner, không phải spec 0.4).
  - Commits: `feat(app/llm): [AIOps-W1-T4] add Drain3 log clustering`, `measure(aiops): masked drain3 grid confirms sim_th 0.3`

---

#### TF1-75 · Telemetry EKS: Trace Continuity
- **Assignee:** Nhật Thành (JaxTheDeveloper)
- **Ưu tiên:** High
- **Trạng thái:** ✅ Done (Merged)
- **PR:** [#25](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/25) (JaxTheDeveloper)
- **Mô tả chi tiết:**
  - Thiết lập observability pipeline xuyên suốt: OTel Collector → Prometheus/Jaeger/OpenSearch.
  - Đảm bảo trace ID được propagate liên tục từ frontend → product-reviews → LLM → cart.
  - Cho phép debug end-to-end khi có sự cố AI.

---

#### TF1-64 · Eval Task-Success Harness
- **Assignee:** Dũng
- **Ưu tiên:** High
- **Trạng thái:** 🔄 In Progress (có code nhưng chưa có PR riêng)
- **Mô tả chi tiết:**
  - Xây dựng framework đánh giá task-success cho Shopping Copilot: kiểm tra Copilot có giải quyết đúng intent hay không.
  - Commit liên quan: `feat(reliability): close valkey-cart SPOF + enable ElastiCache MultiAZ`, `feat(ai): replace circular keyword-matcher with real gRPC agent evaluation (TF1-64)`
  - Đã chuyển từ keyword-matcher sang real gRPC agent evaluation.
  - Cần tạo PR riêng và hoàn thiện bộ golden test cases.

---

#### TF1-62 · Deploy aiops-detector Lên EKS
- **Assignee:** Tiến Thành
- **Ưu tiên:** High
- **Trạng thái:** ❌ Chưa có PR
- **Mô tả:** AIOps detector (3-sigma anomaly detection, Drain3 log clustering) cần được đóng gói container và deploy lên EKS để chạy liên tục. Hiện chỉ có code local.

---

#### TF1-70 · Correlate: Fingerprint Dedup
- **Assignee:** Nhật Thành
- **Ưu tiên:** 🔴 Highest
- **Trạng thái:** ❌ Chưa bắt đầu
- **Mô tả:** Hệ thống gộp nhóm alert trùng lặp (dedup bằng fingerprint) để tránh spam. Chưa có code hay PR.

---

#### TF1-73 · Cost Bedrock: Token Counter
- **Assignee:** Hưng Thịnh
- **Ưu tiên:** High
- **Trạng thái:** ❌ Chưa có PR
- **Mô tả:** Cần implement hệ thống đếm token cho mỗi lời gọi Bedrock, đặt daily/weekly cap để kiểm soát budget ($300/tuần).

---

#### TF1-76 · Phối Hợp CDO Chốt Log Backend
- **Assignee:** Trường
- **Ưu tiên:** Medium (Stretch)
- **Trạng thái:** ❌ Chưa bắt đầu
- **Mô tả:** Phụ thuộc quyết định từ CDO team về log backend (OpenSearch vs Loki).

---

#### TF1-79 · Subtask: Verify EKS Alert Rules
- **Assignee:** Giao
- **Ưu tiên:** High
- **Trạng thái:** ⏳ Chờ EKS access
- **Mô tả:** Kiểm chứng các Prometheus alert rules trên EKS thật.

---

#### TF1-80 · Subtask: Backtest EWMA Alpha
- **Assignee:** Nhật Thành
- **Ưu tiên:** High
- **Trạng thái:** ⏳ Cần data EKS 24h
- **Mô tả:** Chạy backtest EWMA alpha tuning trên dữ liệu metric thật từ EKS (cần ít nhất 24h data).

---

## 3. Tổng Hợp PRs Liên Quan AI Team

### ✅ Merged PRs

| # | Title | Author | Nội dung chính |
|---|-------|--------|---------------|
| [#6](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/6) | Copilot Streamlit demo | dinh144 | PoC demo Shopping Copilot với Streamlit + Bedrock |
| [#11](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/11) | Valkey eviction + safety specs | dinh144 | Guardrail specs, ADR-005/006, Valkey eviction policy |
| [#12](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/12) | AIE competitive research | dinh144 | Semantic Search research, ADR-008/009/010 |
| [#15](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/15) | AIOps log clustering | Cane-chaos | Drain3 log clustering + EWMA backtest |
| [#17](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/17) | Eval fidelity Nova + CI | Sylph-S | Golden dataset + eval scripts + CI pipeline |
| [#24](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/24) | Valkey + proto stubs | dinh144 | Proto regeneration, Bedrock integration, Valkey caching, 3-sigma detector |
| [#25](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/25) | Telemetry trace continuity | JaxTheDeveloper | OTel → Prometheus/Jaeger observability pipeline |
| [#28](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/28) | gRPC adapters + burn-rate | thx2an | Real gRPC client layer + SLO burn-rate alerting |
| [#33](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/33) | AIE W1 verified fixes | dinh144 | Resilience fixes, measured AIOps rules, doc sync |
| [#34](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/34) | Evidence pack sync | dinh144 | Reconcile claims → verified values |
| [#35](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/35) | W2 hardening | dinh144 | Bedrock deploy, cart TTL, drain3, guardrails |
| [#39](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/39) | Valkey fix | Auzema | Valkey maxmemory ADR-003 |

### 🔄 Open PRs (Đang Review)

| # | Title | Author | Nội dung chính |
|---|-------|--------|---------------|
| [#36](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/36) | Guardrail prompt module | Nguyenngocgiao | TF1-61 guardrail prompt injection/PII/system-prompt |
| [#61](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/61) | TF1-57/59/68 Copilot + Gateway | dinh144 | Copilot Server, Model Gateway, Semantic Search, Guardrails |
| [#99](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/99) | LLM Shopping Copilot Service | PhanTai369 | Full gRPC Copilot servicer + 17 unit tests passed |

---

## 4. Tổng Kết Tiến Độ

### ✅ Đã Hoàn Thành (có evidence)
1. **gRPC Client Layer** — Copilot kết nối thật tới tất cả service
2. **Valkey Caching** — ADR-003, content-addressed invalidation, zero staleness
3. **Eval Fidelity** — Golden dataset + CI pipeline kiểm tra độ trung thực model
4. **Guardrails lõi** — Prompt injection, PII filter, system prompt protection
5. **Confirmation Gate** — Xác nhận trước mọi hành động ghi cart
6. **Drain3 Log Clustering** — AIOps phát hiện log bất thường tự động
7. **EWMA Backtest** — Đã đo và xác minh sim_th=0.3
8. **Burn-rate Alerting** — Multi-window SLO alerting
9. **Trace Continuity** — OTel observability pipeline end-to-end
10. **Bedrock Integration** — Chuyển từ mock sang Nova model thật
11. **Fallback Routing** — Sonnet → Haiku → Mock chain
12. **Bulkhead + Circuit Breaker** — Resilience patterns cho LLM calls

### 🔄 Đang Làm (có code, chờ merge)
1. **ShoppingCopilotServiceServicer** — 2 PRs đang mở (#61, #99), tests passed
2. **Semantic Search + Model Gateway** — PR #61
3. **Guardrail Prompt Module** — PR #36

### ❌ Còn Thiếu (chưa có code/PR)
1. **Bedrock Latency P50/P95** — Blocked bởi Bedrock deploy
2. **Alert Correlation & Fingerprint Dedup** — Chưa bắt đầu
3. **Token Counter / Cost Monitor** — Chưa bắt đầu
4. **Deploy aiops-detector lên EKS** — Chưa đóng gói container
5. **Log Backend coordination** — Phụ thuộc CDO
6. **Verify EKS Alert Rules** — Chờ EKS access
7. **Backtest EWMA Alpha** — Cần data 24h thật

---

*Báo cáo tổng hợp từ GitHub PRs API, Jira Week 2 Report, và Git commit history — 16/07/2026*
