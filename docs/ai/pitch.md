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
  1. *Độ trễ và Chi phí:* Mỗi lần khách bấm *Ask AI*, một cuộc gọi Bedrock không cache tốn ~1.5s - 2.5s và trả tiền token lặp lại cho cùng một sản phẩm.
  2. *Độ tin cậy:* Gọi model chính (Amazon Nova Lite) dễ bị nghẽn (429 Rate Limit) hoặc sập (500) khiến tính năng tóm tắt sập hoàn toàn.
  3. *Excessive Agency:* Trợ lý ảo Shopping Copilot tự ý gọi API giỏ hàng (`add_to_cart`) mà không có sự đồng ý của khách nếu bị Prompt Injection.

<!-- slide -->
## Slide 3: Giải Pháp Kỹ Thuật AIE (AI Engineering)
* **ADR-001 (Valkey Caching):**
  * Lưu trữ bản tóm tắt vào Valkey cache key `reviews:summary:{product_id}:{model_ver}:{prompt_ver}`.
  * **TTL phẳng 7 ngày** (cập nhật 12/07: review data tĩnh — đã kiểm chứng — nên TTL động không có gì để phản ứng, đã bỏ). Làm mới bằng **versioned cache key** (`{model_ver}:{prompt_ver}` — derive từ env model thật + hash prompt) — đổi model/prompt là miss tự nhiên.
  * *ROI:* Chủ yếu là **độ trễ trợ lý AI: 2.5s → < 50ms**. Phần token giảm 90% là credit, không phải tiền mặt (xem Phần 2).
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

Để chứng minh tính khả thi về mặt tài chính trước CFO, dưới đây là bảng so sánh chi phí ước lượng dựa trên **100,000 lượt xem sản phẩm/ngày** (tần suất trung bình của storefront).

> [!IMPORTANT]
> **Mẫu số là số lời gọi LLM, không phải số lượt xem trang.** Tóm tắt review **không** chạy khi tải trang: `ProductReviews.tsx` chỉ gọi `AskProductAIAssistant` khi khách bấm nút *Ask AI* / quick prompt, còn lúc render trang chỉ có `GetProductReviews` đọc thẳng PostgreSQL. Theo mô hình tải của chính hệ thống (`src/load-generator/locustfile.py`: `browse_product` trọng số 10 so với `ask_product_ai_assistant` trọng số 1), tỉ lệ là **10 lượt xem : 1 lời gọi LLM**.
>
> ⇒ Tải LLM cơ sở = **10,000 request/ngày**. Mọi con số dưới đây tính trên mẫu số này.

### 1. Bảng giá đầu vào AWS Bedrock (Vùng `us-east-1` — xem ADR-004):

**Model đã chọn (Amazon first-party — cấn trừ 100% bằng AWS Credits, tiền mặt thật = $0):**
* **Amazon Nova Lite:** $0.06 / 1M Input Tokens | $0.24 / 1M Output Tokens → **$0.000138 / request**
* **Amazon Nova Micro:** $0.035 / 1M Input | $0.14 / 1M Output → **$0.0000805 / request**
* **Amazon Nova Pro:** $0.80 / 1M Input | $3.20 / 1M Output → **$0.00184 / request**

**Model đã loại bỏ (AWS Marketplace — buộc trả tiền mặt thật, không cấn trừ credit):**
* **Claude 3.5 Sonnet:** $3.00 / 1M Input | $15.00 / 1M Output → **$0.0075 / request**

* *Giả định:* Mỗi request tóm tắt có Input = 1,500 tokens (dữ liệu reviews gộp), Output = 200 tokens (bản tóm tắt). Tải cơ sở 100,000 lượt xem sản phẩm/ngày → **10,000 lời gọi LLM/ngày** (tỉ lệ 1:10, xem ghi chú mẫu số ở trên).

### 2. So sánh chi phí chi tiết/ngày:

