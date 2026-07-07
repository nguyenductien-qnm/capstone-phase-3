# Thể lệ Phase 3 - TechX Corp Service Takeover

## 1. Bối cảnh & mục tiêu
Phase 3 mô phỏng đúng việc một kỹ sư làm khi vào công ty: **tiếp quản một sản phẩm AI đang chạy production**, vận hành nó, cải tiến nó, và bảo vệ được mọi quyết định của mình.

Khác với Phase 2 (nhận đề bài rồi build), Phase 3 **không phát brief**. Các bạn nhận một hệ thống đang sống - có khách hàng, có SLA, có ngân sách, có nợ kỹ thuật, có sự cố - và phải tự tìm ra việc cần làm, tự ưu tiên, rồi delivery dưới ràng buộc thật.

Mục tiêu cá nhân: chứng minh bạn có thể **own một service** - không chỉ code, mà là judgment, vận hành, đánh đổi business, và giao tiếp.

## 2. Cấu trúc
Ba tầng, mỗi tầng một vai trò:

| Tầng | Đơn vị | Vai trò |
|---|---|---|
| Vận hành / thi đấu | **4 Task Force (TF)** | Mỗi TF cùng vận hành 1 service trên 1 account riêng |
| Kèm cặp | **13 nhóm** (9 CDO + 4 AIO) | Mỗi nhóm **1 mentor kèm cặp**, theo sát cả kỳ |
| Tổng hợp / quyết định | **Ban tổ chức** | Theo dõi, tổng hợp, quyết định kết quả |

**Chia TF** (mỗi TF = 1 nhóm AIO + 2-3 nhóm CDO):

| TF | AIO | CDO |
|---|---|---|
| TF1 | AIO03 | CDO05, CDO09 |
| TF2 | AIO04 | CDO03, CDO06 |
| TF3 | AIO02 | CDO01, CDO02 |
| TF4 | AIO01 | CDO04, CDO07, CDO08 |

Mỗi TF vận hành như một mini product org, chạy song song 2 luồng: **Operate** (giữ đèn sáng - on-call, incident, SLO, fix điểm yếu) và **Build** (ship cải tiến / feature mới trên product). Build gì là do các bạn tự đánh giá hệ thống rồi đề xuất trong backlog - không có checklist phát sẵn. Nhóm CDO nghiêng về platform/hạ tầng (autoscaling, observability, security, cost, reliability qua Helm/IaC/config), nhóm AIO nghiêng về tầng AI theo hai hướng: **dùng AI để vận hành hệ thống** (AIOps) và **làm AI trong sản phẩm** (AIE).

Trong 1 TF: các nhóm CDO lo hạ tầng/platform, nhóm AIO lo tầng AI - cùng giữ cho một service khỏe. Đây là làm việc cross-functional thật, và cũng là một tiêu chí được đánh giá.

## 3. Sân chơi
Ban tổ chức cấp **source code + một image seed** của một sản phẩm AI thương mại TechX Corp. Mỗi TF **tự build image → đẩy lên ECR của account mình → deploy → vận hành**. Việc dựng và đưa hệ thống lên chạy chính là bước tiếp quản đầu tiên. Đây là hệ thống hoàn chỉnh: nhiều microservice, Kubernetes, hàng đợi, cơ sở dữ liệu, một tính năng AI, và đầy đủ observability (metrics, logs, traces, dashboard).

Hệ thống này **không hoàn hảo** - nó có sẵn những điểm chưa tối ưu về chi phí, bảo mật, độ tin cậy, khả năng mở rộng, khả năng truy vết. Nhiệm vụ của các bạn là tìm ra, ưu tiên, và xử lý chúng như một đội vận hành thật.

## 4. Năm trụ + trụ AI
Công việc CDO xoay quanh **5 trụ**:

1. **Security** - bảo vệ hệ thống, dữ liệu và danh tính: hardening, least-privilege, phát hiện và chặn xâm nhập.
2. **Reliability** - giữ lời hứa SLA qua mọi sự cố: chịu lỗi, tự phục hồi, giữ SLO.
3. **Performance Efficiency** - đúng tài nguyên cho đúng tải: chịu tải, scale, multi-tenant, tối ưu độ trễ.
4. **Cost Optimization** - mỗi đô chi ra phải đáng: right-size, spot, cắt lãng phí trong khi giữ SLA.
5. **Auditability** - truy được ai làm gì và khi nào: K8s audit, CloudTrail, change management, log integrity.

Xuyên suốt cả 5 trụ là **Operational Excellence** - vận hành hướng tới kết quả kinh doanh. Đây là xương sống của Phase 3: luồng Operate hằng ngày của bạn (on-call, ADR, Ops Review, quy mọi quyết định về khách và doanh thu). Cả TF cùng thực hành, không nhóm nào "sở hữu" riêng.

Nhóm AIO giữ **trụ AI** riêng (nằm ngoài 5 trụ CDO), làm việc theo hai hướng. Mỗi hướng có phần **cốt lõi** (phải làm để giữ tầng AI khoẻ) và phần **mở rộng** (đề xuất trong backlog, bảo vệ ở pitch - nơi tạo khác biệt để đánh giá). Giống CDO chọn trụ, AIO **tự đánh giá tầng AI rồi đề xuất mình tập trung vào đâu**. Khi on-call, AIO xử lý cả sự cố hạ tầng lẫn tầng AI ập tới.

### Hướng AIOps - dùng AI để vận hành hệ thống
Dựa trên observability sẵn có (Prometheus metrics / Jaeger traces / OpenSearch logs).
- **Cốt lõi:** phát hiện bất thường đa tín hiệu (latency, error rate, saturation, queue lag, cost…) + **vòng tự động hoá xử lý sự cố** (phát hiện → kiểm tra an toàn: dry-run/blast-radius → xử lý → verify qua telemetry → rollback/escalate), chạy liên tục trong lúc vận hành.
- **Mở rộng:** phân tích nguyên nhân (RCA) cross-service, dự báo capacity/cost, phát hiện drift.

### Hướng AIE - làm AI trong sản phẩm
Bề mặt AI hiện tại là **tóm tắt review** (`product-reviews` + `llm`). Nhiệm vụ AIE gồm cả **vận hành/nâng chất tính năng có sẵn** lẫn **tự dựng một trợ lý AI agentic** trên chính sản phẩm này.

- **Cốt lõi 1 - Chất lượng & an toàn tính năng AI có sẵn:** **không hiển thị tóm tắt sai lệch** cho khách (eval độ trung thực + fallback khi LLM lỗi/chậm); **guardrail** chặn prompt-injection nhét trong review, lọc PII, chặn lộ system prompt; tối ưu **chi phí + độ trễ** (cache, route model rẻ, giảm token, timeout/retry).
- **Cốt lõi 2 - Trợ lý AI agentic (tự dựng):** dựng một trợ lý biết **gọi công cụ** (product-catalog, cart, reviews…) để giúp khách - **BTC không phát sẵn code agent, các bạn tự xây** trên source hiện có. Ví dụ trợ lý cần làm được:
  - *"Tìm tai nghe dưới $50 giao nhanh"* → gọi search catalog + lọc → gợi ý.
  - *"Pin sản phẩm này dùng bao lâu?"* → trả lời **grounded trên review thật** (RAG), không bịa.
  - *"So sánh A với B"* → gom catalog + review 2 sản phẩm → tổng hợp ưu/nhược.
  - *"Thêm 2 cái vào giỏ"* → gọi cart, **nhưng phải xác nhận trước khi checkout**.

  Được đánh giá **không phải "trả lời trôi chảy"**, mà: gọi **đúng công cụ trong phạm vi cho phép** (không tự ý checkout/xoá giỏ - **guardrail excessive-agency**), trả lời **grounded không hallucinate**, có **eval task-success**. Chi tiết bề mặt AI + gợi ý cách dựng: [onboarding/AI_FEATURE.md](onboarding/AI_FEATURE.md).
