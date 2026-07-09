# Decision Log (ADR) - TF1 / AI Team (AIO03)

---

## ADR-001 - Sử dụng Valkey Caching cho dịch vụ Product Reviews
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-08
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Cost Optimization / Performance Efficiency
- **Bối cảnh:** 
  Hệ thống Storefront hiển thị review tóm tắt bằng AI cho khách hàng trên trang chi tiết sản phẩm. Nếu không sử dụng cache, mỗi lượt tải trang chi tiết sẽ gọi trực tiếp AWS Bedrock API, phát sinh chi phí token khổng lồ (bất lợi cho CFO) và làm tăng độ trễ p95 phản hồi lên > 2 giây (vi phạm SLO latency < 1s).
- **Quyết định:** 
  Tận dụng cụm cache Valkey sẵn có (`valkey-cart` chạy trên cổng `6379`) để lưu trữ các bản tóm tắt review dưới dạng JSON.
  - **Cache Key Format:** `reviews:summary:{product_id}`
  - **Bypass Flag:** Sử dụng OpenFeature flag `llmReviewsCacheEnabled` (kiểm soát qua flagd) để tắt cache nhanh khi cần kiểm thử hoặc cập nhật.
  - **Cập nhật bổ sung (Dynamic TTL & Active Invalidation):**
    1. **TTL động (Dynamic TTL):** Thay vì TTL 24h cố định, TTL được tính động từ **4 giờ đến 7 ngày** dựa trên số lượng review ($N$) và độ biến động điểm số ($\sigma^2$) của sản phẩm nhằm tối ưu hóa chi phí token tối đa.
    2. **Hủy cache khi có review mới (Write-Around Invalidation):** Xóa cache ngay khi API nhận review mới để khách tiếp theo thấy tóm tắt thời gian thực.
    3. **Phản hồi chất lượng kém (Feedback Loop):** Tích hợp nút Thumbs Down. Nếu $\ge 3$ lượt vote kém, tự xóa cache cũ và ép định tuyến cuộc gọi tiếp theo qua **Claude 3.5 Sonnet** (thay vì Nova Lite) để nâng cấp chất lượng.
- **Phương án khác đã cân:**
  - *Option A - Sử dụng Amazon ElastiCache (Redis managed):* Độ bền cao và bảo mật hơn, tuy nhiên tăng chi phí cố định tối thiểu ~$30/tuần -> Vi phạm trần ngân sách AWS $300/tuần. Quyết định: Bỏ qua và dùng Valkey in-cluster.
  - *Option B - Sử dụng thuật toán Eviction LFU thay vì LRU:* Bị loại bỏ vì LFU dễ bị Cache Pollution bởi các sản phẩm cũ từng rất hot, không linh hoạt bằng LRU đối với trend mua sắm thay đổi liên tục.
- **Cost Δ:** Tiết kiệm khoảng **85% - 90%** chi phí gọi Bedrock API (giảm từ ~$80/tuần xuống còn ~$8/tuần cho các sản phẩm hot). Cơ chế Dynamic TTL giúp tiết kiệm thêm **~40% chi phí token** cho các sản phẩm ít reviews.
- **Ảnh hưởng SLO:** Giảm p95 latency của trang chi tiết sản phẩm từ **2.5s xuống < 100ms** khi cache hit, giữ vững cam kết SLO (< 1s).
- **Rollback:** Chuyển đổi flag `llmReviewsCacheEnabled` sang `false` để bypass cache và gọi trực tiếp Bedrock. Nếu Valkey bị sập, Reviews service tự động bỏ qua cache và log error.
- **Hệ quả:**
  - ✅ *Lợi ích:* Tiết kiệm chi phí vượt trội, cải thiện độ chính xác và tính cập nhật thời gian thực của AI, xử lý được phản hồi chất lượng của khách.
  - ⚠️ *Đánh đổi:* Phải lập trình thêm logic tính TTL động và API tiếp nhận feedback từ UI.

---