| Kịch bản | Model | Cache hit | Chi phí/ngày | Chi phí/tuần | Loại chi phí | Kết luận |
|---|---|---|---|---|---|---|
| **(Đã loại) Claude, không Cache** | Claude 3.5 Sonnet | 0% | **$75.00** | **$525.00** | 💵 Tiền mặt thật | ❌ **Vượt trần 1.75 lần** |
| **(Đã loại) Claude + Cache 90%** | Claude 3.5 Sonnet | 90% | **$7.50** | **$52.50** | 💵 Tiền mặt thật | ⚠️ Trong trần, nhưng **ăn thật vào $300** của CDO |
| **Nova Lite, không Cache** | Nova Lite | 0% | $1.38 | $9.66 | 🎟️ Credit ($0 cash) | ⚠️ Không tốn tiền mặt, nhưng lãng phí token |
| **Nova Lite + Valkey Cache** | Nova Lite | 90% | $0.14 | **$0.97** | 🎟️ Credit ($0 cash) | ✅ **Đạt** |
| **Nova Lite + Cache + Fallback Micro** | Lite 9% / Micro 1% | 90% | $0.13 | **$0.93** | 🎟️ Credit ($0 cash) | ✅ **Đạt** |
| **Nova Lite + Cache + Prompt Caching** | Nova Lite | 90% | $0.08 | **$0.58** | 🎟️ Credit ($0 cash) | ✅ **Tối ưu nhất** |

> [!TIP]
> **Kết luận cho CFO — hai quyết định độc lập, mỗi cái giải một bài toán khác nhau:**
>
> 1. **Chọn Nova thay Claude (ADR-004) → cắt chi phí *tiền mặt* về $0.** Đây là trục chính, và nó **không phụ thuộc vào lưu lượng**. Claude nằm trên AWS Marketplace nên **không cấn trừ được credit**: mỗi đô-la Claude tiêu là một đô-la tiền mặt rút thẳng khỏi trần $300 vốn dành cho EKS node, NAT, LB của nhóm CDO. Không cache thì Claude tốn $525/tuần — vượt trần 1.75 lần; có cache 90% thì còn $52.50/tuần — *nằm trong trần*, nhưng vẫn là **tiền mặt thật** chiếm 17.5% ngân sách hạ tầng để đổi lấy đúng thứ mà Nova cho không. Nova là first-party, cấn trừ 100% bằng AWS Credits: **tiền mặt = $0 ở mọi mức tải.**
> 2. **Valkey Caching (ADR-001) → cắt 90% credit burn và cắt latency.** Với Nova, chi phí token đã nhỏ không đáng kể ngay cả khi không cache ($9.66/tuần credit). Vì vậy **ROI thật của cache không nằm ở tiền, mà ở độ trễ của trợ lý AI: 2.5s → < 50ms.** Đây là lập luận dành cho PM, không phải CFO.
>
> Lưu ý phạm vi trần: $300/tuần trong `onboarding/BUDGET.md` là ngân sách **hạ tầng AWS** (EKS node, EBS, NAT, LB). Chi phí Bedrock của Nova được cấn trừ hoàn toàn bằng credit nên **không tiêu vào trần này**; còn chi phí Claude qua Marketplace thì có — đó chính là lý do nó bị loại.

---

# PHẦN 3: KỊCH BẢN PHẢN BIỆN VAI TRÒ (ROLEPLAY DEFENSE STRATEGIES)

### 👤 1. PM: "Khách hàng được lợi gì? Tại sao lo hạ tầng mà không ưu tiên cải thiện UI trước?"
* **Lập luận bảo vệ:**
  > *"Thưa PM, trải nghiệm của khách hàng không chỉ là giao diện đẹp mà cốt lõi là tốc độ và độ chính xác. Xin nói chính xác phạm vi: tóm tắt review **không** chặn việc render trang sản phẩm — trang vẫn tải bình thường từ PostgreSQL. Nó chạy khi khách chủ động bấm nút **Ask AI**. Nhưng đúng ở khoảnh khắc đó, khách đang chờ và đang nhìn màn hình: không cache thì họ chờ 2.5 giây, có cache thì dưới 50ms — nhanh gấp 50 lần. Đây là tính năng AI mà khách chủ động yêu cầu, nên một trợ lý trả lời tức thì hay ì ạch chính là thứ quyết định họ có dùng lại lần thứ hai không.*
  >
  > *Đồng thời, chúng tôi xây dựng Confirmation Gate cho Shopping Copilot để đảm bảo giỏ hàng của khách hàng không bị thay đổi ngoài ý muốn khi có lỗi hoặc prompt injection, bảo vệ uy tín thương hiệu."*

