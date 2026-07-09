# Slide Pitching & Kịch Bản Bảo Vệ Kế Hoạch Tuần 1
**Đội ngũ thực hiện:** AI Team (AIO03) - Task Force 1  
**Ngày báo cáo:** 2026-07-10 (Thứ Sáu)  
**Trạng thái:** Sẵn sàng cho buổi bảo vệ (Pitching Defense)

---

# PHẦN 1: CẤU TRÚC SLIDES TRÌNH BÀY (SLIDE DECK OUTLINE)

<!-- slide -->
## Slide 1: Thiết Lập Baseline & Kế Hoạch Nghiệm Thu Tuần 1
* **Tiêu đề:** Tối ưu hóa hiệu năng & Tin cậy Vận hành storefront TechX Corp bằng AI (AIE & AIOps)
* **Người trình bày:** Nhóm AI (AIO03)
* **Cam kết cốt lõi:**
  * Bảo vệ trần ngân sách AWS: **$300/tuần** (onboarding/BUDGET.md).
  * Đạt chỉ số chất lượng dịch vụ: Storefront p95 Latency **< 1.0s**, Error Rate **< 0.5%** (onboarding/SLO.md).

<!-- slide -->
## Slide 2: Đánh Giá Hiện Trạng Hệ Thống & Rủi Ro Cốt Lõi
* **Hiện trạng kiến trúc:**
  * Dịch vụ `product-reviews` đang gọi trực tiếp mock API `llm` trên cụm K8s (EKS).
* **3 Rủi ro nghiêm trọng nhất (SPOF & Bottlenecks):**
  1. *Độ trễ và Chi phí:* API Bedrock trực tiếp tốn ~1.5s - 2.5s và chi phí token khổng lồ cho mỗi lượt xem sản phẩm.
  2. *Độ tin cậy:* Gọi model chính (Amazon Nova Lite) dễ bị nghẽn (429 Rate Limit) hoặc sập (500) khiến tính năng tóm tắt sập hoàn toàn.
  3. *Excessive Agency:* Trợ lý ảo Shopping Copilot tự ý gọi API giỏ hàng (`add_to_cart`) mà không có sự đồng ý của khách nếu bị Prompt Injection.

<!-- slide -->
## Slide 3: Giải Pháp Kỹ Thuật AIE (AI Engineering)
* **ADR-001 (Valkey Caching):**
  * Lưu trữ bản tóm tắt vào Valkey cache key `reviews:summary:{product_id}`.
  * **TTL Động:** 4 giờ đến 7 ngày tính theo reviews. Làm mới bằng **versioned cache key** (`{model_ver}:{prompt_ver}`) — đổi model/prompt là miss tự nhiên.
  * *ROI:* Giảm **90% chi phí token** và phản hồi cache cực nhanh (< 50ms).
* **ADR-004 (Hybrid Task-Specific Routing & Fallback):**
  * Tác vụ Reviews (Cao tải/Rẻ): Amazon Nova Lite -> Fallback: Nova Micro -> Mock. Timeout: 3.0s.
  * Tác vụ Chatbot (Phức tạp): Amazon Nova Pro -> Fallback: Amazon Nova Lite -> Mock. Timeout: 5.0s.
  * Thử lại (Retry) tối đa 2 lần với Exponential Backoff + Jitter trước khi fallback. Toàn bộ chi phí cấn trừ qua Credit AWS (tiền mặt thật = $0).

<!-- slide -->
## Slide 4: Trợ Lý Shopping Copilot An Toàn (PoC)
* **3 Intents hoạt động chính:**
  1. *Search Catalog:* Tìm kiếm sản phẩm bằng ngôn ngữ tự nhiên.
  2. *Reviews RAG:* Grounded QA chỉ dựa trên review thật, cấm bịa đặt (hallucinate).
  3. *Cart Operations:* Cài đặt **Confirmation Gate** (Yêu cầu người dùng bấm xác nhận rõ ràng trước khi gọi tool ghi vào giỏ hàng).
