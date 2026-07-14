# Backlog ưu tiên - TF1 / AI Team (AIO03)

## 1. Đánh giá hệ thống hiện tại
Hệ thống hiện tại chạy trên K8s (EKS) với dịch vụ tóm tắt review (`product-reviews`) gọi trực tiếp API `llm` (mặc định là mock). Khi tích hợp API LLM thật (AWS Bedrock) và chạy dưới tải thực tế, hệ thống đối mặt với 3 rủi ro lớn nhất:
1. **Rủi ro vỡ trần chi phí Bedrock & Latency tăng cao (SLO p95 < 1s):** Việc gọi API LLM trực tiếp cho mỗi lượt duyệt sản phẩm mà không có bộ đệm (caching) sẽ làm phát sinh chi phí token khổng lồ và kéo dài thời gian phản hồi (p95 > 2s do độ trễ mạng API).
2. **Rủi ro gián đoạn dịch vụ khi API chính gặp lỗi (Reliability):** Nếu model chính (Amazon Nova Lite) bị lỗi hoặc chạm ngưỡng giới hạn băng thông (Rate Limit - 429), tính năng tóm tắt review sẽ sập hoàn toàn nếu không có cơ chế tự động chuyển đổi sang model dự phòng (Fallback Routing).
3. **Rủi ro an toàn thông tin (Security & Excess Agency):** Trợ lý Shopping Copilot tự ý thực hiện các hành động ghi phá hoại giỏ hàng của khách (hoặc tự ý checkout) do bị Prompt Injection qua review sản phẩm, hoặc tự động hóa hành động không có sự xác nhận của người dùng.

---

## 2. Backlog xếp hạng (AI Team - 12 Tasks)