### 👤 2. CFO: "Tốn bao nhiêu tiền? Chứng minh ROI của việc này đáng tiền?"
* **Lập luận bảo vệ:**
  > *"Thưa CFO, trần chi phí hạ tầng của chúng ta là $300/tuần. Rủi ro lớn nhất không phải là lưu lượng, mà là **chọn sai model**: Claude 3.5 Sonnet nằm trên AWS Marketplace nên phải trả bằng **tiền mặt thật, không cấn trừ được credit khuyến mại**. Tôi xin nói rõ mẫu số trước khi nói con số: tóm tắt review chỉ chạy khi khách bấm nút, không phải mỗi lượt xem trang — theo mô hình tải của chính hệ thống thì tỉ lệ là 1:10, tức 10,000 lời gọi/ngày trên 100k lượt xem. Với mẫu số đó, Claude tốn $525/tuần tiền mặt khi không cache, **vượt trần 1.75 lần**. Có cache 90% thì còn $52.50/tuần — nằm trong trần, nhưng vẫn là tiền mặt thật, và nó ăn 17.5% ngân sách lẽ ra dành cho EKS node và NAT của nhóm CDO.*
  >
  > *Vì vậy quyết định đầu tiên của chúng tôi (ADR-004) là chuyển toàn bộ sang Amazon Nova, được cấn trừ 100% bằng AWS Credits: **chi phí tiền mặt về đúng $0, ở mọi mức tải.** Xin nhấn mạnh — lập luận này không phụ thuộc vào việc lưu lượng có tăng gấp mười hay không; nó là câu chuyện credit đối lại tiền mặt.*
  >
  > *Quyết định thứ hai — Valkey Caching (ADR-001) — tái sử dụng cụm `valkey-cart` sẵn có của CDO nên chi phí hạ tầng phát sinh cũng bằng $0. Tôi xin nói thẳng để không thổi phồng con số: sau khi đã chuyển sang Nova, token chỉ còn ~$9.66/tuần credit ngay cả khi không cache. Cache kéo nó xuống dưới $1/tuần, **nhưng đó không phải lý do chính đáng để làm cache**. Lý do chính đáng là latency — 2.5s xuống dưới 50ms — và đó là câu chuyện của PM chứ không phải của CFO. Với ngài, cam kết của chúng tôi gọn thế này: **$0 tiền mặt cho toàn bộ tầng AI, và trần $300 giữ nguyên vẹn cho nhóm CDO dùng vào compute.**"*