* **Chỉ số đo lường (AI Evals):**
  * Chạy đánh giá tự động qua `run_evals.py` trên bộ dữ liệu `golden_dataset.json` để kiểm soát độ trung thực (fidelity) của bản tóm tắt review.

<!-- slide -->
## Slide 5: Giải Pháp Vận Hành AIOps (AI Operations)
* **EWMA Anomaly Detection:**
  * Giám sát p95 Latency và Error Rate (ngưỡng 3 độ lệch chuẩn, hệ số làm mượt $\alpha = 0.2$) để lọc cảnh báo nhiễu.
* **Drain3 Log Clustering:**
  * Phân cụm log tự động để phát hiện các mẫu log lỗi mới lạ (OOM, db pool exhaustion) thời gian thực.
* **Vòng Tự Khắc Phục Khép Kín (Closed-loop Remediation):**
  * Thiết kế kịch bản tự động xử lý đi kèm các rào cản an toàn: **Dry-run (chạy thử), Blast Radius (tối đa 1 pod/giờ), Verification (đo metrics 120s sau vá lỗi), và Circuit Breaker (ngắt tự động sau 3 lần fail liên tiếp)**.

<!-- slide -->
## Slide 6: Bảng Phân Bổ 12 Task Ưu Tiên Tuần 1
* *Bảng công việc chi tiết được chia đều cho 10 thành viên (5 AIE, 5 AIOps) trên JIRA:*

| Mã Task | Phân Hệ | Tên Task | Trọng Tâm Nghiệm Thu |
|---|---|---|---|
| **TF1-44** | AIE | Backlog & Risk Assessment | Hoàn thiện file `00_backlog.md` |
| **TF1-45** | AIE | Slide Pitching & Cost Model | Slide & Kịch bản bảo vệ ngân sách |
| **TF1-46** | AIE | Valkey & Fallback Spec | Đặc tả spec caching & fallback routing |
| **TF1-47** | AIE | [Extend] Copilot Spec & CDO Contracts | Đặc tả gRPC `:50051` và ký hợp đồng CDO |
| **TF1-48** | AIE | [Extend] Copilot PoC & Evals Script | Mã nguồn Streamlit và `run_evals.py` |
| **TF1-49** | AIOps | Golden Signal Spec | Đặc tả thuật toán EWMA phát hiện lỗi |
| **TF1-50** | AIOps | [Extend] Remediation Spec | Đặc tả an toàn vòng tự phục hồi |
| **TF1-51** | AIOps | Telemetry Audit | Audit luồng trace GenAI không đứt đoạn |
| **TF1-52** | AIOps | [Extend] Drain3 Log Clustering | Gom cụm log lỗi thực tế |
| **TF1-53** | AIOps | [Extend] Script cảnh báo vận hành | Alerting script báo lỗi DB, OOM, DNS |
| **TF1-54** | AIE | Eviction Policy Valkey (Option 1) | `volatile-lru` + bỏ Cart TTL + Cron GC |
| **TF1-58** | AIE | Nối `product-reviews` vào Bedrock Nova; cache theo versioned key | Đóng khoảng cách docs ↔ code sau review mentor |

---

# PHẦN 2: BẢN ƯỚC LƯỢNG CHI PHÍ & ROI (AWS BEDROCK COST MODEL)

Để chứng minh tính khả thi về mặt tài chính trước CFO, dưới đây là bảng so sánh chi phí ước lượng dựa trên **100,000 lượt xem sản phẩm/ngày** (Tần suất trung bình của storefront):

### 1. Bảng giá đầu vào AWS Bedrock (Vùng `us-east-1` — xem ADR-004):

**Model đã chọn (Amazon first-party — cấn trừ 100% bằng AWS Credits, tiền mặt thật = $0):**
* **Amazon Nova Lite:** $0.06 / 1M Input Tokens | $0.24 / 1M Output Tokens → **$0.000138 / request**
* **Amazon Nova Micro:** $0.035 / 1M Input | $0.14 / 1M Output → **$0.0000805 / request**
* **Amazon Nova Pro:** $0.80 / 1M Input | $3.20 / 1M Output → **$0.00184 / request**