| # | Mã Task JIRA | Tên Công Việc | Trụ | Rủi ro (khả năng×nghiêm trọng) | Tác động business | Cost Δ/tuần | Effort | Vì sao ưu tiên bậc này |
|---|---|---|---|---|---|---|---|---|
| 1 | **TF1-44** | Thiết lập Backlog ưu tiên & phân tích rủi ro (`00_backlog.md`) | Reliability / Governance | Cao × Cao (5×5 = 25) | Định hình toàn bộ phạm vi công việc và quản lý rủi ro | $0 | Thấp | Bắt buộc phải hoàn thiện làm kim chỉ nam để phân rã công việc cho 10 thành viên ngày đầu tiên. |
| 2 | **TF1-45** | Biên soạn Slide Pitching bảo vệ kế hoạch & Cost Model | Governance / Cost | Trung bình × Cao (3×4 = 12) | Bảo vệ ngân sách $300/tuần và cam kết SLO | $0 | Thấp | Cần thiết để chuẩn bị kịch bản phản biện, chứng minh ROI của giải pháp trước buổi bảo vệ thứ Sáu. |
| 3 | **TF1-51** | Audit hạ tầng Telemetry & Phân tích trace context | Observability | Cao × Cao (5×5 = 25) | Phát hiện đứt gãy trace và nợ kỹ thuật (INC-3) | $0 | Thấp | Phải làm sớm để đảm bảo các metric và trace GenAI thông suốt từ UI tới Collector/Jaeger. |
| 4 | **TF1-46** | Thiết kế Spec Valkey Caching & Model Fallback Routing | Cost / Reliability | Cao × Cao (4×4 = 16) | Giảm 90% credit burn Bedrock; bảo vệ SLO trễ < 1s | $0 | Thấp | Bản thiết kế kiến trúc kỹ thuật cốt lõi (ADR-001 + ADR-004/005, thay cho ADR-002 đã superseded) thống nhất biến ENV với nhóm CDO. |
| 5 | **TF1-47** | [Extend] Thiết kế Spec Shopping Copilot Agent & Hợp đồng CDO | Functional / Compliance | Trung bình × Cao (3×4 = 12) | Chốt hợp đồng tài nguyên K8s và đặc tả gRPC `:50051` | $0 | Trung bình | Ký phê duyệt hợp đồng tích hợp giúp CDO đóng gói hạ tầng EKS đồng bộ. |
| 6 | **TF1-48** | [Extend] Phát triển Shopping Copilot PoC (Streamlit) & Thiết lập Evals | Functional / Quality | Trung bình × Cao (3×4 = 12) | Demo chatbot với Confirmation Gate và script python tính accuracy | ~$5 | Trung bình | Xây dựng core logic chatbot an toàn (chống excessive agency) và tool evals golden dataset. Streamlit là thành phần xây mới, không có trong base repo. |
| 7 | **TF1-49** | Thiết kế Spec Golden Signal Anomaly Detection | Observability | Trung bình × Cao (3×4 = 12) | Thiết lập cơ chế phát hiện bất thường EWMA | $0 | Thấp | Cơ sở lý thuyết lọc nhiễu metrics trước khi tích hợp vào cảnh báo vận hành. |
| 8 | **TF1-52** | [Extend] Nghiên cứu & Xây dựng Log Clustering (Drain3) | Observability | Trung bình × Trung bình (3×3 = 9) | Tự động hóa gom cụm log lỗi GenAI (OOM, timeout) | $0 | Trung bình | Giải pháp AIOps xây thêm để nhanh chóng gom các sự cố cascading từ hàng triệu dòng log thô. |
| 9 | **TF1-50** | [Extend] Thiết kế Spec Auto-Remediation closed-loop & Safety | Reliability | Trung bình × Trung bình (3×3 = 9) | Thiết lập an toàn cho vòng tự khắc phục (Dry-run, Blast Radius) | $0 | Trung bình | Kịch bản tự động xử lý sự cố cấp công nghiệp (xây mới) trước khi code thực tế. |
| 10 | **TF1-53** | [Extend] Xây dựng script/tool cảnh báo vận hành | Observability | Thấp × Cao (2×4 = 8) | Gửi alert cảnh báo sớm về lỗi pool DB, OOM, DNS | $0 | Trung bình | Tích hợp script phát hiện lỗi và alert cứu hộ (công cụ xây thêm bên ngoài repo gốc). |
| 11 | **TF1-54** | Triển khai Option 1 giải quyết xung đột Eviction Policy Valkey | Reliability / Cost | Cao × Cao (4×4 = 16) | Đảm bảo an toàn giỏ hàng dưới ngân sách $300 | $0 | Trung bình | Chốt kiến trúc Option 1: volatile-lru + Bỏ Cart TTL + Cron GC dọn dẹp hàng đêm. |
| 12 | ~~**TF1-55**~~ → **TF1-58** | ~~Bổ sung rpc `AddReview` + `SubmitSummaryFeedback`~~ → Versioned cache key + nối Bedrock | Functional / Cost | Trung bình × Trung bình (3×3 = 9) | Làm mới cache đúng nguyên nhân (đổi model/prompt) | $0 | Trung bình | **TF1-55 đã huỷ.** Review là dữ liệu tĩnh seed qua `src/postgresql/init.sql`; không có UI viết review, không có nút feedback. Write-Around Invalidation và Thumbs Down sẽ invalidate cho sự kiện không bao giờ xảy ra. Thay bằng `reviews:summary:{product_id}:{model_ver}:{prompt_ver}` — xem ADR-001 và `03_specs/valkey_caching.md` §6. |
| 13 | **TF1-61** | Bổ sung Guardrails chống Prompt Injection, PII & Hallucination | Security / Trust | Cao × Cao (5×5 = 25) | Ngăn chặn LLM trả về thông tin rác, lộ system prompt (MANDATE-06) | $0 | Trung bình | Yêu cầu bắt buộc của Ban tổ chức (hạn 18/07). |
| 14 | **TF1-XX** | Graceful Shutdown cho Copilot & Product Reviews | Reliability | Trung bình × Cao (3×4 = 12) | Không rớt request khi deploy/restart (MANDATE-03) | $0 | Thấp | Yêu cầu bắt buộc của Ban tổ chức (hạn 16/07). Đã code xong trên nhánh `feat/TF1-57-59-68` (PR #61). |
| 15 | **TF1-YY** | Cấu hình Docker non-root cho Copilot | Security | Trung bình × Cao (3×4 = 12) | Chống rủi ro bảo mật leo thang đặc quyền (MANDATE-05) | $0 | Thấp | Yêu cầu bắt buộc của Ban tổ chức (hạn 17/07). Đã code xong trên nhánh `feat/TF1-57-59-68` (PR #61). |


---

## 3. Cố ý bỏ (lúc này) & Ghi chú Extend
1. **Tích hợp chính thức Copilot vào Next.js Frontend:** Chưa làm tuần này vì cần chốt file `.proto` và giao diện Envoy proxy với Platform Team trước để tránh xung đột code.
2. **Triển khai tự động hóa xử lý sự cố (Auto-remediation engine) chạy trên EKS:** Hoãn sang Tuần 3 vì cần kiểm chứng độ chính xác của metrics Prometheus và Jaeger trong Tuần 2 trước khi kích hoạt vòng lặp tự động sửa lỗi thật.
3. **Nối tool của Shopping Copilot vào gRPC thật (TF1-56):** Hoãn sang Tuần 2 để đợi CDO ổn định hạ tầng và gRPC endpoint trước khi tích hợp code Agent gọi API thật (hiện tại Copilot PoC đang chạy mock dữ liệu).


---

## 4. Hạng mục Đua Top (RULES.md line 66 — Mở rộng AIE)

Các tính năng nâng cao để cạnh tranh top, triển khai Tuần 2-3 (sau khi cốt lõi ổn định):

| # | Tên | Trụ | ADR | Spec | Mô tả | Cost Δ |
|---|---|---|---|---|---|---|
| 12 | **Semantic Search nâng cao** | Perf / Cost | ADR-008 | [semantic_search.md](03_specs/semantic_search.md) | Nâng cấp keyword→vector search bằng Titan Embeddings + pgvector | ~$0 |
| 13 | **AI Recommendations** | Perf / Cost | ADR-009 | [ai_recommendations.md](03_specs/ai_recommendations.md) | Nâng cấp random→embedding similarity recommendations | ~$0 |
| 14 | **Model Gateway & A/B Testing** | Perf / Cost / Rel | ADR-010 | [model_gateway_ab_testing.md](03_specs/model_gateway_ab_testing.md) | Flag-driven model routing + per-model metrics | ~$0 |

**Tất cả 3 hạng mục đều chi phí $0 bổ sung** vì:
- Reuse pgvector trên PostgreSQL hiện có (semantic search + recommendations)
- Reuse flagd đang chạy trên EKS (model gateway)
- Chỉ dùng Amazon native models (credit-eligible)

---

## 5. Ký tên & Phân công Nhân sự
*Trình bày bởi:* **Nhóm AI (AIO03)** - Task Force 1  
*Ngày trình:* **2026-07-08**

### 👥 Danh sách Phân công Tiểu ban (Sub-teams):

#### 🤖 Tiểu ban AIE (AI Engineering)
1. **Nguyễn Hữu Định (Định Nguyễn - AI Lead):** Phụ trách Quản trị rủi ro, Backlog, Slide Pitching, và code chính cho các task gán trên Jira (TF1-59, TF1-68, TF1-57).
2. **Nguyễn Công Thịnh (Thịnh Nguyễn Công):** Thiết kế Spec Valkey Cache, Fallback Routing, Deploy Bedrock (TF1-65, TF1-60, TF1-46).
3. **Phan Đức Tài:** Thiết kế Spec gRPC, Đo Bedrock latency (TF1-66, TF1-56, TF1-47).
4. **Lê Kim Dũng (03 lê kim dũng):** Phát triển Shopping Copilot PoC, Evals (TF1-48, TF1-64).

#### 📈 Tiểu ban AIOps (AI Operations)
5. **Thịnh Nguyễn Hưng:** Thiết kế Spec Anomaly Detection, Telemetry, Cost (TF1-49, TF1-75, TF1-73).
6. **Nguyễn Ngọc Giao:** Thiết kế Auto-Remediation, Verify EKS alert, Burn-rate alerting, Guardrails (TF1-50, TF1-79, TF1-69, TF1-61).
7. **Trần Mạnh Trường:** Audit Telemetry & Chốt log backend (TF1-76).
8. **Vinh Bui:** Xây dựng Log Clustering, Guardrails End-to-end (TF1-52, TF1-74, TF1-78).
9. **Thanh Pham Huu Tien:** Deploy aiops-detector, Verify rule draft (TF1-62, TF1-71, TF1-53).
10. **Thanh Hoang (Jax):** Backtest EWMA, Correlate stage RCA (TF1-80, TF1-70, TF1-51).

---

## 5. Ghi chú Phối hợp Hạ tầng (CDO Team Co-working)
* **Quyền hạn cụm (EKS IAM Access):** Nhóm AI ghi nhận và xác nhận cấu hình EKS Access Entries được CDO merge qua PR #7. Cấu hình này đã giải quyết triệt để lỗi 409 bằng cách lọc ID cluster creator, đồng thời cấp quyền ClusterAdmin đầy đủ cho danh sách admin của Task Force thông qua biến `eks_admin_user_arns`.
* **Tích hợp Caching:** Nhóm AI thống nhất tận dụng service `valkey-cart` cổng `6379` hiện có trên cụm EKS của CDO thay vì tự deploy cụm Valkey riêng lẻ, giúp tiết kiệm 100% chi phí tài nguyên phát sinh. **[CẬP NHẬT 14/07]** CDO đã migrate backend sang **ElastiCache Valkey managed** (`terraform/modules/elasticache/`); pod in-cluster tắt — xem ADR-003 addendum.

---

## Ghi chú đồng bộ 12/07/2026
- Mục 1.1: "gọi API LLM cho mỗi lượt duyệt" → đã đính chính từ 10/07: LLM chỉ chạy khi khách bấm *Ask AI* (tỉ lệ 10 view : 1 call theo locustfile — xem `pitch.md` Phần 2). Rủi ro cost vẫn đúng hướng nhưng mẫu số nhỏ hơn 10×.
- Trạng thái task đến 12/07: fallback/bulkhead/CB đã trong code + verify runtime (ADR-log phụ lục); TF1-54 (valkey) phát hiện lỗi chuỗi maxmemory/TTL — chờ quyết với CDO trước khi tiếp tục.

## Ghi chú đồng bộ 14/07/2026
- **Mandate mới từ BTC** (`_baseline-phase3/mandates/`): MANDATE-03 (bảo trì không downtime, hạn 16/07), MANDATE-05 (runtime hardening: non-root/pin image/limits + admission policy, hạn 17/07), **MANDATE-06 (AI trust & safety, hạn 18/07 — trụ AIE: mentor tự bắn injection + câu hỏi ngoài review, phải chặn/fallback; ADR ký tên; eval tái tạo được)**. MANDATE-04 chỉ áp TF4.
- **Trạng thái Jira (Cập nhật từ API Jira chiều 14/07):** 
  - **TF1-57:** Backlog (deferred theo W2 plan, description đã khớp title + reopen conditions).
  - **TF1-59:** In Progress - Implement ShoppingCopilotServiceServicer (đã code xong trên PR #47, chờ merge).
  - **TF1-61:** Done - Guardrail prompt-injection / PII / lộ system prompt (hiện tại = 0).
  - **TF1-68:** In Progress - Chốt ADR-003 valkey với CDO: maxmemory + tách instance.
  - **TF1-74:** Backlog - Copilot end-to-end: confirmation gate + guardrail + injection eval trên agent thật (Đây chính là task để xử lý dứt điểm MANDATE-06).
  - *Ngoài ra còn các task W2 mới từ TF1-62 đến TF1-80 cho AIOps và deploy EKS thật.*
- Do TF1-61 đã đánh Done trên Jira, phần Action Guardrails & Hallucination Eval (MANDATE-06) sẽ được log vào task **TF1-74**. Việc cấu hình Graceful Shutdown & Non-root (MANDATE-03, 05) được log dưới dạng task kỹ thuật bổ trợ (TF1-XX, YY).
- **TTL cart 60m đã khôi phục trong code** (`ValkeyCartStore.cs:188,216`) — giữ nguyên sau migration.