## ADR-002 - Cơ chế Model Fallback & Retry cho cuộc gọi AWS Bedrock
- **Trạng thái:** ~~Chấp nhận~~ → **Thay thế bởi ADR-004** (Superseded)
- **Ngày:** 2026-07-08 (thay thế: 2026-07-09)
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability
- **Lưu ý:** ⚠️ ADR này đã bị **thay thế bởi ADR-004** (Hybrid Task-Specific Routing). Các model ID Claude 3.0 (`anthropic.claude-3-sonnet-20240229-v1:0`, `anthropic.claude-3-haiku-20240307-v1:0`) đã bị AWS đánh dấu Legacy và từ chối truy cập. Xem ADR-004 để biết model routing mới.
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability
- **Bối cảnh:** 
  Các cuộc gọi API đến AWS Bedrock (sử dụng model chính `Claude 3.0 Sonnet`) có thể bị lỗi ngắt quãng, timeout mạng hoặc trả về lỗi Rate Limit (429) trong giờ cao điểm, gây mất tính năng tóm tắt review hoặc treo trang storefront.
- **Quyết định:** 
  Triển khai cơ chế Model Fallback Routing tự động trên Reviews Service:
  - **Model chính:** `anthropic.claude-3-sonnet-20240229-v1:0` (Claude 3 Sonnet).
  - **Model dự phòng (Fallback):** `anthropic.claude-3-haiku-20240307-v1:0` (Claude 3 Haiku).
  - **Timeout:** Giới hạn 5.0 giây cho mỗi cuộc gọi Sonnet.
  - **Retry limit:** Thử lại tối đa 2 lần. Nếu vẫn lỗi hoặc timeout, tự động chuyển hướng request sang gọi Claude 3 Haiku.
- **Phương án khác đã cân:**
  - *Option A - Không sử dụng Fallback (Chỉ hiển thị thông báo lỗi):* Trải nghiệm người dùng kém, tính năng tóm tắt reviews trống trơn.
  - *Option B - Sử dụng GPT-4o-mini làm backup:* Cần quản lý thêm API Key của OpenAI phức tạp và không an toàn hơn dùng IAM role của Bedrock sẵn có trên AWS.
- **Cost Δ:** $0 phát sinh cố định. Chi phí gọi Haiku chỉ bằng 1/10 so với Sonnet, giúp giảm chi tiêu Bedrock khi hệ thống gặp lỗi.
- **Ảnh hưởng SLO:** Đảm bảo độ sẵn sàng của tính năng reviews đạt **> 99.9%** kể cả khi dịch vụ Sonnet bị quá tải.
- **Rollback:** Cơ chế fallback được đóng gói trực tiếp trong mã nguồn của product-reviews. Để tắt hoặc điều chỉnh model ID, cập nhật qua các biến ENV cấu hình pod (`LLM_MAIN_MODEL`, `LLM_FALLBACK_MODEL`).
- **Hệ quả:**
  - ✅ *Lợi ích:* Hệ thống cực kỳ bền bỉ (resilient), bảo vệ luồng xem sản phẩm của người dùng.
  - ⚠️ *Đánh đổi:* Chất lượng tóm tắt của Haiku kém hơn một chút so với Sonnet (tỷ lệ tóm tắt đầy đủ giảm khoảng 10%), nhưng vẫn đảm bảo đúng sự thật.

---

## ADR-003 - Giải quyết Xung đột Eviction Policy trên cụm Valkey dùng chung
- **Trạng thái:** Chấp nhận (Accepted - Quyết định chọn Option 1)
- **Ngày:** 2026-07-08
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability / Cost Optimization
- **Bối cảnh:** 
  CTO yêu cầu dùng chung cụm Valkey `valkey-cart` cho cả Shopping Cart và Reviews Cache để tiết kiệm chi phí (ngân sách AWS < $300/tuần). Tuy nhiên, nếu cấu hình eviction policy là `allkeys-lru`, Valkey sẽ xóa nhầm giỏ hàng của người dùng khi bộ nhớ đầy do cache review phình to. Dù chuyển sang `volatile-lru`, do Cart trong code C# cũng có TTL 60m, giỏ hàng vẫn có nguy cơ bị trục xuất dưới áp lực RAM cao.