- **Mở rộng (đua top):** semantic search nâng cao, recommendation bằng tín hiệu AI, model gateway + A/B khi đổi model.

> Với mọi hạng mục AIE: phải **chạy thật** trong hệ thống của TF (không mockup), có **eval** chứng minh chất lượng/an toàn, không phá SLO/ngân sách.

**Phân trụ trong mỗi TF** (Auditability là trụ xuyên suốt mọi thay đổi, nhẹ hơn nên linh hoạt):

*TF có 2 nhóm CDO* - mỗi nhóm 2 trụ core, Auditability chung:
| Nhóm | Trụ |
|---|---|
| Nhóm A (winner Phase 2) | 2 trụ core tự chọn (vd Cost Optimization + Performance Efficiency) |
| Nhóm B | 2 trụ core còn lại (Security + Reliability) |
| Cả hai | Auditability (luân phiên, mỗi tuần 1 nhóm cầm chính) |

*TF có 3 nhóm CDO* - chia 2+2+1:
| Nhóm | Trụ |
|---|---|
| Nhóm A (winner Phase 2) | 2 trụ core tự chọn (vd Cost Optimization + Security) |
| Nhóm B | 2 trụ core còn lại (Reliability + Performance Efficiency) |
| Nhóm C | Auditability (đào sâu 1 mảng) |

**Pick (draft):** thứ tự theo hạng Phase 2, nhóm dẫn đầu chọn trước; snake draft trên **4 trụ core** (Security, Reliability, Performance Efficiency, Cost Optimization), chọn từng trụ một. Được chọn trụ mình muốn là phần thưởng cho nhóm dẫn đầu.

**Tĩnh để sở hữu, xoay để trực:** home-pillar là chủ sở hữu chính (giữ tính liên tục + trách nhiệm). Nhưng khi **on-call trực, bạn xử lý bất kỳ trụ nào ập tới** (sự cố cost, security, hay audit đều vào người trực). Rotation này đảm bảo mọi người chạm đủ mọi mảng trong lúc vận hành.

## 5. Timeline 3 tuần

**Tuần 1 - Tiếp quản, dựng baseline & bảo vệ ưu tiên**
- Onboard: đọc packet trong `onboarding/` - [kiến trúc](onboarding/ARCHITECTURE.md), [SLO](onboarding/SLO.md), [ngân sách](onboarding/BUDGET.md), [lịch sử sự cố](onboarding/INCIDENT_HISTORY.md).
- **Dựng baseline:** build từ source → ECR của TF → deploy chạy trên **EKS** (xem [GETTING_STARTED](GETTING_STARTED.md)). Đưa hệ thống lên sống là mốc cụ thể đầu tiên, đã tính điểm.
- Tự đánh giá hệ thống đang chạy → dựng **backlog ưu tiên** (theo rủi ro × tác động business).
- Cuối tuần: **Pitch bảo vệ ưu tiên** trước hội đồng (đóng vai PM/CFO/SRE lead) - hội đồng sẽ phản biện. Đây là mốc đánh giá tư duy quan trọng nhất. Chi tiết cách chuẩn bị + bị vặn thế nào: [onboarding/PITCH_GUIDE.md](onboarding/PITCH_GUIDE.md).

**Tuần 2-3 - Vận hành & Cải tiến dưới ràng buộc**

