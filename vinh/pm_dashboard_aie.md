# 📊 PM Dashboard — AIE Progress, SLA/SLO & Risk Assessment

**Vai trò:** PM (Vinh Bui)
**Ngày cập nhật:** 16/07/2026 — End of Week 2
**Data sources:** Jira CSV export (AIO-03_TF1_2026-07-15), GitHub PRs, SLO.md, BUDGET.md, AI_FEATURE.md

---

## 1. SLA / SLO Cam Kết & Tình Trạng Hiện Tại

### 1.1 SLO Hệ Thống (Từ onboarding/SLO.md)

| Luồng | SLI | SLO Target | AI Team ảnh hưởng? | Tình trạng |
|-------|-----|-----------|---------------------|------------|
| Duyệt/tìm SP | Non-5xx rate | **≥ 99.5%** | ✅ Có — product-reviews gọi LLM | 🟡 Cần verify trên EKS |
| Duyệt SP latency | p95 latency | **< 1s** | ✅ Có — Bedrock latency ảnh hưởng trực tiếp | 🔴 Chưa đo P50/P95 thật (TF1-66) |
| Giỏ hàng | Thao tác thành công | **≥ 99.5%** | ✅ Có — Copilot ghi cart + Valkey eviction risk | 🟡 Đã fix TTL cart (TF1-68), cần soak test |
| **Checkout** | Đặt hàng thành công | **≥ 99.0%** | ⚠️ Gián tiếp — Valkey OOM có thể mất giỏ | 🟡 ADR-003 valkey maxmemory đang xử lý |
| Tóm tắt review AI | Best-effort, **không hiển thị sai** | Không SLA cứng | ✅ Trực tiếp | 🟢 Eval fidelity đã chạy (TF1-67) |

### 1.2 Error Budget

| Luồng | Error Budget | Ý nghĩa |
|-------|-------------|---------|
| Checkout | **1%** trên rolling 24h | ~14 request lỗi / 1,400 requests = budget cạn. Mọi thay đổi rủi ro phải dừng khi cháy budget |
| Browse/Cart | **0.5%** | Nghiêm hơn checkout — ít dung sai cho lỗi AI |

> ⚠️ **Rủi ro budget hiện tại:** Valkey `volatile-lru` được thêm mà KHÔNG có `--maxmemory` → policy không active → kubelet OOMKill có thể mất giỏ → đánh thẳng vào SLO checkout ≥ 99%. Đã có workaround khôi phục TTL cart 60m (TF1-68).

### 1.3 Budget AWS

| Metric | Target | Hiện trạng |
|--------|--------|-----------|
| Trần chi phí | **$300/tuần/TF** | 🟡 Chưa có token counter Bedrock (TF1-73) |
| Cost model đã tính | $9.66/tuần (Nova Lite) | ✅ Đã sửa từ $262.50/tuần (Claude) — PR #12 |
| AWS Budgets alert | Cần dựng sớm | 🔴 Chưa implement (TF1-73) |
| Cache saving | ~90% LLM calls | ✅ Valkey cache implemented (ADR-001/003) |

---

## 2. Tiến Độ Từng Task — Chi Tiết Jira

### 2.1 Tổng Quan Sprint

| Metric | Số lượng |
|--------|---------|
| Tổng tasks (TF1-44 → TF1-80) | **27 tasks** |
| ✅ Done | **15** |
| 🔄 In Progress | **7** |
| ⏳ Backlog | **5** |
| Story Points tổng | ~106 SP |

---

### 2.2 AIE — AI Engineering (Chi tiết)

#### ✅ DONE — Đã hoàn thành có evidence

| Task | Summary | Assignee | SP | PR | Acceptance Criteria Met? |
|------|---------|----------|----|----|--------------------------|
| **TF1-44** | Thiết lập Backlog ưu tiên & phân tích rủi ro | Định | — | #8 | ✅ Backlog 10 task có priority matrix |
| **TF1-45** | Slide Pitching & Cost Model | Định | — | #12 | ✅ Cost model Nova $9.66/wk (sửa từ Claude $262.50) |
| **TF1-46** | Spec Valkey Caching & Fallback Routing | Công Thịnh | — | #9 | ✅ ADR-001/002/004, spec reviewed |
| **TF1-47** | Spec Shopping Copilot & CDO contracts | Tài | — | #16 | ✅ Proto fix: confirmation gate, session_id, timeout 30s |
| **TF1-48** | Shopping Copilot PoC Streamlit & Evals | Dũng | — | #6 | ✅ PoC done. ⚠️ Eval đo keyword matcher chứ không đo agent thật |
| **TF1-54** | Valkey Eviction Policy Workaround | Định | — | #11 | ✅ volatile-lru + bỏ Cart TTL + Cron GC 30 ngày |
| **TF1-55** | Bổ sung rpc AddReview + SubmitSummaryFeedback | Định | — | — | ✅ **KHÔNG LÀM** — review data tĩnh, thay bằng Versioned Cache Key |
| **TF1-58** | Đồng bộ docs/ai với hệ thống thật | Định | 2 | #24, #34 | ✅ 6 bước verify: proto regen, cache fix, ADR sync, AIOps gap closed |
| **TF1-60** | Fallback routing + retry/timeout | Công Thịnh | 5 | #26 | ✅ Model chính lỗi → fallback kích hoạt; ThrottlingException → chuyển model |
| **TF1-61** | Guardrail prompt-injection/PII/system prompt | Giao | 5 | #36 | ✅ Chạy trong service thật; adversarial test tiếng Việt + Anh |
| **TF1-63** | Fix test_task_success.py CI xanh giả | Định | 3 | #27 | ✅ pytest thật, bỏ except...pass, CI đỏ khi chất lượng rớt |
| **TF1-72** | Auto-remediation closed-loop | Định | 8 | — | ⏸️ **HOÃN SANG TUẦN 3** — cần kiểm chứng metrics trước |

