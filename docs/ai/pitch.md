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
  2. *Độ tin cậy:* Gọi model chính (Claude 3.0 Sonnet) dễ bị nghẽn (429 Rate Limit) hoặc sập (500) khiến tính năng tóm tắt sập hoàn toàn.
  3. *Excessive Agency:* Trợ lý ảo Shopping Copilot tự ý gọi API giỏ hàng (`add_to_cart`) mà không có sự đồng ý của khách nếu bị Prompt Injection.

<!-- slide -->
## Slide 3: Giải Pháp Kỹ Thuật AIE (AI Engineering)
* **ADR-001 (Valkey Caching):**
  * Lưu trữ bản tóm tắt vào Valkey cache key `reviews:summary:{product_id}`.
  * **TTL Động:** 4 giờ đến 7 ngày tính theo reviews. Active invalidation khi có review mới & Thumbs Down feedback loop.
  * *ROI:* Giảm **90% chi phí token** và phản hồi cache cực nhanh (< 50ms).
* **ADR-004 (Hybrid Task-Specific Routing & Fallback):**
  * Tác vụ Reviews (Cao tải/Rẻ): Amazon Nova Lite -> Fallback: Nova Micro -> Mock. Timeout: 2.0s.
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
## Slide 6: Bảng Phân Bổ 10 Task Ưu Tiên Tuần 1
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
| **TF1-57** | AIE | [Extend] AIE Competitive Items | Nghiên cứu Semantic Search, Recommendations |

---

# PHẦN 2: BẢN ƯỚC LƯỢNG CHI PHÍ & ROI (AWS BEDROCK COST MODEL)

Để chứng minh tính khả thi về mặt tài chính trước CFO, dưới đây là bảng so sánh chi phí ước lượng dựa trên **100,000 lượt xem sản phẩm/ngày** (Tần suất trung bình của storefront):

### 1. Bảng giá đầu vào AWS Bedrock (Vùng us-west-2):
* **Claude 3.0 Sonnet:** $0.003 / 1k Input Tokens | $0.015 / 1k Output Tokens
* **Claude 3 Haiku:** $0.00025 / 1k Input Tokens | $0.00125 / 1k Output Tokens
* *Giả định:* Mỗi request tóm tắt có Input = 1,500 tokens (dữ liệu reviews gộp), Output = 200 tokens (bản tóm tắt).

### 2. So sánh chi phí chi tiết/ngày:

| Kịch bản | Tỷ lệ dùng Sonnet | Tỷ lệ dùng Haiku | Tỷ lệ trúng Cache | Chi phí token/ngày | Chi phí/tuần | Khả năng duy trì ngân sách ($300/tuần) |
|---|---|---|---|---|---|---|
| **Không có Cache (Gọi trực tiếp Sonnet)** | 100% | 0% | 0% | **$750.00** | **$5,250.00** | ❌ **Vượt trần 17.5 lần** |
| **Chỉ có Fallback (80% Sonnet, 20% Haiku)** | 80% | 20% | 0% | **$610.00** | **$4,270.00** | ❌ **Vượt trần 14.2 lần** |
| **Có Valkey Cache (Tỷ lệ hit 90%)** | 10% | 0% | 90% | **$75.00** | **$525.00** | ⚠️ Gần đạt ngưỡng (Cần tối ưu thêm TTL) |
| **Có Valkey Cache + Fallback Routing** | 9% (Sonnet) | 1% (Haiku) | 90% | **$68.00** | **$476.00** | ⚠️ Gần đạt ngưỡng |
| **Có Valkey Cache + Prompt Caching Bedrock** | 10% | 0% | 90% | **$37.50** | **$262.50** |  **Đạt yêu cầu (< $300)** |

> [!TIP]
> **Kết luận cho CFO:** Valkey Caching là giải pháp **bắt buộc**. Nếu không có Cache, hệ thống sẽ đốt sạch ngân sách tuần chỉ trong nửa ngày. Kết hợp Valkey Cache (hit rate 90%) và Prompt Caching trên Bedrock giúp hạ chi phí xuống còn **$262.50/tuần**, nằm an toàn trong hạn mức $300.

