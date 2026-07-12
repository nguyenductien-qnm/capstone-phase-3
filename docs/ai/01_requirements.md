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