### 👤 3. SRE Lead: "Rủi ro kỹ thuật là gì? Nhỡ code của các bạn làm sập hệ thống hoặc gây lỗi dây chuyền thì sao?"
* **Lập luận bảo vệ:**
  > *"Thưa SRE Lead, tôi xin phân định rõ **cái gì đã chạy** và **cái gì mới là thiết kế của tuần này** — vì tuần 1 là tuần lập kế hoạch:*
  >
  > ***Đã có trong code hôm nay:*** *`product-reviews` gọi Amazon Bedrock Nova Lite qua Converse API, có Valkey cache với versioned key và TTL động 4h–7d, và detector cảnh báo vận hành (`tools/aiops-detector`) đã chạy với 9 rule bám đúng ngưỡng SLO thật (error rate 0.5%, checkout 1%, p95 1.0s).*
  >
  > ***Đã đặc tả, chưa cắm vào code — sẽ làm ở Tuần 2:***
  > *1. **Resilience Stack (ADR-005) + Hybrid Routing (ADR-004):** khi Bedrock lỗi (429/500) hoặc quá timeout, hệ thống sẽ retry tối đa 2 lần với exponential backoff + full jitter, rồi fallback: Reviews đi Nova Lite (timeout 3.0s) → Nova Micro (2.0s) → Mock Summary; Copilot đi Nova Pro (5.0s) → Nova Lite (3.0s). Bulkhead `asyncio.Semaphore(10)` sẽ chặn các cuộc gọi Bedrock chậm làm cạn thread pool của pod `product-reviews` — quan trọng vì **cùng pod đó cũng phục vụ `GetProductReviews` nằm trên đường render trang**, nên đây mới là đường mà lỗi LLM có thể lan sang SLO p95 < 1s của storefront. Circuit Breaker sẽ mở ngay khi flagd bật `llmRateLimitError`, để không đốt token vào các cuộc gọi chắc chắn hỏng. Cập nhật 12/07: bulkhead (non-blocking, size 6), circuit breaker (3 lỗi liên tiếp → open 30s, theo lỗi quan sát được — không đọc cờ flagd) và fallback ladder đã nằm trong code, có bằng chứng runtime: khi primary lỗi, log ghi "Fallback routing triggered → nova-micro" và "Circuit Breaker OPENED for 30.0s"; khách luôn nhận mock summary, không bao giờ nhận lỗi thô.*
  > *2. **AIOps Closed-Loop Safety Boundary (TF1-50, `specs/anomaly_remediation.md`):** vòng tự khắc phục được thiết kế theo chuẩn SRE nghiêm ngặt: luôn Dry-run trước để kiểm tra quyền; giới hạn Blast Radius (tối đa 1 pod/namespace/giờ để tránh cascade loop); đo metrics 120s sau khi vá, nếu không về ngưỡng bình thường thì tự Rollback; fail 3 lần liên tiếp thì Circuit Breaker đóng băng và gọi on-call. Vòng này **cố ý chưa bật auto-remediation trong tuần 1** — chúng tôi chỉ detect và alert (`tools/aiops-detector` không hề gọi API ghi vào Kubernetes)."*

---

# PHỤ LỤC CẬP NHẬT 12/07/2026 — chỉnh lập luận theo kết quả kiểm chứng

1. **CFO — bỏ trục "credit vs tiền mặt", thay bằng trục GIÁ (đã verify):** claim "Claude = Marketplace = không cấn trừ credit" chưa được kiểm chứng với loại credit BTC cấp, và AWS đã nhận Activate credits cho 3P models từ 04/2024 — lập luận này sập nếu hội đồng hỏi đúng 1 câu. Nhóm đã **chốt bỏ Claude (11/07)**; lập luận thay thế đứng vững bằng số niêm yết: **Nova Lite rẻ ~50× Claude Sonnet** ($0.06/$0.24 vs $3/$15 per 1M token) → $9.66/tuần không cache, <$1/tuần có cache — dưới 0.4% trần $300 ở mọi kịch bản. Lưu ý thêm: Claude 3.5 Sonnet trong bảng so sánh đã EOL trên Bedrock (03/2026).
2. **Số latency trình bày:** "2.5s" chưa đo — theo Artificial Analysis (TTFT 1.04s, 175.7 tok/s), luồng tóm tắt 2 vòng converse ≈ **4.4s điển hình** khi chưa cache; giá trị cache vẫn nguyên (→ <50ms) nhưng con số trước-cache phải nói là ước từ benchmark, chờ đo thật trên Bedrock (script `docs/ai/evals/measure_bedrock_latency.py` sẵn, cần AWS creds).
3. **Số AIOps có evidence mới cho slide 5:** MTTD đo thật (chaos flagd, 5 vòng): **max 35.4s với poll 30s** — dưới 1 phút như ADR-007 hứa, tiêu ~0.5% error budget/ngày. Nguồn: `docs/ai/evals/measure_detection_pipeline.py`.