---

# PHẦN 3: KỊCH BẢN PHẢN BIỆN VAI TRÒ (ROLEPLAY DEFENSE STRATEGIES)

### 👤 1. PM: "Khách hàng được lợi gì? Tại sao lo hạ tầng mà không ưu tiên cải thiện UI trước?"
* **Lập luận bảo vệ:**
  > *"Thưa PM, trải nghiệm của khách hàng không chỉ là giao diện đẹp mà cốt lõi là tốc độ và độ chính xác. Nếu không tối ưu hạ tầng, mỗi lần khách click vào trang sản phẩm sẽ phải chờ 2.5 giây để gọi LLM sinh tóm tắt review. Theo nghiên cứu Amazon, cứ mỗi 100ms trễ sẽ làm giảm 1% doanh thu. Việc làm Valkey Cache giúp giảm thời gian phản hồi từ 2.5s xuống dưới 50ms (nhanh gấp 50 lần), trực tiếp bảo vệ trải nghiệm mua sắm và tỷ lệ chuyển đổi. Đồng thời, chúng tôi xây dựng Confirmation Gate cho Shopping Copilot để đảm bảo giỏ hàng của khách hàng không bị thay đổi ngoài ý muốn khi có lỗi hoặc prompt injection, bảo vệ uy tín thương hiệu."*

### 👤 2. CFO: "Tốn bao nhiêu tiền? Chứng minh ROI của việc này đáng tiền?"
* **Lập luận bảo vệ:**
  > *"Thưa CFO, trần chi phí của chúng ta là $300/tuần. Nếu chạy trực tiếp không có cache, chi phí token Bedrock thực tế sẽ chạm ngưỡng $5,250/tuần (vượt trần 17 lần) chỉ với lượng traffic cơ bản 100k views/ngày. Bằng cách ưu tiên thiết kế Valkey Caching (tái sử dụng cụm valkey-cart có sẵn của CDO, chi phí phát sinh bằng $0), chúng tôi giữ lại 90% request tại cache, chỉ tốn $262.50/tuần để gọi API Bedrock. Giải pháp này giúp công ty tiết kiệm gần $5,000/tuần tiền hóa đơn đám mây. Đây là mức ROI cực kỳ rõ ràng và đo lường được ngay lập tức."*

### 👤 3. SRE Lead: "Rủi ro kỹ thuật là gì? Nhỡ code của các bạn làm sập hệ thống hoặc gây lỗi dây chuyền thì sao?"
* **Lập luận bảo vệ:**
  > *"Thưa SRE Lead, chúng tôi đã đặt an toàn hệ thống lên hàng đầu với 2 chốt chặn kỹ thuật:*
  > *1. **Model Fallback Routing (ADR-002):** Khi AWS Bedrock bị lỗi (429/500) hoặc timeout > 5.0s, hệ thống tự động retry 2 lần và chuyển đổi sang model backup Claude 3 Haiku trong vòng 500ms, đảm bảo tính liên tục của dịch vụ và không làm nghẽn thread pool của product-reviews.*
  > *2. **AIOps Closed-Loop Safety Boundary:** Kịch bản tự khắc phục lỗi của chúng tôi được thiết kế theo chuẩn SRE nghiêm ngặt: luôn chạy Dry-run trước để kiểm tra quyền; giới hạn Blast Radius (không restart quá 1 pod/giờ để tránh cascade loop); đo đạc metrics 120s sau sửa lỗi, nếu latency storefront không giảm về ngưỡng bình thường thì tự động kích hoạt Rollback cấu hình cũ; cuối cùng, nếu fail 3 lần liên tiếp, Circuit Breaker sẽ đóng băng tự động và báo động cho kỹ sư trực on-call."*