**Model đã loại bỏ (AWS Marketplace — buộc trả tiền mặt thật, không cấn trừ credit):**
* **Claude 3.5 Sonnet:** $3.00 / 1M Input | $15.00 / 1M Output → **$0.0075 / request**

* *Giả định:* Mỗi request tóm tắt có Input = 1,500 tokens (dữ liệu reviews gộp), Output = 200 tokens (bản tóm tắt). Tải cơ sở 100,000 lượt xem sản phẩm/ngày.

### 2. So sánh chi phí chi tiết/ngày:

| Kịch bản | Model | Cache hit | Chi phí/ngày | Chi phí/tuần | Loại chi phí | Kết luận |
|---|---|---|---|---|---|---|
| **(Đã loại) Claude, không Cache** | Claude 3.5 Sonnet | 0% | **$750.00** | **$5,250.00** | 💵 Tiền mặt thật | ❌ **Vượt trần 17.5 lần** |
| **(Đã loại) Claude + Cache 90%** | Claude 3.5 Sonnet | 90% | **$75.00** | **$525.00** | 💵 Tiền mặt thật | ❌ **Vẫn vượt trần 1.75 lần** |
| **Nova Lite, không Cache** | Nova Lite | 0% | $13.80 | $96.60 | 🎟️ Credit ($0 cash) | ⚠️ Trong trần, nhưng lãng phí token |
| **Nova Lite + Valkey Cache** | Nova Lite | 90% | $1.38 | **$9.66** | 🎟️ Credit ($0 cash) | ✅ **Đạt** |
| **Nova Lite + Cache + Fallback Micro** | Lite 9% / Micro 1% | 90% | $1.32 | **$9.25** | 🎟️ Credit ($0 cash) | ✅ **Đạt** |
| **Nova Lite + Cache + Prompt Caching** | Nova Lite | 90% | $0.83 | **$5.80** | 🎟️ Credit ($0 cash) | ✅ **Tối ưu nhất** |

> [!TIP]
> **Kết luận cho CFO — hai quyết định độc lập, mỗi cái giải một bài toán khác nhau:**
>
> 1. **Chọn Nova thay Claude (ADR-004) → cắt chi phí *tiền mặt* về $0.** Claude nằm trên AWS Marketplace nên **không cấn trừ được credit**: dù đã cache 90%, nó vẫn ngốn $525/tuần tiền mặt thật, tức **vượt trần $300 tới 1.75 lần**. Đây là quyết định cứu ngân sách, không phải quyết định tối ưu hoá.
> 2. **Valkey Caching (ADR-001) → cắt 90% credit burn và cắt latency.** Với Nova, chi phí token đã nằm sâu trong trần ngay cả khi không cache ($96.60/tuần). Vì vậy **ROI thật của cache không nằm ở tiền, mà ở p95 latency: 2.5s → < 50ms.** Đây là lập luận dành cho PM, không phải CFO.
>
> Lưu ý phạm vi trần: $300/tuần trong `onboarding/BUDGET.md` là ngân sách **hạ tầng AWS** (EKS node, EBS, NAT, LB). Token Bedrock của Nova được cấn trừ hoàn toàn bằng credit nên **không tiêu vào trần này**; trần còn nguyên cho nhóm CDO dùng vào compute.

---

# PHẦN 3: KỊCH BẢN PHẢN BIỆN VAI TRÒ (ROLEPLAY DEFENSE STRATEGIES)

### 👤 1. PM: "Khách hàng được lợi gì? Tại sao lo hạ tầng mà không ưu tiên cải thiện UI trước?"
* **Lập luận bảo vệ:**
  > *"Thưa PM, trải nghiệm của khách hàng không chỉ là giao diện đẹp mà cốt lõi là tốc độ và độ chính xác. Nếu không tối ưu hạ tầng, mỗi lần khách click vào trang sản phẩm sẽ phải chờ 2.5 giây để gọi LLM sinh tóm tắt review. Theo nghiên cứu Amazon, cứ mỗi 100ms trễ sẽ làm giảm 1% doanh thu. Việc làm Valkey Cache giúp giảm thời gian phản hồi từ 2.5s xuống dưới 50ms (nhanh gấp 50 lần), trực tiếp bảo vệ trải nghiệm mua sắm và tỷ lệ chuyển đổi. Đồng thời, chúng tôi xây dựng Confirmation Gate cho Shopping Copilot để đảm bảo giỏ hàng của khách hàng không bị thay đổi ngoài ý muốn khi có lỗi hoặc prompt injection, bảo vệ uy tín thương hiệu."*