- **Quyết định (Option 1):** 
  - **Valkey Configuration:** Thiết lập eviction policy của cụm Valkey thành `volatile-lru`.
  - **Mã nguồn Cart (C#):** Loại bỏ hoàn toàn dòng lệnh `KeyExpireAsync(userId, ...)` cho giỏ hàng trong `ValkeyCartStore.cs` để biến key giỏ hàng thành vĩnh viễn (non-volatile), giúp giỏ hàng miễn nhiễm 100% trước cơ chế tự động eviction của Valkey.
  - **Quản lý bộ nhớ:** Viết một script CronJob chạy ngầm vào 2h sáng hằng ngày để quét (`SCAN`) và xóa chủ động các giỏ hàng không hoạt động trên 30 ngày.
- **Phương án khác đã cân:**
  - *Option 2 - Tách biệt cụm Valkey:* Cụm Cache dùng `allkeys-lru`, cụm Cart dùng `noeviction`. Đây là AWS Best Practice nhưng bị loại vì tốn thêm chi phí hạ tầng cố định (~$30/tuần), vi phạm ngân sách $300/tuần.
  - *Option 3 - Write-Through sang PostgreSQL:* Đồng bộ giỏ hàng xuống PostgreSQL để khôi phục khi Valkey bị xóa. Bị loại vì thời gian triển khai 1 tuần quá ngắn, rủi ro làm chậm luồng Checkout.
  - *Option 4 - Chỉ giám sát và nâng RAM:* Chỉ dựa vào Prometheus cảnh báo RAM và auto-scale. Bị loại vì mang tính thụ động, giỏ hàng vẫn bị xóa trước khi hạ tầng kịp scale-up.
- **Cost Δ:** $0 phát sinh cố định. Giữ nguyên chi phí cũ của cụm Valkey dùng chung.
- **Ảnh hưởng SLO:** Đảm bảo tỷ lệ Checkout thành công &ge; 99.0% và loại bỏ hoàn toàn sự sự cố mất giỏ hàng (INC-2) do cache review tranh chấp RAM.
- **Hệ quả:**
  - ✅ *Lợi ích:* Giải quyết triệt để rủi ro mất giỏ hàng mà không tốn thêm bất kỳ chi phí hạ tầng nào.
  - ⚠️ *Đánh đổi:* Phải duy trì và giám sát thêm một CronJob dọn rác giỏ hàng cũ vào ban đêm để tránh memory leak.

---

## ADR-004 - Định tuyến Model LLM lai theo Tác vụ (Hybrid Task-Specific Routing) cho Đơn Vùng (Single-Region)
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Cost Optimization / Performance Efficiency / Reliability
- **Bối cảnh:** 
  Việc sử dụng đơn độc một model Claude 3.5 Sonnet cho tất cả các tác vụ AI (tóm tắt review và trợ lý chat) gây quá tải chi phí token ([$3.00/$15.00 per 1M tokens](https://aws.amazon.com/bedrock/pricing/)), dễ vỡ quỹ ngân sách $300/tuần khi chịu tải test. Ngược lại, nếu chỉ dùng các model giá rẻ như Amazon Nova Lite cho cả hai tác vụ, chất lượng hội thoại phức tạp và độ chính xác gọi tool (Function Calling) của Shopping Copilot sẽ bị sụt giảm nặng, dễ gây ra hành vi không mong muốn (excessive agency).
  - **Benchmarks:** Dữ liệu TTFT và throughput lấy từ [Artificial Analysis Leaderboard](https://artificialanalysis.ai/leaderboards/models) cho Bedrock On-Demand. Chi phí từ [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/).
  - **Case Study tham khảo:** [Mercari — Model Routing Phân Tầng](https://engineering.mercari.com/) | [Shopify — Cross-Region Failover](https://shopify.engineering/)
  - **Vùng triển khai:** Đơn vùng `us-east-1` (xác nhận từ ECR Registry `265808836805.dkr.ecr.us-east-1.amazonaws.com`)
- **Quyết định:** 
  Triển khai mô hình định tuyến lai dựa trên đặc thù tác vụ (Task-Specific Routing) trong đơn vùng (Single-Region):
  - **Tác vụ Reviews Summary (Tải cực cao, độ phức tạp thấp):**
    - Định tuyến chính (Primary): Amazon Nova Lite (`amazon.nova-lite-v1:0`). TTFT cực nhanh (~0.4s theo [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models)), chi phí cực rẻ ([$0.06/$0.24 per 1M tokens](https://aws.amazon.com/bedrock/pricing/)).
    - Dự phòng (Fallback): Amazon Nova Micro (`amazon.nova-micro-v1:0`) và cuối cùng là Mock Summary.
    - Timeout: Giảm xuống **2.0 giây (2000ms)** để bảo vệ SLO của trang storefront.
  - **Tác vụ Shopping Copilot (Tải thấp, độ phức tạp cao, cần độ chính xác gọi tool tuyệt đối):**
    - Định tuyến chính (Primary): Claude 3.5 Sonnet v2 (`anthropic.claude-3-5-sonnet-20241022-v2:0`).
    - Dự phòng (Fallback): Claude 3.5 Haiku (`anthropic.claude-3-5-haiku-20241022-v1:0`).
    - Timeout: Giới hạn **5.0 giây (5000ms)**.
- **Phương án khác đã cân:**
  - *Option A - Sử dụng thuần Claude (A1):* Chất lượng tốt nhất nhưng bị loại bỏ vì chi phí token vượt ngân sách $300/tuần khi Locust test.
  - *Option B - Sử dụng thuần Amazon Nova (A2):* Tiết kiệm nhất nhưng bị loại do khả năng gọi tool tiếng Việt của Nova chưa đủ tin cậy cho Copilot Agent.
- **Cost Δ:** Tiết kiệm khoảng **95% chi phí token** của luồng Reviews Summary, giúp duy trì tổng chi tiêu LLM toàn hệ thống ở mức cực thấp (~$5 - $10/tuần) ngay cả khi bị test tải nặng. Nguồn so sánh giá: [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/).
- **Ảnh hưởng SLO:**
  - Giữ vững p95 latency storefront < 1.0s — nhờ thời gian xử lý của Nova Lite cực kỳ ngắn (~0.4s theo [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models)).
  - Bảo vệ tỷ lệ Checkout thành công ≥ 99% nhờ độ chính xác cao của Claude Sonnet 3.5.
- **Hệ quả:**
  - ✅ *Lợi ích:* Cân bản hoàn hảo giữa chi phí, tốc độ và độ chính xác của AI.
  - ⚠️ *Đánh đổi:* Phải duy trì cấu hình và quản lý biến môi trường của 4 model Bedrock khác nhau trong code.

---

## ADR-005 - Chiến lược Resilience & Retry cho cuộc gọi LLM API
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability / Performance Efficiency
- **Bối cảnh:** 
  Các cuộc gọi API AWS Bedrock (đặc biệt là Claude 3.5 Sonnet và Amazon Nova Lite) có thể gặp lỗi ngắt quãng (429 Rate Limit, 500 Internal Error, timeout mạng). Nếu chỉ retry đơn thuần không có backoff hoặc không có dynamic deadline protection, hệ thống sẽ gặp hiện tượng cascading timeout kéo dài thời gian phản hồi trang chi tiết sản phẩm, vi phạm SLO p95 < 1.0s. Hơn nữa, sự cố do BTC bơm qua flagd (như `llmRateLimitError`) cần được xử lý tự động để hệ thống tự hồi phục.
- **Quyết định:** 
  Triển khai 5-layer resilience stack:
  1. **SDK Client Adaptive Retry Mode:** Sử dụng cấu hình retry thích ứng mặc định của AWS SDK.
  2. **Exponential Backoff & Full Jitter:** Thử lại với thời gian trễ tăng dần kết hợp ngẫu nhiên hóa (jitter) để tránh thundering herd, chỉ lọc và retry trên các mã lỗi HTTP 429, 500, 503 hoặc timeout.
  3. **Bulkhead Isolation:** Giới hạn tối đa 10 luồng gọi Bedrock đồng thời bằng `asyncio.Semaphore` để tránh làm cạn kiệt tài nguyên xử lý của pod.
  4. **Context-Aware Dynamic Deadlines:** Điều chỉnh timeout động của cuộc gọi Bedrock dựa trên thời gian xử lý còn lại của request so với SLO p95 (ví dụ: nếu trang sản phẩm còn 800ms trước khi trễ hạn, timeout của LLM sẽ tự động rút ngắn tương ứng).
  5. **Flag-Aware Circuit Breaker:** Tự động chuyển đổi trạng thái Circuit Breaker sang OPEN ngay khi nhận diện cờ `llmRateLimitError` từ flagd ở vị trí ON, chuyển hướng request sang Mock Summary hoặc model dự phòng mà không cần đợi lỗi thật xảy ra.
- **Phương án khác đã cân:**
  - *Option A - Chỉ sử dụng SDK retry mặc định (Default Mode):* Bị loại vì không có jitter gây ra hiện tượng thundering herd và không hỗ trợ dynamic deadlines.
  - *Option B - Không giới hạn luồng (No Bulkhead):* Khi Bedrock phản hồi chậm, số lượng request tăng lên làm cạn kiệt CPU/RAM của pod, gây ra sự cố cascading crash.
- **Cost Δ:** $0 phát sinh cố định. Giảm thiểu chi phí token gọi thừa khi Bedrock đang quá tải.
- **Ảnh hưởng SLO:** Bảo vệ SLO p95 < 1.0s, duy trì tỷ lệ Availability > 99.9% kể cả khi bị BTC ép tải hoặc kích hoạt lỗi qua flagd.
- **Hệ quả:**
  - ✅ *Lợi ích:* Tăng cường đáng kể khả năng tự phục hồi, chống thundering herd, giảm tỷ lệ timeout của storefront xuống sát 0%.
  - ⚠️ *Đánh đổi:* Phải lập trình và bảo trì thư viện bọc (wrapper) cuộc gọi Bedrock phức tạp hơn.

---

## ADR-006 - Cơ chế Guardrail & Safety cho Tầng AI (Shopping Copilot & Product Reviews)
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Security / Reliability
- **Bối cảnh:** 
  AI_FEATURE.md §2.A và §2.B yêu cầu hệ thống phải an toàn trước các cuộc tấn công Prompt Injection nhúng trong reviews sản phẩm, ngăn lộ thông tin nhạy cảm (PII), chặn lộ system prompt, và đặc biệt là ngăn chặn hành vi excessive agency (tự ý xóa giỏ hàng hoặc tự ý thanh toán đặt hàng của trợ lý Shopping Copilot).
- **Quyết định:** 
  Triển khai hệ thống bảo mật 3 lớp (AI Guardrails):
  1. **Input Guardrail:** Lọc sạch (sanitization) và phân tích nội dung reviews/user prompt qua regex filter và LLM-based classifier trước khi đưa vào context để chặn Prompt Injection.
  2. **Output Guardrail:** Lọc và che giấu (redact) thông tin nhạy cảm (PII như email, phone, credit card) cùng với bộ lọc phát hiện rò rỉ system prompt (system prompt leakage detector).
  3. **Tool Execution Authorization (Confirmation Gate UI Protocol):**
     - Phân loại tools thành 3 Tier:
       - *Tier 1 (Read-only):* Tự động thực thi (`search_products`, `get_product_reviews`, `get_cart`, `list_recommendations`, `convert_currency`, `get_shipping_quote`).
       - *Tier 2 (Write/Modify):* Cần xác nhận từ người dùng qua cấu trúc JSON payload (`add_to_cart`). Agent không được tự thực thi mà phải trả về JSON request confirmation. Frontend Streamlit/Storefront sẽ render nút bấm UI xác nhận.
       - *Tier 3 (Critical/Blocked):* Chặn tuyệt đối (`empty_cart`, `place_order`, `ship_order`). AI Agent không bao giờ được phép gọi các rpc này để triệt tiêu hoàn toàn Excessive Agency.
     - Tích hợp Idempotency Key và Expiry Epoch cho mỗi request xác nhận để ngăn chặn việc gửi trùng lặp lệnh ghi.
- **Phương án khác đã cân:**
  - *Option A - Chỉ chặn bằng System Prompt:* Bị loại vì dễ bị bypass qua các kỹ thuật jailbreak/prompt injection tinh vi (như sự cố Replit AI Agent xóa database production tháng 7/2025).
  - *Option B - Xác nhận tất cả các thao tác (kể cả đọc):* Bị loại vì gây ra trải nghiệm người dùng cực kỳ phiền toái (approval spam), làm giảm mức độ tương tác của khách hàng.
- **Cost Δ:** $0 phát sinh cố định. Tiết kiệm chi phí vận hành do tránh được các đơn hàng rác hoặc hành động ghi không mong muốn.
- **Ảnh hưởng SLO:** Bảo vệ tỷ lệ thanh toán thành công và độ chính xác của giỏ hàng luôn ở mức 100%. Triệt tiêu hoàn toàn rủi ro rò rỉ PII của khách hàng.
- **Hệ quả:**
  - ✅ *Lợi ích:* Đạt tiêu chuẩn an toàn cao nhất của OWASP LLM09:2025 (Excessive Agency). Loại bỏ 100% rủi ro agent tự ý thanh toán hoặc xóa sạch giỏ hàng.
  - ⚠️ *Đánh đổi:* Frontend và Backend phải tích hợp chung giao thức JSON Confirmation, tăng thời gian làm việc nhóm CDO & AIO.