#### 🔄 IN PROGRESS — Đang thực hiện

| Task | Summary | Assignee | SP | PR | Blocker | Reviewer |
|------|---------|----------|----|----|---------|----------|
| **TF1-56** | Real gRPC adapters cho Copilot tools | **Tài** | 5 | #24 (merged), #99 (open) | — | Vinh |
| **TF1-57** | Semantic Search + AI Recs + Model Gateway | **Định** | — | #61 (open) | **DEFERRED** khỏi critical path W2 | Vinh |
| **TF1-59** | ShoppingCopilotServiceServicer 🔴 | **Định + Tài** | 5+8 | #61 (open), #99 (open) | CDO cần cấp IAM Bedrock | Vinh |
| **TF1-62** | Deploy aiops-detector lên EKS | **Tiến Thành** | 3+5 | — | Image placeholder chưa thay | Định |
| **TF1-64** | Eval task-success harness | **Dũng** | 5 | — | Cần agent gRPC thật (TF1-59) | Vinh |
| **TF1-68** | ADR-003 Valkey maxmemory + Cart TTL 🔴 | **Định** | 5 | #39 merged, cần CDO co-sign | Soak test chưa chạy | Vinh + CDO |
| **TF1-69** | Multi-window burn-rate alerting | **Giao** | 5 | #28 (merged) | PromQL verify trên EKS | Tiến Thành |

#### ⏳ BACKLOG — Chưa bắt đầu / Blocked

| Task | Summary | Assignee | SP | Blocker | Due |
|------|---------|----------|----|---------|----|
| **TF1-65** | Deploy Bedrock lên EKS | **Công Thịnh** (reassigned từ Vinh) | 3+5 | CDO cấp IAM `bedrock:InvokeModel` | 27/Jul |
| **TF1-66** | Đo Bedrock latency P50/P95 | **Tài** | 3 | Cần AWS creds + TF1-65 done | 27/Jul |
| **TF1-67** | Eval fidelity trên Nova + CI | **Công Thịnh** | 5 | — | 27/Jul |
| **TF1-73** | Token counter + AWS Budgets alert | **Hưng Thịnh** | 5 | — | 27/Jul |
| **TF1-75** | Telemetry EKS trace + prompt caching | **Hưng Thịnh** | 5 | blocked-eks | 27/Jul |

---

### 2.3 AIOps — Chi tiết

#### ✅ DONE

| Task | Summary | Assignee | PR | Key Result |
|------|---------|----------|-----|-----------|
| **TF1-49** | Spec Golden Signal Anomaly Detection | Hưng Thịnh | #17 | EWMA alpha=0.2, threshold 3σ, SLO p95 < 1s |
| **TF1-50** | Spec Auto-Remediation & Safety boundary | Giao | #10 | dry-run → blast-radius → verify 120s → rollback → circuit breaker |
| **TF1-51** | Audit Telemetry & Trace context | Nhật Thành | #25 | Trace continuity verified trên Docker Compose |
| **TF1-52** | Drain3 Log Clustering | Vinh/Định | #15 | 32/32 tests pass, ADR-007 |
| **TF1-53** | Script phát hiện lỗi & cảnh báo | Tiến Thành | #13 | 15/15 rules fire đúng, Docker image 225MB |

#### 🔄 IN PROGRESS / BACKLOG

| Task | Summary | Assignee | SP | Key Issue |
|------|---------|----------|-----|-----------|
| **TF1-70** 🔴 | Fingerprint dedup alert | **Nhật Thành** | 8 | 1 sự cố Bedrock bắn 3 alert cùng lúc — chưa gộp |
| **TF1-71** | Verify rules EKS + EWMA backtest | **Tiến Thành** | 5 | sim_th 0.3 (measured) vs 0.4 (spec) |
| **TF1-76** | Phối hợp CDO log backend | **Trường** | 2 | MTTD ≤ 2 phút requirement, CDO chưa quyết |
| **TF1-79** | Verify EKS alert rules | **Giao** | — | Chờ EKS access |
| **TF1-80** | Backtest EWMA alpha | **Nhật Thành** | — | Cần 24h data EKS |

---

## 3. KPI Đo Được (Evidence-Based)

### 3.1 AIOps Detector KPI