### 👤 2. CFO: "Tốn bao nhiêu tiền? Chứng minh ROI của việc này đáng tiền?"
* **Lập luận bảo vệ:**
  > *"Thưa CFO, trần chi phí hạ tầng của chúng ta là $300/tuần. Rủi ro lớn nhất không phải là lưu lượng, mà là **chọn sai model**: Claude 3.5 Sonnet nằm trên AWS Marketplace nên phải trả bằng **tiền mặt thật, không cấn trừ được credit khuyến mại**. Với 100k views/ngày, Claude tốn $5,250/tuần khi không cache — và kể cả khi đã cache 90% thì vẫn còn $525/tuần, tức vẫn vượt trần 1.75 lần. Vì vậy quyết định đầu tiên của chúng tôi (ADR-004) là chuyển toàn bộ sang Amazon Nova, vốn được cấn trừ 100% bằng AWS Credits: **chi phí tiền mặt về đúng $0**.*
  >
  > *Quyết định thứ hai — Valkey Caching (ADR-001) — tái sử dụng cụm `valkey-cart` sẵn có của CDO nên chi phí hạ tầng phát sinh cũng bằng $0. Tôi xin nói thẳng để không thổi phồng con số: sau khi đã chuyển sang Nova, token chỉ còn ~$96.60/tuần credit ngay cả khi không cache. Cache kéo nó xuống $9.66/tuần, **nhưng đó không phải lý do chính đáng để làm cache**. Lý do chính đáng là latency — 2.5s xuống dưới 50ms — và đó là câu chuyện của PM chứ không phải của CFO. Với ngài, cam kết của chúng tôi gọn thế này: **$0 tiền mặt cho toàn bộ tầng AI, và trần $300 giữ nguyên vẹn cho nhóm CDO dùng vào compute.**"*

### 👤 3. SRE Lead: "Rủi ro kỹ thuật là gì? Nhỡ code của các bạn làm sập hệ thống hoặc gây lỗi dây chuyền thì sao?"
* **Lập luận bảo vệ:**
  > *"Thưa SRE Lead, chúng tôi đã đặt an toàn hệ thống lên hàng đầu với 2 chốt chặn kỹ thuật:*
  > *1. **Hybrid Task-Specific Routing (ADR-004) + Resilience Stack (ADR-005):** Khi AWS Bedrock lỗi (429/500) hoặc quá timeout, hệ thống retry tối đa 2 lần với exponential backoff + full jitter, rồi tự động fallback: luồng Reviews đi Nova Lite (timeout 3.0s) → Nova Micro (2.0s) → Mock Summary; luồng Copilot đi Nova Pro (5.0s) → Nova Lite (3.0s). Bulkhead `asyncio.Semaphore(10)` chặn cạn kiệt thread pool của product-reviews, và Circuit Breaker mở ngay khi flagd bật `llmRateLimitError` nên ta không đốt token vào các cuộc gọi chắc chắn hỏng.*
  > *2. **AIOps Closed-Loop Safety Boundary:** Kịch bản tự khắc phục lỗi của chúng tôi được thiết kế theo chuẩn SRE nghiêm ngặt: luôn chạy Dry-run trước để kiểm tra quyền; giới hạn Blast Radius (không restart quá 1 pod/giờ để tránh cascade loop); đo đạc metrics 120s sau sửa lỗi, nếu latency storefront không giảm về ngưỡng bình thường thì tự động kích hoạt Rollback cấu hình cũ; cuối cùng, nếu fail 3 lần liên tiếp, Circuit Breaker sẽ đóng băng tự động và báo động cho kỹ sư trực on-call."*