Ba nguồn việc chạy song song:
- **Việc tự chọn:** thực thi backlog đã pitch - **không đủ thời gian làm hết**, phải chọn.
- **Directive từ BTC:** trong lúc vận hành, BTC có thể ban hành **yêu cầu bắt buộc toàn TF** dưới dạng memo (vd migrate database sang managed service). Thực thi trong ràng buộc, không thương lượng phạm vi. Memo sẽ xuất hiện trong [`mandates/`](mandates/) khi có hiệu lực.
- **Sự cố:** hệ thống sẽ gặp trục trặc do BTC tạo ra - phát hiện và xử lý, giữ ảnh hưởng tới khách nhỏ nhất (không tắt cơ chế).

- Trực **on-call** luân phiên. Ràng buộc thật: ngân sách có trần, SLO có error budget, stakeholder đòi hỏi trái chiều.
- Mỗi tuần có **Ops Review**: báo cáo trạng thái service (SLO, ngân sách, sự cố, backlog + directive đã xử).

**Kết thúc - Service Health Readout**
- Mỗi TF trình bày: đã làm gì, đánh đổi gì, vì sao, trạng thái service ra sao, tiếp theo là gì.
- Hội đồng **nghe và phản biện (bắt bẻ)** - nhắm vào quyết định và trạng thái service của cả đội, có thể hỏi thẳng một cá nhân để kiểm chứng chiều sâu.

## 6. Nhịp vận hành
- **Standup mỗi ngày**: báo trạng thái, bàn giao ca on-call. Mentor của nhóm theo sát.
- **Weekly Ops Review**: mốc kiểm tra hằng tuần.
- **Sự cố sẽ đến**: hệ thống sẽ gặp trục trặc do ban tổ chức tạo ra trong quá trình vận hành. Nhiệm vụ là **phát hiện và xử lý**, giữ cho khách hàng ít bị ảnh hưởng nhất.

## 7. Sản phẩm phải nộp (deliverables)
- **Backlog ưu tiên** + bản pitch (Tuần 1).
- **Decision log / ADR ký tên** cho mọi quyết định lớn.
- **Postmortem / COE ký tên** sau mỗi sự cố.
- **Ops Review** hằng tuần.
- **Service Health Readout** cuối kỳ (trình bày trước hội đồng + trả lời phản biện).

## 8. Luật chơi
- **Tự build từ source ban tổ chức cấp → đẩy image lên ECR của TF → deploy trên account của TF.**
- **Sự cố là để xử lý, không phải để tắt.** Cơ chế tạo sự cố do ban tổ chức kiểm soát. **Nghiêm cấm** can thiệp, vô hiệu hóa, hay đổi hướng cơ chế này. Vi phạm = **loại khỏi vòng đánh giá (disqualify)**.
- **Đường dây đọc flag là hạ tầng được bảo vệ.** flagd và các hook OpenFeature có sẵn trong service lõi chính là cách ban tổ chức bơm sự cố vào hệ thống của bạn. Gỡ bỏ, vô hiệu, hay refactor để service không còn đọc flag incident nữa được xem như đổi hướng cơ chế sự cố - **disqualify** ngang với re-point flagd. Muốn chịu được sự cố thì làm hệ thống bền hơn (fallback, retry, containment), không tháo đường dây đang có. Bạn vẫn được tự thêm flag/feature mới của mình.
- Điểm yếu do cấu hình (thiếu sót thật trong hệ thống) thì **sửa tận gốc**; sự cố do ban tổ chức bơm vào thì **làm hệ thống chịu được** (fallback, retry, containment) chứ không "tắt cho hết lỗi".
- Fair play: mọi quyết định phải truy được về người (ký tên). Không mượn kết quả của TF khác.
- Tôn trọng ràng buộc: không vượt ngân sách, không phá SLO của nhau.

## 9. Lời kết

Phase 3 đo đúng thứ khó dạy nhất và quan trọng nhất khi đi làm: khả năng nhìn ra vấn đề, vận hành dưới áp lực, đánh đổi có lý, và chịu trách nhiệm với quyết định của mình. Chúc các đội giữ được service khỏe và tỏa sáng.