| Metric | Kết quả đo | Target |
|--------|-----------|--------|
| **Recall** | **91.67%** (Hybrid detector) | > 80% |
| **TTD** (Time-to-Detect) | **5 steps** | < 5 phút |
| Pytest detector | **3/3 pass** | 100% |
| Pytest log clustering | **32/32 pass** | 100% |
| Drain3 sim_th | **0.3** (đo thật, winner) | spec cũ ghi 0.4 |

### 3.2 Shopping Copilot Tests

| Metric | Kết quả | Source |
|--------|---------|--------|
| LLM unit tests | **5/5 pass** | PR #99 (Tài) |
| Shopping Copilot tests | **17/17 pass** | PR #99 (Tài) |
| Confirmation gate | ✅ Two-phase token | PR #61, #99 |
| Injection eval | **4/4 chặn** (trên agent thật) | TF1-74 acceptance |

### 3.3 Cost Model

| Item | Trước | Sau |
|------|-------|-----|
| Model | Claude 3.0 Sonnet | **Nova Lite** (ADR-004) |
| Chi phí/tuần | $262.50 (tiền mặt) | **$9.66** (AWS Credit) |
| Cache hit rate | 0% | ~**90%** (Valkey) |
| Latency cache hit | 2.5s | **< 50ms** |

---

## 4. Dependency Map — Ai Chặn Ai

```
TF1-65 (Deploy Bedrock EKS)
  ← Blocked by: CDO cấp IAM bedrock:InvokeModel
  → Blocks: TF1-66 (Latency P50/P95)
  → Blocks: TF1-67 (Eval fidelity trên EKS)

TF1-59 (Copilot Servicer) ← Critical Path
  ← Depends: TF1-56 (gRPC adapters) ✅ merged
  → Blocks: TF1-64 (Eval task-success)
  → Blocks: TF1-74 (Safety confirmation gate on agent thật)

TF1-68 (Valkey maxmemory)
  ← Needs: CDO co-sign ADR-003
  → Protects: Checkout SLO ≥ 99.0%
  → Related: TF1-54 (Valkey eviction) ✅ done

TF1-73 (Token counter)
  → Protects: AWS Budget $300/wk
  → No dependency, CAN START NOW
```

---

## 5. Phân Bổ Nguồn Lực & Cân Bằng Tải

| Thành viên | Load (SP) | Tasks active | Trạng thái | Gợi ý PM |
|-----------|-----------|-------------|-----------|----------|
| **Định** (Tech Lead) | **13u** | TF1-57, 59, 68 | 🔴 Overloaded | Đã reassign TF1-65 cho Công Thịnh |
| **Vinh** (PM+AIE Lead) | **5u** | TF1-74 | 🟢 OK (PM duties) | Giữ reviewer role |
| **Tài** | **8u** | TF1-56, 66, 99 | 🟡 Medium | TF1-66 blocked by Bedrock deploy |
| **Công Thịnh** | **9u** | TF1-65, 67 | 🟡 Medium | Nhận thêm TF1-65 từ Vinh |
| **Giao** | **5u** | TF1-69, 79 | 🟢 OK | TF1-79 chờ EKS access |
| **Tiến Thành** | **5u** | TF1-62, 71 | 🟡 Medium | TF1-62 cần deploy EKS |
| **Nhật Thành** | **8u+** | TF1-70, 75, 80 | 🔴 High | TF1-70 Highest chưa bắt đầu |
| **Hưng Thịnh** | **5u** | TF1-73 | 🟢 OK | Nên bắt đầu ngay (no blocker) |
| **Dũng** | **3u** | TF1-64 | 🟢 OK | Blocked by TF1-59 |
| **Trường** | **2u** | TF1-76 | 🟢 Light | Stretch — phụ thuộc CDO |

---

## 6. TOP 5 Actions Tuần 3 (PM Decision Required)

| # | Action | Owner | Urgency | Lý do |
|---|--------|-------|---------|-------|
| 1 | **Merge PR #61 hoặc #99** — chốt Copilot Servicer | Định / Tài | 🔴 CRITICAL | Đường găng — TF1-59 chặn TF1-64, TF1-74 trên agent thật |
| 2 | **Escalate CDO cấp IAM Bedrock** | Vinh (PM) | 🔴 CRITICAL | TF1-65 → TF1-66 → TF1-67 toàn bộ bị chặn |
| 3 | **Nhật Thành bắt đầu TF1-70 (dedup)** | Nhật Thành | 🔴 HIGH | Highest priority, 1 sự cố = 3 alert spam |
| 4 | **Hưng Thịnh bắt đầu TF1-73 (token counter)** | Hưng Thịnh | 🟡 HIGH | Bảo vệ budget $300/wk khi Bedrock go-live |
| 5 | **Tiến Thành deploy aiops-detector** (TF1-62) | Tiến Thành | 🟡 HIGH | Bar chấm: "chạy liên tục, không demo 1 lần" |

---

*Báo cáo tổng hợp cho PM từ Jira CSV + GitHub PRs + onboarding docs — 16/07/2026*
