# Decision Log (ADR) - TF1 / AI Team (AIO03)

---

## ADR-001 - Sử dụng Valkey Caching cho dịch vụ Product Reviews  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-08
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Cost Optimization / Performance Efficiency
- **Bối cảnh:** 
  Trang chi tiết sản phẩm có một trợ lý AI tóm tắt/hỏi đáp review. **Phạm vi cần nói chính xác:** trợ lý này *không* chạy khi tải trang — `ProductReviews.tsx` chỉ gọi rpc `AskProductAIAssistant` khi khách bấm nút *Ask AI*/quick prompt, còn lúc render trang chỉ có `GetProductReviews` đọc thẳng PostgreSQL. Do đó cuộc gọi Bedrock **không nằm trên đường render và không tính vào SLO storefront p95 < 1s** (xem `03_specs/fallback_retry.md` và ADR-004). Vấn đề thật sự là: mỗi lần bấm nút, nếu không cache thì (a) trả tiền token lặp lại cho cùng một sản phẩm có review tĩnh, và (b) khách phải chờ ~2–4s (ước benchmark, chờ đo thật) trong khi đang nhìn màn hình chờ trợ lý trả lời.
- **Quyết định:** 
  Tận dụng cụm cache Valkey sẵn có (`valkey-cart` chạy trên cổng `6379`) để lưu trữ các bản tóm tắt review dưới dạng JSON.
  - **Điểm gắn cache:** `AskProductAIAssistant` — đây là rpc duy nhất gọi LLM. `GetProductReviews` chỉ đọc thẳng PostgreSQL nên cache ở đó không tiết kiệm token nào.
  - **Cache Key Format:** `reviews:summary:{product_id}:{model_ver}:{prompt_ver}:{content_fp}` — content-addressed (xem dưới).
  - **Bypass Flag:** Sử dụng OpenFeature flag `llmReviewsCacheEnabled` (kiểm soát qua flagd) để tắt cache nhanh khi cần kiểm thử hoặc cập nhật.
  - **Chiến lược làm mới cache — Content-Addressed Invalidation [chốt 13/07]:** cơ chế chuẩn thế giới (Rails `cache_key`/HTTP ETag) — key là hàm của STATE object, review đổi ⇒ key đổi ⇒ **miss tự nhiên, ZERO staleness**, không invalidate thủ công, không đoán TTL.
    1. **content_fp** = `md5(COUNT || MAX(id) || md5(content))[:12]` từ 1 aggregate query (`fetch_reviews_fingerprint`). Thêm/xoá/sửa review đều đổi fp. Chi tiết + đánh đổi: `03_specs/valkey_caching.md` §6.
    2. **Versioned key** `model_ver:prompt_ver` (derive env model + hash prompt): đổi model/prompt ⇒ key đổi. Kết hợp fp thành khoá đầy đủ theo mọi chiều state.
    3. **TTL 7d = GC backstop thuần** (~~động~~ + ~~tĩnh-chống-outdate~~ đều bỏ): dọn key fingerprint cũ, không còn vai trò chống outdate — đó là việc của content_fp.
  - **Vì sao content-addressed thay vì dynamic-TTL hay write-invalidation thủ công:** dynamic-TTL đoán độ tươi (không self-heal); write-invalidation phụ thuộc write-path nhớ gọi (dễ quên → bug staleness). Content-fingerprint **self-healing** — đúng ngay cả khi có đường ghi `AddReview` (TF1-55/56) lẫn khi chưa có, không cần code invalidate riêng. Đây là lý do nó là mặc định thay vì "không làm gì vì data tĩnh".
- **Phương án khác đã cân:**
  - *Option A - Sử dụng Amazon ElastiCache (Redis managed):* Độ bền cao và bảo mật hơn, nhưng tăng chi phí cố định tối thiểu ~$30/tuần **tiền mặt thật**. Con số này **không vi phạm** trần $300/tuần (nó chiếm 10%) — lý do loại là *đánh đổi không xứng*: cụm Valkey in-cluster của CDO đã sẵn có, đáp ứng đúng nhu cầu cache một bản tóm tắt JSON có thể tái sinh bất cứ lúc nào từ LLM. Trả 10% ngân sách hạ tầng để mua độ bền cho dữ liệu vốn dĩ **disposable** là chi sai chỗ; 10% đó có giá trị hơn nhiều khi để cho CDO dùng vào EKS node. Quyết định: Bỏ qua và dùng Valkey in-cluster.
  - *Option B - Sử dụng thuật toán Eviction LFU thay vì LRU:* Bị loại bỏ vì LFU dễ bị Cache Pollution bởi các sản phẩm cũ từng rất hot, không linh hoạt bằng LRU đối với trend mua sắm thay đổi liên tục.
- **Cost Δ:** *(⚠️ phụ thuộc GIẢ ĐỊNH cache-hit-rate — CHƯA ĐO)* nếu đạt ~85–90% cache hit thì chi phí Bedrock giảm từ **~$9.66/tuần xuống ~$0.97/tuần** (mẫu số 10k lời gọi/ngày). **Con số 90% là mô hình, chưa đo** — hit rate thật phụ thuộc pattern truy cập (10 sản phẩm + versioned key); đo thật khi có tải EKS (TF1-67/71). Dù hit rate thấp hơn nhiều, chi phí Nova vẫn <$10/tuần nên **kết luận "đạt" không nhạy với con số này** — đó là điểm mạnh. ~~Dynamic TTL tiết kiệm thêm ~40%~~ **[GỠ 12/07: dynamic TTL đã bỏ — data tĩnh; con số 40% cũng chưa từng đo].** Khoản tiết kiệm token không phải lý do chính đáng để làm cache (xem Ảnh hưởng SLO) — lý do là latency.
- **Ảnh hưởng SLO:** Không đụng tới SLO storefront p95 < 1s (cuộc gọi LLM nằm ngoài đường render trang). Giá trị thật nằm ở **độ trễ phản hồi của trợ lý AI: ~2–4s (ước benchmark, chờ đo) → < 50ms khi cache hit** — tức là trải nghiệm tại đúng khoảnh khắc khách đang chờ. Tóm tắt review là **best-effort, không SLA cứng** theo `onboarding/SLO.md`; ràng buộc SLO duy nhất áp lên nó là *không được hiển thị tóm tắt sai lệch*, và **content-addressed cache key** (fingerprint nội dung review nhúng vào key — chuẩn Rails cache_key/ETag) chính là cơ chế bảo vệ điều đó: review đổi → key đổi → miss tự nhiên, ZERO staleness. TTL 7d chỉ còn là GC. Xem `03_specs/valkey_caching.md` §6.
- **Rollback:** Chuyển đổi flag `llmReviewsCacheEnabled` sang `false` để bypass cache và gọi trực tiếp Bedrock. Nếu Valkey bị sập, Reviews service tự động bỏ qua cache và log error.
- **Hệ quả:**
  - ✅ *Lợi ích:* Tiết kiệm chi phí vượt trội, cải thiện độ chính xác và tính cập nhật thời gian thực của AI, xử lý được phản hồi chất lượng của khách.
  - ⚠️ *Đánh đổi (đã lỗi thời — TTL động đã gỡ):* TTL phẳng 7d, không còn logic tính động.

---

## ADR-002 - Cơ chế Model Fallback & Retry cho cuộc gọi AWS Bedrock  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** ~~Chấp nhận~~ → **Thay thế bởi ADR-004** (Superseded)
- **Ngày:** 2026-07-08 (thay thế: 2026-07-09)
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability
- **Lưu ý:** ⚠️ ADR này đã bị **thay thế bởi ADR-004** (Hybrid Task-Specific Routing). Các model ID Claude 3.0 (`anthropic.claude-3-sonnet-20240229-v1:0`, `anthropic.claude-3-haiku-20240307-v1:0`) đã bị AWS đánh dấu Legacy và từ chối truy cập. Xem ADR-004 để biết model routing mới. Nội dung bên dưới **giữ nguyên làm bản ghi lịch sử**, không phản ánh thiết kế hiện hành.
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

## ADR-003 - Giải quyết Xung đột Eviction Policy trên cụm Valkey dùng chung  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** Chấp nhận (Accepted - Quyết định chọn Option 1)
- **Ngày:** 2026-07-08
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability / Cost Optimization
- **Bối cảnh:** 
  CTO yêu cầu dùng chung cụm Valkey `valkey-cart` cho cả Shopping Cart và Reviews Cache để tiết kiệm chi phí (ngân sách AWS < $300/tuần). Tuy nhiên, nếu cấu hình eviction policy là `allkeys-lru`, Valkey sẽ xóa nhầm giỏ hàng của người dùng khi bộ nhớ đầy do cache review phình to. Dù chuyển sang `volatile-lru`, do Cart trong code C# **khi đó** còn đặt TTL 60m (`KeyExpireAsync`), giỏ hàng vẫn có nguy cơ bị trục xuất dưới áp lực RAM cao.
- **Quyết định (Option 1):** 
  - **Valkey Configuration:** Thiết lập eviction policy của cụm Valkey thành `volatile-lru`.
  - **Mã nguồn Cart (C#):** Loại bỏ hoàn toàn dòng lệnh `KeyExpireAsync(userId, ...)` cho giỏ hàng trong `ValkeyCartStore.cs` để biến key giỏ hàng thành vĩnh viễn (non-volatile), giúp giỏ hàng miễn nhiễm 100% trước cơ chế tự động eviction của Valkey.
  - **Quản lý bộ nhớ:** Viết một script CronJob chạy ngầm vào 2h sáng hằng ngày để quét (`SCAN`) và xóa chủ động các giỏ hàng không hoạt động trên 30 ngày.
  - ⚠️ **Cần CDO đồng ký (co-sign):** `ValkeyCartStore.cs` thuộc quyền sở hữu của nhóm CDO, và đúng vùng code từng gây sự cố **INC-2**. Quyết định này đã được triển khai (TF1-54, `ValkeyCartStore.cs:174,199`) **trước khi có chữ ký CDO** — cần bổ sung phê duyệt hồi tố.
- **Trạng thái triển khai:** ✅ Đã áp dụng. `ValkeyCartStore.cs:174` và `:199` đã comment out `KeyExpireAsync`. Cart hiện **không còn TTL**.
- **Phương án khác đã cân:**
  - *Option 2 - Tách biệt cụm Valkey (pod thứ hai in-cluster):* Cụm Cache dùng `allkeys-lru`, cụm Cart dùng `noeviction`. Đây là AWS Best Practice và **chi phí thực tế ≈ $0** — Valkey đang chạy là một pod in-cluster (`values.yaml:939-967`, `replicas: 1`, `resources.limits.memory: 20Mi`), không phải ElastiCache; pod thứ hai chỉ tốn thêm 20Mi trên node group sẵn có (3× t3.medium) và Terraform không hề khai báo ElastiCache. **Đính chính:** con số "~$30/tuần" từng ghi ở đây là chi phí của **ElastiCache managed** (xem ADR-001 Option A) và đã bị áp nhầm sang một phương án in-cluster. Lý do loại thật sự: Option 1 đã được triển khai và merge; revert để tách cụm đồng nghĩa chạm code Cart của CDO lần thứ hai vào đúng vùng INC-2, chi phí rủi ro lớn hơn lợi ích cách ly. **Giữ Option 2 làm phương án dự phòng nếu áp lực RAM tái diễn.**
  - *Option 3 - Write-Through sang PostgreSQL:* Đồng bộ giỏ hàng xuống PostgreSQL để khôi phục khi Valkey bị xóa. Bị loại vì thời gian triển khai 1 tuần quá ngắn, rủi ro làm chậm luồng Checkout.
  - *Option 4 - Chỉ giám sát và nâng RAM:* Chỉ dựa vào Prometheus cảnh báo RAM và auto-scale. Bị loại vì mang tính thụ động, giỏ hàng vẫn bị xóa trước khi hạ tầng kịp scale-up.
- **Cost Δ:** $0 phát sinh cố định. Giữ nguyên chi phí cũ của cụm Valkey dùng chung.
- **Ảnh hưởng SLO:** Đảm bảo tỷ lệ Checkout thành công &ge; 99.0% và loại bỏ hoàn toàn sự sự cố mất giỏ hàng (INC-2) do cache review tranh chấp RAM.
- **Hệ quả:**
  - ✅ *Lợi ích:* Giải quyết triệt để rủi ro mất giỏ hàng mà không tốn thêm bất kỳ chi phí hạ tầng nào.
  - ⚠️ *Đánh đổi:* Phải duy trì và giám sát thêm một CronJob dọn rác giỏ hàng cũ vào ban đêm để tránh memory leak.

### Addendum 14/07/2026 — hạ tầng đổi: ElastiCache Valkey managed (đóng J1)

Bối cảnh của ADR này đã thay đổi do CDO migrate hạ tầng cache:

- **Valkey giờ là ElastiCache managed**, không còn pod in-cluster: `terraform/modules/elasticache/main.tf` (replication group `valkey` 7.2, TLS + auth token qua Secrets Manager, automatic failover). Cart và product-reviews cùng trỏ `master.ecommerce-dev-valkey.7ylfic.use1.cache.amazonaws.com:6379` (`values.yaml:305,781`); pod `valkey-cart` in-cluster đã `enabled: false`.
- **TTL cart 60m đã khôi phục** (`ValkeyCartStore.cs:188,216`) — đảo ngược Quyết định Option 1 ở trên về phía an toàn.
- **Hệ quả cho rủi ro J1 (CRITICAL):** kịch bản kubelet OOMKill do cgroup limit 20Mi **không còn tồn tại** — bộ nhớ giờ theo node ElastiCache (≥ ~500MB với cache.t4g.micro), headroom lớn hơn ~25 lần. Soak test đo time-to-OOM in-cluster **không còn cần thiết**; thay bằng giám sát CloudWatch `BytesUsedForCache` + `Evictions`.
- **Điểm đã chốt với CDO (Co-signed):**
  1. Terraform sẽ set `parameter_group_name` dùng `maxmemory-policy` là `volatile-lru` cho cart, bảo vệ giỏ hàng.
  2. Cart key được khôi phục TTL 60m (volatile) nhưng an toàn do dung lượng RAM dồi dào. Có CloudWatch alarm cho `Evictions > 0`.
  3. Quyết định **Tách instance cache reviews**: CDO đã phê duyệt tạo instance Valkey thứ hai cho Reviews. Chi phí tăng thêm ~$9/tháng t4g.micro nhưng cô lập hoàn toàn (bulkhead) áp lực RAM giữa hai domain.
- **Trạng thái co-sign:** ✅ CDO đã co-sign và xác nhận kế hoạch tách cụm. (Hoàn thành TF1-68).

---

## ADR-004 - Định tuyến Model LLM lai theo Tác vụ (Hybrid Task-Specific Routing) cho Đơn Vùng (Single-Region)  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Cost Optimization / Performance Efficiency / Reliability
- **Bối cảnh:** 
  Việc sử dụng các model của Anthropic như Claude 3.5 Sonnet cho các tác vụ AI gây phát sinh chi phí tiền mặt thật trên AWS Marketplace, không cấn trừ được bằng Credit khuyến mại của AWS (có thể làm vỡ trần ngân sách tiền mặt của Task Force). Ngược lại, nếu chỉ dùng các model giá rẻ như Amazon Nova Lite cho cả hai tác vụ, chất lượng hội thoại phức tạp và độ chính xác gọi tool (Function Calling) của Shopping Copilot sẽ bị sụt giảm nặng, dễ gây ra hành vi không mong muốn (excessive agency).
  - **Benchmarks:** Dữ liệu TTFT và throughput lấy từ [Artificial Analysis Leaderboard](https://artificialanalysis.ai/leaderboards/models) cho Bedrock On-Demand. Chi phí từ [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/).
  - **Case Study tham khảo:** [Mercari — Model Routing Phân Tầng](https://engineering.mercari.com/) | [Shopify — Cross-Region Failover](https://shopify.engineering/)
  - **Vùng triển khai:** Đơn vùng `us-east-1` (xác nhận từ ECR Registry `265808836805.dkr.ecr.us-east-1.amazonaws.com`)
- **Quyết định:** 
  Triển khai mô hình định tuyến lai dựa trên đặc thù tác vụ (Task-Specific Routing) trong đơn vùng (Single-Region):
  - **Tác vụ Reviews Summary (Tải cực cao, độ phức tạp thấp):**
    - Định tuyến chính (Primary): Amazon Nova Lite (`amazon.nova-lite-v1:0`). TTFT ~1.04s, ~175.7 tok/s theo [Artificial Analysis](https://artificialanalysis.ai/models/nova-lite) *(sửa 12/07 — bản đầu ghi 0.4s sai nguồn)*, chi phí cực rẻ ([$0.06/$0.24 per 1M tokens](https://aws.amazon.com/bedrock/pricing/)).
    - Dự phòng (Fallback): Amazon Nova Micro (`amazon.nova-micro-v1:0`) và cuối cùng là Mock Summary.
    - Timeout: **4.0 giây (4000ms)** — chốt theo P95 đo thật 15/07/2026 (`measure_bedrock_latency.py`, Reviews Lite flow P95 3.969s). Đặt thấp hơn sẽ cắt ngang đuôi phân phối latency, huỷ đúng lúc sắp thành công rồi retry lại từ đầu: trả tiền token nhiều lần cho 0 kết quả và dội tải ngược lên Bedrock đúng lúc nó đang chậm. Đổi lại **không được gì**, vì tóm tắt AI là **best-effort, không SLA cứng** (`SLO.md`) và chỉ chạy khi khách bấm nút, không chặn render trang → không tính vào SLO storefront p95 < 1s.
  - **Tác vụ Shopping Copilot (Tải thấp, độ phức tạp cao, cần độ chính xác gọi tool tuyệt đối):**
    - Định tuyến chính (Primary): Amazon Nova Pro (`amazon.nova-pro-v1:0`). Đảm bảo độ chính xác gọi tool xuất sắc và chi phí được cấn trừ hoàn toàn 100% bằng AWS Credits (tiền mặt thật = $0).
    - Dự phòng (Fallback): Amazon Nova Lite (`amazon.nova-lite-v1:0`).
    - Timeout: Giới hạn **5.7 giây (5700ms)** theo P95 tool loop đo thật; fallback Nova Lite **2.5 giây**.
- **Phương án khác đã cân:**
  - *Option A - Sử dụng Claude (A1):* Bị loại bỏ hoàn toàn vì Claude thuộc AWS Marketplace, bắt buộc trả bằng tiền mặt thật, không được trừ vào credit. Quyết định: Loại bỏ Claude để đưa chi phí tiền mặt về $0.
  - *Option B - Sử dụng thuần Amazon Nova Lite (A2):* Tiết kiệm nhất nhưng bị loại do khả năng gọi tool tiếng Việt của Nova Lite chưa đủ tin cậy cho Copilot Agent so với Nova Pro.
- **Cost Δ:** Tiết kiệm khoảng **100% chi phí tiền mặt thật** cho toàn bộ hệ thống LLM nhờ việc chuyển dịch hoàn toàn sang các mô hình First-party của Amazon (Nova Lite, Nova Micro, Nova Pro) được cấn trừ hoàn toàn qua AWS Credits.
- **Ảnh hưởng SLO:**
  - **Không tác động trực tiếp lên p95 latency storefront < 1.0s**, vì cả hai luồng LLM đều nằm ngoài đường render trang (Reviews chạy khi bấm *Ask AI*; Copilot là panel hội thoại riêng). Độ trễ Nova Lite (~2.2s/call điển hình theo benchmark, chờ đo P95 thật) chỉ ảnh hưởng *độ trễ cảm nhận của trợ lý AI*, không phải p95 của storefront.
  - Bảo vệ tỷ lệ Checkout thành công ≥ 99% nhờ độ chính xác gọi tool cao của Amazon Nova Pro — Copilot có thể ghi vào giỏ hàng, nên gọi sai tool là rủi ro trực tiếp lên luồng ra tiền.
- **Hệ quả:**
  - ✅ *Lợi ích:* Cân bản hoàn hảo giữa chi phí, tốc độ và độ chính xác của AI.
  - ⚠️ *Đánh đổi:* Phải duy trì cấu hình và quản lý biến môi trường của 4 model Bedrock khác nhau trong code.

---

## ADR-005 - Chiến lược Resilience & Retry cho cuộc gọi LLM API  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Reliability / Performance Efficiency
- **Bối cảnh:** 
  Các cuộc gọi API AWS Bedrock (đặc biệt là Amazon Nova Pro và Amazon Nova Lite) có thể gặp lỗi ngắt quãng (429 Rate Limit, 500 Internal Error, timeout mạng). Bản thân cuộc gọi LLM nằm ngoài đường render trang nên **không trực tiếp** làm vỡ SLO p95 < 1.0s. Rủi ro thật là **gián tiếp**: pod `product-reviews` phục vụ đồng thời `AskProductAIAssistant` (gọi LLM, chậm) và `GetProductReviews` (đọc PostgreSQL, nằm trên đường render trang). Khi Bedrock chậm hoặc lỗi mà không có backoff, bulkhead và dynamic deadline, các cuộc gọi LLM treo sẽ cạn kiệt thread pool của pod và **kéo `GetProductReviews` sập theo — lúc đó SLO storefront p95 < 1.0s mới thật sự bị đe doạ.** Hơn nữa, sự cố do BTC bơm qua flagd (như `llmRateLimitError`) cần được xử lý tự động để hệ thống tự hồi phục.
- **Quyết định:** 
  Triển khai 5-layer resilience stack:
  1. **SDK Client Adaptive Retry Mode:** Sử dụng cấu hình retry thích ứng mặc định của AWS SDK.
  2. **Exponential Backoff & Full Jitter:** Thử lại với thời gian trễ tăng dần kết hợp ngẫu nhiên hóa (jitter) để tránh thundering herd, chỉ lọc và retry trên các mã lỗi HTTP 429, 500, 503 hoặc timeout.
  3. **Bulkhead Isolation:** Giới hạn tối đa 10 luồng gọi Bedrock đồng thời bằng `asyncio.Semaphore` để tránh làm cạn kiệt tài nguyên xử lý của pod.
  4. **Context-Aware Dynamic Deadlines:** Điều chỉnh timeout động của cuộc gọi Bedrock dựa trên thời gian xử lý còn lại của request so với SLO p95 (ví dụ: nếu trang sản phẩm còn 800ms trước khi trễ hạn, timeout của LLM sẽ tự động rút ngắn tương ứng).
  5. **Flag-Aware Circuit Breaker:** Tự động chuyển đổi trạng thái Circuit Breaker sang OPEN ngay khi nhận diện cờ `llmRateLimitError` từ flagd ở vị trí ON, chuyển hướng request sang Mock Summary hoặc model dự phòng mà không cần đợi lỗi thật xảy ra.
- **Trạng thái triển khai:** ⚠️ **Chưa có trong code — đây là quyết định thiết kế của Tuần 1, thực thi ở Tuần 2.** Tính đến `product_reviews_server.py` hiện tại: `bedrock_client` được khởi tạo trần (`:483`) không có `botocore.config.Config`, không có `Semaphore`, không có backoff/circuit breaker, và không có đường fallback sang Nova Micro. Đáng lưu ý, đường xử lý `llmRateLimitError` hiện tại (`:237-275`) làm **ngược** với layer 5: nó chủ động gọi mock để sinh lỗi 429 rồi trả thẳng thông báo lỗi cho khách, thay vì mở circuit breaker và fallback. Đóng khoảng cách này là hạng mục Tuần 2 (cần tạo task Jira; chưa có mã task tại thời điểm pitch).
- **Phương án khác đã cân:**
  - *Option A - Chỉ sử dụng SDK retry mặc định (Default Mode):* Bị loại vì không có jitter gây ra hiện tượng thundering herd và không hỗ trợ dynamic deadlines.
  - *Option B - Không giới hạn luồng (No Bulkhead):* Khi Bedrock phản hồi chậm, số lượng request tăng lên làm cạn kiệt CPU/RAM của pod, gây ra sự cố cascading crash.
- **Cost Δ:** $0 phát sinh cố định. Giảm thiểu chi phí token gọi thừa khi Bedrock đang quá tải.
- **Ảnh hưởng SLO:** Bảo vệ SLO storefront p95 < 1.0s **gián tiếp**, bằng cách ngăn các cuộc gọi LLM treo làm cạn thread pool của pod `product-reviews` và kéo theo `GetProductReviews` trên đường render trang. Giữ tính năng tóm tắt ở mức best-effort có suy giảm mềm (fallback → Mock Summary) thay vì trả lỗi cho khách, kể cả khi bị BTC ép tải hoặc kích hoạt lỗi qua flagd.
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
  *(Ghi chú: Toàn bộ bộ công cụ / tools mà Agent sử dụng (như search, cart, recommendations) đều là các thành phần Mở rộng [Extend] được nhóm tự định nghĩa và tích hợp riêng cho Copilot, vì BTC không cung cấp sẵn mã nguồn Agent trong base repo).*
- **Quyết định:** 
  Triển khai hệ thống bảo mật 3 lớp (AI Guardrails):
  1. **Input Guardrail:** Lọc sạch (sanitization) và phân tích nội dung reviews/user prompt qua regex filter và LLM-based classifier trước khi đưa vào context để chặn Prompt Injection.
  2. **Output Guardrail:** Lọc và che giấu (redact) thông tin nhạy cảm (PII như email, phone, credit card) cùng với bộ lọc phát hiện rò rỉ system prompt (system prompt leakage detector).
  3. **Tool Execution Authorization (Confirmation Gate UI Protocol):**
     - Phân loại tools thành 3 Tier:
       - *Tier 1 (Read-only):* Tự động thực thi. **[Core]** `search_products`, `get_product_reviews`, `get_cart` — ba tool này phục vụ trực tiếp 3 intent cốt lõi và được đặc tả ở `03_specs/shopping_copilot.md` §3. **[Extend]** `list_recommendations`, `convert_currency`, `get_shipping_quote` — chưa đặc tả, chỉ ghi nhận ý định.
       - *Tier 2 (Write/Modify):* Cần xác nhận từ người dùng qua cấu trúc JSON payload (**[Core]** `add_item_to_cart`). Agent không được tự thực thi mà phải trả về JSON request confirmation. Frontend Streamlit/Storefront sẽ render nút bấm UI xác nhận.
       - *Tier 3 (Critical/Blocked):* Chặn tuyệt đối (`empty_cart`, `place_order`, `ship_order`). AI Agent không bao giờ được phép gọi các rpc này để triệt tiêu hoàn toàn Excessive Agency.
     - Tích hợp Idempotency Key và Expiry Epoch cho mỗi request xác nhận để ngăn chặn việc gửi trùng lặp lệnh ghi.
- **Phương án khác đã cân:**
  - *Option A - Chỉ chặn bằng System Prompt:* Bị loại vì dễ bị bypass qua các kỹ thuật jailbreak/prompt injection tinh vi (như sự cố Replit AI Agent xóa database production tháng 7/2025).
  - *Option B - Xác nhận tất cả các thao tác (kể cả đọc):* Bị loại vì gây ra trải nghiệm người dùng cực kỳ phiền toái (approval spam), làm giảm mức độ tương tác của khách hàng.
- **Cost Δ:** $0 phát sinh cố định. Tiết kiệm chi phí vận hành do tránh được các đơn hàng rác hoặc hành động ghi không mong muốn.
- **Ảnh hưởng SLO:** Bảo vệ tỷ lệ thanh toán thành công và độ chính xác của giỏ hàng luôn ở mức 100%. Triệt tiêu hoàn toàn rủi ro rò rỉ PII của khách hàng.
- **Hệ quả:**
  - ✅ *Lợi ích:* Đạt tiêu chuẩn an toàn cao nhất của OWASP LLM06:2025 (Excessive Agency). Loại bỏ 100% rủi ro agent tự ý thanh toán hoặc xóa sạch giỏ hàng.
  - ⚠️ *Đánh đổi:* Frontend và Backend phải tích hợp chung giao thức JSON Confirmation, tăng thời gian làm việc nhóm CDO & AIO.

---

## ADR-007 - [Extend] Sử dụng Drain3 cho Log Clustering & Anomaly Detection  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Observability / AIOps
- **Task:** TF1-52 / AIOps-W1-T4
- **Bối cảnh:**
  Khi hệ thống gặp sự cố (OOM, DB connection timeout, LLM 429 rate limit), log thô từ các container `product-reviews` và `llm` đổ vào OpenSearch có thể lên tới hàng nghìn dòng/phút. On-call mất 10-15 phút đọc log thủ công để xác định root cause. Alert dựa trên keyword đơn (`grep ERROR`) sinh quá nhiều false-positive, gây alert fatigue.
  *(Ghi chú: Drain3 là một thành phần Mở rộng / Extend được tự xây mới ngoài phạm vi repo mã nguồn tĩnh ban đầu).*
- **Quyết định:**
  Sử dụng thuật toán **Drain3** (online log parsing, fixed-depth tree) để tự động phân cụm log thô thành các log template. Phát hiện anomaly qua 2 tiêu chí:
  - **NEW_ERROR_TEMPLATE:** Template lỗi chưa từng xuất hiện → dấu hiệu sự cố mới.
  - **ERROR_SPIKE:** Template lỗi cũ nhưng tần suất vượt ngưỡng → sự cố đang leo thang.
  - Persist Drain3 state giữa các lần chạy để phân biệt template mới vs cũ (incremental clustering).
  - Parameters: `sim_th=0.4`, `depth=4`, `max_clusters=1000`.
- **Phương án khác đã cân:**
  - *Option A - Regex pattern matching thủ công:* Nhanh nhưng phải viết/update regex mỗi khi log format thay đổi. Không scale khi thêm service mới. Bỏ qua.
  - *Option B - LLM-based log classification:* Chính xác cao nhưng tốn chi phí API ($5-20/ngày) và chậm. Vi phạm tinh thần tiết kiệm ngân sách. Bỏ qua.
  - *Option C - LogReduce / clustering dựa trên cosine similarity:* Tốt nhưng chậm hơn Drain3 khi log volume lớn và không có cơ chế incremental state tốt bằng. Bỏ qua.
- **Cost Δ:** $0 (Drain3 là thư viện Python mã nguồn mở, chạy in-cluster).
- **Ảnh hưởng SLO:** Không ảnh hưởng trực tiếp đến SLO. Gián tiếp cải thiện MTTD (Mean Time To Detect) từ 10-15 phút xuống < 1 phút nhờ tự động phát hiện log lỗi mới.
- **Rollback:** Module hoạt động độc lập (read-only với OpenSearch), không ghi/sửa bất kỳ service nào. Để tắt: xóa CronJob hoặc ngừng chạy script.
- **Hệ quả:**
  - ✅ *Lợi ích:* Tự động phát hiện sự cố mới, giảm alert fatigue, tích hợp được vào vòng AIOps auto-remediation.
  - ⚠️ *Đánh đổi:* Lần chạy đầu tiên (cold start) sẽ alert tất cả template lỗi vì chưa có baseline. Giảm thiểu bằng cách chạy 1 lần warm-up trên log lịch sử trước khi bật cảnh báo.

---

## ADR-008 - Semantic Search nâng cao bằng Amazon Titan Embeddings + pgvector (Hạng mục Đua Top)  ⟵ *amended 12/07, xem Phụ lục kiểm chứng*
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Performance Efficiency / Cost Optimization
- **Bối cảnh:** 
  Hàm `SearchProducts` trong Product Catalog service hiện chỉ dùng keyword matching (`WHERE LOWER(p.name) LIKE $1`), không hiểu ngữ nghĩa truy vấn tự nhiên. Ví dụ: "tai nghe chống ồn dưới $50" trả về 0 kết quả vì không có từ khóa chính xác. RULES.md line 66 yêu cầu "semantic search nâng cao" cho hạng mục đua top. AI_FEATURE.md Intent #1 yêu cầu "query tự nhiên ra đúng sản phẩm, không phải keyword cứng".
- **Quyết định:** 
  Sử dụng **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`) để tạo vector embeddings 1024 chiều cho tất cả sản phẩm, lưu trữ trên **pgvector** (PostgreSQL extension). Khi tìm kiếm: embed query → tìm sản phẩm gần nhất bằng cosine similarity (`<=>`) với HNSW index.
  - **Embedding model:** `amazon.titan-embed-text-v2:0` (1024 dimensions, Amazon first-party → credit-eligible). *Trước khi code, xác nhận model khả dụng ở `us-east-1`: `aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId,'embed')].modelId"`.*
  - **Vector store:** pgvector trên PostgreSQL hiện có (zero infra mới)
  - **Index:** HNSW (m=16, ef_construction=64)
  - **Fallback:** Nếu embedding chưa sẵn sàng hoặc Bedrock timeout, fallback về keyword search hiện tại
  - **Feature flag:** `semanticSearchEnabled` qua flagd
- **Phương án khác đã cân:**
  - *Option B - Titan Embeddings + OpenSearch:* Tối ưu cho search scale lớn nhưng OpenSearch Serverless yêu cầu tối thiểu ~$350/tháng → vượt ngân sách. Loại bỏ.
  - *Option C - AWS Bedrock Knowledge Bases:* Managed RAG nhưng tự tạo OpenSearch backend → cùng vấn đề chi phí. Loại bỏ.
  - *Option D - Hybrid Search (BM25 + Semantic + RRF):* Tối ưu nhất về chất lượng nhưng phức tạp hơn. Giữ lại cho Phase 2 nếu còn thời gian.
- **Cost Δ:** Chi phí gần như $0. Titan Text Embeddings V2 ~$0.00002/1K tokens. Embed toàn bộ catalog (~200 products) tốn ~$0.001. Per-search: ~$0.000004. 100% credit-eligible.
- **Ảnh hưởng SLO:** Latency p95 dự kiến ~88ms (embed query 80ms + pgvector HNSW 8ms), nằm trong SLO < 1s.
- **Hệ quả:**
  - ✅ *Lợi ích:* Cho phép tìm kiếm bằng ngôn ngữ tự nhiên, giảm "no results" pages, tăng conversion rate. Zero chi phí infra mới.
  - ⚠️ *Đánh đổi:* Phải cập nhật code backend CDO để lưu vector. Tuy nhiên, đánh đổi này là xứng đáng để đạt chuẩn Enterprise-grade (AWS Well-Architected). Dynamic Prompting bị loại bỏ vì là anti-pattern.
- **Spec chi tiết:** [docs/ai/03_specs/semantic_search.md](03_specs/semantic_search.md)

---

## ADR-009 - AI-Powered Product Recommendations bằng Embedding Similarity (Hạng mục Đua Top)
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Performance Efficiency / Cost Optimization
- **Bối cảnh:** 
  Service `recommendation` hiện trả về sản phẩm **hoàn toàn ngẫu nhiên** (`random.sample`), không có bất kỳ tín hiệu AI nào. RULES.md line 66 yêu cầu "recommendation bằng tín hiệu AI" cho hạng mục đua top. AI_FEATURE.md Intent #5 yêu cầu "Gợi ý kèm / cross-sell". Hệ thống không có clickstream data thật nên collaborative filtering không khả thi.
- **Quyết định:** 
  Áp dụng `pgvector` trên RDS. Khi user xem product A, lấy embedding của A từ DB → tìm K products gần nhất bằng cosine similarity (`<=>`) trên `pgvector` → trả về làm recommendations. Bác bỏ LLM reasoning (Dynamic Prompting).
  - **Phase 1:** Embedding similarity (zero-cost, sub-50ms latency)
  - **Phase 2 (optional):** LLM Re-ranking bằng Nova Lite để chọn complementary items
  - **Feature flag:** `aiRecommendationsEnabled` qua flagd
  - **Fallback:** Nếu embedding chưa sẵn sàng, fallback về random hiện tại
- **Phương án khác đã cân:**
  - *Option B - LLM Re-ranking (Nova Lite):* Chất lượng cao hơn (hiểu "complementary") nhưng latency 1-3s và tốn token. Giữ cho Phase 2.
  - *Option C - Amazon Personalize:* State-of-the-art nhưng cần tối thiểu 1000 interaction events (không có) và chi phí cao. Loại bỏ.
  - *Option D - Collaborative Filtering:* Cần user profiles và purchase history thật. Demo app không có. Loại bỏ.
  - *Option E - TF-IDF Content-based:* Kém hơn embeddings vì không hiểu ngữ nghĩa. Loại bỏ.
- **Cost Δ:** $0 phát sinh. Reuse embeddings đã tính cho Semantic Search (ADR-008). Chỉ 1 SQL query trên pgvector.
- **Ảnh hưởng SLO:** Latency p95 < 50ms (chỉ 1 DB query). Không ảnh hưởng SLO hiện tại.
- **Hệ quả:**
  - ✅ *Lợi ích:* Chuyển từ random → AI-driven recommendations. Zero cold-start. Zero extra cost. Tái sử dụng infra embedding.
  - ⚠️ *Đánh đổi:* Chỉ gợi ý sản phẩm "tương tự", chưa gợi ý sản phẩm "bổ sung" (cần Phase 2 LLM Re-ranking).
- **Spec chi tiết:** [docs/ai/03_specs/ai_recommendations.md](03_specs/ai_recommendations.md)

---

## ADR-010 - Model Gateway & A/B Testing cho LLM bằng OpenFeature/flagd (Hạng mục Đua Top)
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-09
- **Người ký:** Nhóm AI (AIO03) - Task Force 1
- **Trụ:** Performance Efficiency / Cost Optimization / Reliability
- **Bối cảnh:** 
  Hệ thống LLM hiện gọi cứng một model duy nhất qua biến ENV. Muốn so sánh chất lượng/latency/cost giữa các model (vd: Nova Lite vs Nova Pro cho reviews summary) phải thay ENV và redeploy pod → không thể A/B test an toàn. RULES.md line 66 yêu cầu "model gateway + A/B khi đổi model" cho hạng mục đua top.
- **Quyết định:** 
  Xây dựng **Model Router** trực tiếp trong Python code của LLM service, sử dụng **OpenFeature/flagd** (đã có sẵn trên EKS) để điều khiển traffic split:
  - **Flag name:** `llmModelRouting` với `fractional` targeting để phân luồng traffic theo tỷ lệ phần trăm.
  - **Metrics per-model:** Emit OTel metrics (`llm.gateway.requests`, `llm.gateway.latency_ms`, `llm.gateway.tokens`, `llm.gateway.estimated_cost_usd`) tagged bằng `model_id` và `task_type`.
  - **Rollout strategy:** Shadow mode → Canary 5% → Gradual 25%→50%→100%.
  - **Fallback:** Nếu flagd unavailable, default về Nova Lite cho reviews, Nova Pro cho copilot (giống ADR-004).
- **Phương án khác đã cân:**
  - *Option B - LiteLLM Proxy:* Feature-rich nhưng thêm 1 microservice phải deploy/monitor trên EKS. Overkill cho 2-3 models cùng provider. Loại bỏ.
  - *Option C - AWS API Gateway + Lambda:* Unnecessary network hop cho internal service. Cold start Lambda thêm ~200ms. Loại bỏ.
  - *Option D - Envoy Proxy Sidecar:* Cần custom filter C++/WASM. Effort quá lớn cho 3-week capstone. Loại bỏ.
- **Cost Δ:** $0 phát sinh cố định. A/B testing giúp phát hiện model rẻ hơn mà chất lượng tương đương → tiềm năng tiết kiệm thêm chi phí LLM.
- **Ảnh hưởng SLO:** Overhead routing < 5ms. Flag change → effect < 30 giây. Không ảnh hưởng SLO hiện tại.
- **Hệ quả:**
  - ✅ *Lợi ích:* Cho phép A/B test model an toàn, so sánh cost/latency/quality per-model trực quan trên Grafana, gradual rollout khi đổi model.
  - ⚠️ *Đánh đổi:* Phải viết và maintain Model Router code, phải thiết lập Grafana dashboard cho metrics per-model.
- **Spec chi tiết:** [docs/ai/03_specs/model_gateway_ab_testing.md](03_specs/model_gateway_ab_testing.md)

---

## Phụ lục kiểm chứng 12/07/2026 — số đo thay số ước lượng (verification addendum)

> Kết quả re-verify toàn bộ ADR trên stack chạy thật (docker compose, image build từ source) + thí nghiệm tái tạo được (script trong `docs/ai/evals/`). Mỗi mục dưới đây SỬA hoặc BỔ SUNG cho ADR tương ứng ở trên.

**ADR-001 (Valkey caching):** Premise "review tĩnh" đã kiểm chứng đúng (proto không có rpc ghi, seed `init.sql`) → hệ quả: **dynamic TTL bị gỡ khỏi code** (không có gì để nó phản ứng, chỉ đốt lại token cho output giống hệt; hệ chỉ có 10 cache key) → TTL phẳng 7d. **Versioned key trước đây vô hiệu** — `model_ver/prompt_ver` là hằng số chết; nay derive từ `LLM_REVIEWS_MAIN_MODEL` + md5(SYSTEM_PROMPT)[:8].

**ADR-002/005 (Fallback & Resilience):** Trạng thái "tuần 2 mới làm" đã stale — PR#26 merge rồi. Kiểm chứng runtime phát hiện và đã sửa 4 lỗi: (1) flag `llmReviewsFallbackEnabled` **không tồn tại trong flagd**, default code = False → fallback chưa từng chạy (proof trước fix: 0 dòng "Fallback routing triggered"; sau fix: ×5); (2) bulkhead `Semaphore(10)` blocking trên pool 10 thread = **no-op** (thí nghiệm `evals/bulkhead_experiment.py`: fast-request 1909ms cả khi sema=6 blocking; non-blocking→mock = 10ms) → sửa thành non-blocking, sema 6; (3) circuit breaker đọc cờ sự cố `llmRateLimitError` — vùng xám luật "đổi hướng cơ chế sự cố" (AI_FEATURE §3) → thay bằng breaker 3-lỗi-liên-tiếp/mở-30s (proof: "Circuit Breaker OPENED for 30.0s after 3 consecutive primary failures"); (4) lớp lỗi `BotoCoreError` (NoCredentials, endpoint...) **thoát ngang ladder** vì không nằm trong except tuple → đã mở rộng. Lớp 1 "SDK adaptive retry" trong spec sai — code tắt SDK retry (`max_attempts: 0`, đúng để tránh retry kép).

**ADR-003 (Eviction policy) — ⚠️ CẢNH BÁO, cần quyết lại với CDO:** chuỗi 3 mảnh tự vô hiệu: `--maxmemory-policy volatile-lru` được thêm **không kèm `--maxmemory`** → policy không bao giờ chạy; TTL cart bị gỡ để "chống eviction" là chẩn đoán sai (TTL expiry ≠ LRU eviction) và gỡ đúng cơ chế chống rò rỉ duy nhất; limit container 20Mi + cart tích vô hạn → **kubelet OOMKill → mất toàn bộ giỏ → đánh checkout SLO ≥99%** (đúng vết INC-2). Cron GC 30-ngày không cứu được. Phương án: khôi phục TTL hoặc set maxmemory + tách instance cache reviews; chọn sau soak test đo time-to-OOM.

**ADR-004 (Hybrid routing):** TTFT Nova Lite ghi ~0.4s **sai so với chính nguồn cite** — Artificial Analysis: **TTFT 1.04s, 175.7 tok/s** → 1 call ≈2.2s, luồng tóm tắt 2 vòng converse ≈4.4s điển hình (không phải "2.5s"). Nhóm đã **chốt bỏ Claude (11/07)** — lập luận bảo vệ Nova chuyển sang con số đã verify: **rẻ ~50× Claude Sonnet** ($0.06/$0.24 vs $3/$15 per 1M); bỏ claim credit chưa kiểm chứng. Claude 3.5 Sonnet trong bảng so sánh đã EOL trên Bedrock 03/2026 — nếu còn dùng so sánh, dùng Sonnet 4.x (cùng giá).

**ADR-004 fix (16/07):** PR#61 đưa `llmModelRouting` (Model Gateway ADR-010, A/B copilot) vào flagd, nhưng product-reviews cũng đọc chung flag này → default `ab_test_active` (Lite 80/Pro 20) lộ 20% traffic tóm tắt review sang Nova Pro, ngược premise "reviews = Lite vì tải cao/đơn giản" ở trên. Trên EKS thì flag chưa từng tồn tại trong chart (drift 2 file flagd) nên fallback env `nova-lite` cứu được; trên compose thì ăn giá Pro thật. Đã tách: `product-reviews/model_router.py` giờ đọc flag riêng `llmReviewsModelRouting` (chỉ có variant `lite_only`, 100% Nova Lite); `llmModelRouting` giữ nguyên cho riêng shopping-copilot. Đã sync cả 2 flag mới vào `platform/charts/application/flagd/demo.flagd.json` để hết drift.

**ADR-007 (Drain3 + detector):** Số đo thật (compose + chaos flagd, script `evals/measure_detection_pipeline.py`): ingest lag P50 2.1s; **MTTD poll 30s: mean 19.6s / max 35.4s** — claim "MTTD < 1 phút" giờ có evidence; vùng poll hợp lệ theo error budget: [10s, 60s], chi phí query ~0 (5ms/query). Grid Drain3 trên 19.294 dòng log thật (`evals/drain3_param_grid.py`): **sim_th 0.3 trội 0.4 ở cả 4 tiêu chí** (795 vs 1074 templates, coverage 48.3% vs 47.1%, singleton 56% vs 60%, stability 0.64 vs 0.73); depth 4–6 vô cảm. Đồng bộ 13/07: code default = **0.3** (số đo, env `DRAIN_SIM_TH`), thay vì giữ 0.5 (cũ) hay lùi về 0.4 (spec chưa kiểm). Masking đã thêm vào grid; re-confirm trên 24h log EKS.

**ADR-008 (Semantic search):** Dữ liệu thật: **catalog 10 sản phẩm, 50 reviews** (đếm từ DB). HNSW/pgvector từng bị chê là over-engineering, nhưng **[CẬP NHẬT 14/07]** Ban Kiến trúc sư lật lại quyết định: Triển khai `pgvector` ngay bây giờ để đạt chuẩn Enterprise-grade. Phương án nhét catalog vào prompt (Dynamic Prompting) bị bác bỏ hoàn toàn.

### Ghi chú build (12/07): protobuf gencode/runtime

Source từng không build được image: `demo_pb2.py` bị regen bằng protoc mới (gencode 7.35.0) trong khi `requirements.txt` (qua grpcio-health-checking 1.71) ghim runtime protobuf 5.29.6 → `VersionError` khi boot. Diff `pb/demo.proto` so baseline chỉ là **2 dòng trắng** — regen là churn thuần. **Fix: revert `demo_pb2*.py` (product-reviews + recommendation) về bản baseline.** Quy tắc rút ra: chỉ regen pb khi proto đổi semantic, và regen bằng đúng grpcio-tools phiên bản khớp requirements (xem `docker-gen-proto.sh`).

### Sổ đăng ký con số (12/07) — số nào đã có căn cứ, số nào còn là assumption

Trả lời câu hỏi kiểm toán "còn số phẳng không lý do không": có, và chúng được liệt kê ở đây thay vì giả vờ không tồn tại. Quy ước: số ASSUMPTION phải có nhãn + kế hoạch đo; không được trình như số đo.

**Đã đo / có derivation:**
| Số | Căn cứ |
|---|---|
| Poll detector 30s | Đo MTTD max 35.4s, vùng hợp lệ [10s,60s] theo error budget; chi phí query 5ms/lần |
| Mẫu số cost 10:1, giá Nova/Claude, Titan | locustfile weights; pricing page |
| TTL cache 7d phẳng | Data tĩnh (verified proto/DB) → không cần expiry; 7d là trần tự-phục-hồi tuỳ chọn |
| Burn-rate 14.4×/6× (rule draft) | Derivation chuẩn SRE workbook từ budget 0.5%/24h |
| sim_th Drain3 | Grid đo trên 19.3k dòng: 0.3 trội — CHƯA chốt vào code, chờ masking + 24h EKS |
| Bulkhead "phải < 10 và non-blocking" | Thí nghiệm 10ms vs 1909ms (ràng buộc đã chứng minh) |

**Còn là ASSUMPTION (có nhãn, cần đo hoặc quyết):**
| Số | Hiện ở đâu | Kế hoạch |
|---|---|---|
| Bulkhead size **6** | `LLM_BULKHEAD_SIZE` | Ràng buộc <10 đã chứng minh; giá trị 6 cụ thể chưa tối ưu — load test in-cluster |
| CB **3 lỗi / 30s** | `LLM_CB_THRESHOLD/COOLDOWN` | Convention; tune bằng chaos test |
| Timeout **4.0s/2.0s/5.7s/2.5s** | spec + env | Đã đo P50/P95 thật bằng `evals/measure_bedrock_latency.py` ngày 15/07/2026; xem `evals/bedrock_latency_results_2026-07-15.md` |
| Retry 2/1, backoff 100ms/×1.5 | spec + code | Pattern AWS blog; giá trị cụ thể chưa justify, tác hại nhỏ (≤2 retry) |
| `maxTokens 1024, temp 0.1, topP 0.9` | code converse | Chưa ai ghi lý do — cần 1 dòng justification hoặc eval nhỏ |
| EWMA α=0.2, 3σ | spec + detector | Trong canon SPC; backtest trên 24h Prometheus thật |
| memory-saturation **0.85/10m**, min_count **1/10m** | rules.yaml (draft/K2) | Đo FP 24h để tune |
| Cooldown alert **600s** | rules.yaml | ❌ chưa đo — convention; đo FP-run 24h EKS (TF1-71) |
| Window **5m/10m** | rules.yaml | ❌ chưa đo FP theo window (TF1-71) |
| min_count **1** (đã hạ từ 1–3) | rules.yaml | ⚠️ suy luận K2 + FP-run 15′=0; dải "3" đã bỏ, không cần |
| Remediation **120s verify / 3-fail CB / 1 pod/h** | anomaly_remediation.md | Label assumption; eval khi bật auto-remediation |
| Envoy copilot **30s** (5 vòng tool × 5s) | envoy.tmpl.yaml | Dựa ADR-006 khi chưa có agent thật — đo lại khi copilot chạy |
| Exclusion list rule latency | rules.yaml | Rà lại mỗi khi thêm service mới |
| Drain3 max_children 100 / max_clusters 1000 | log_clustering.py | Default thư viện, chưa xét — đưa vào lượt grid sau |

### Cập nhật 12/07 (tối) — mentor xác nhận 3 điều
1. **Đọc cờ sự cố flagd để bypass = PHẠM LUẬT** (xác nhận chính thức) — bản circuit breaker cũ (flag-aware, ADR-005/L5) nếu còn giữ là dính; đã thay bằng breaker 3-lỗi-liên-tiếp từ trước khi hỏi. Bài học ghi vào luật nhóm: **không code path nào được đọc cờ sự cố của BTC**, kể cả để "phòng thủ".
2. **Khung evidence-pack 6 doc áp dụng Phase 3** — cấu trúc docs/ai đã đổi theo (01/02/03/04/05/06).
3. **Số đo compose local được dùng tạm** — mọi bảng số trong docs giữ nhãn nguồn "compose"; W2 thay bằng số EKS.

### G7/K3 — kế hoạch tương quan & dedup alert (migrate từ review 12/07, nền cho RCA W2)
- **G7 (chưa có — đo tuần 2):** ma trận tương quan Pearson/Spearman giữa golden signals per-service (lag 0/30/60s) từ 24h Prometheus + bảng alert co-occurrence từ log alerter. Mục đích: đặt rule không trùng lặp, chọn leading indicator, nền cho RCA cross-service (mở rộng đề). Trước khi có bảng này, rule/ngưỡng mới coi là tạm.
- **K3 (gap theo pipeline giáo trình — Correlate là stage bắt buộc):** hiện chỉ có cooldown per-rule+service; 1 sự cố Bedrock bắn 3 alert cùng lúc. Fix W2: fingerprint `(rule_id, service, 5m-bucket)` → gộp cùng bucket thành 1 message (~30 dòng trong `alerter.py`).


# ADR-011: AI Trust & Safety (MANDATE-06)

## Status
Accepted

## Date
2026-07-14

## Context
Tính năng AI (như tóm tắt review, shopping copilot) hiển thị trực tiếp cho khách hàng. Cần đảm bảo hệ thống chặn được Prompt Injection, không bị lộ thông tin cá nhân (PII), chống ảo giác (Hallucination) và fallback an toàn khi gặp sự cố, đáp ứng yêu cầu của MANDATE-06. AI Copilot Agent hiện tại gọi thẳng các API giỏ hàng, mang theo nguy cơ AI tự ý mua hàng mà không có sự đồng ý của khách hàng (Excessive Agency).

## Decision
1. **Áp dụng Defense-in-Depth Guardrails**:
   - Tầng 1: **Input/Output Regex Filtering**: Lọc PII (email, phone number) và chặn keyword injection trước khi đưa prompt tới LLM.
   - Tầng 2: **System Prompt Engineering**: Hướng dẫn LLM bỏ qua các thông tin rác.
   - Tầng 3: **Output Checking**: Bắt buộc chặn nếu LLM rò rỉ >40 ký tự của system prompt.
2. **Xác nhận hành động (Action Gating)**:
   - Tool `add_item_to_cart` chỉ sinh `confirmation_token`. Không ghi vào giỏ hàng thật cho đến khi Client chủ động request lại token này.
3. **Đánh giá (Eval)**:
   - Viết sẵn script `eval_mandate06.py` nhằm tự động giả lập các kịch bản Injection/Hallucination/Excessive Agency.

## Alternatives Considered

### Lọc bằng Model LLM thứ 2 (LLM-as-a-Judge)
- Pros: Khả năng nhận diện context và prompt injection rất thông minh.
- Cons: Làm tăng gấp đôi chi phí (cost) và độ trễ (latency). Rất khó đáp ứng SLO < 1s cho một lượt chat.
- Rejected: Trong pha này, Regex Filtering kết hợp System Prompt đủ hiệu quả với chi phí 0đ và delay ~0ms.

### Không cho phép AI truy cập Giỏ hàng
- Pros: Triệt tiêu rủi ro Excessive agency 100%.
- Cons: Trải nghiệm người dùng kém (AI không giúp được gì ngoài chat).
- Rejected: Gating mechanism (2-phase commit) cân bằng giữa UX và tính an toàn.

## Consequences
- Hệ thống an toàn tuyệt đối trước nguy cơ AI tự checkout.
- Đạt 100% yêu cầu MANDATE-06 của Ban Tổ Chức.
- Các API Frontend và App cần được cập nhật để xử lý `confirmation_token` khi nhận phản hồi từ AI Copilot.

---

# ADR-012: Phương pháp Anomaly Detection & Baseline cho AIOps Detector (MANDATE-07 #7a)

- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-16
- **Người ký:** Nhóm AI (AIO03) — Task Force 1 · Soạn thảo: Thanh Pham Huu Tien (owner TF1-53/TF1-62)
- **Trụ:** AI (AIOps) / Reliability / Operational Excellence
- **Task:** TF1-53 (detector W1) · TF1-62 (deploy EKS) · MANDATE-07 `#7a`

## Context
MANDATE-07 yêu cầu hệ thống tự phát hiện bất thường trên nhiều tín hiệu (sàn = univariate: mỗi service × 1 tín hiệu có baseline + luật riêng), cảnh báo theo mức ảnh hưởng, không spam. Detector (`aiops/detector/`) đã chạy liên tục trên EKS (ns `techx-tf1`, image `1.1-aiops-detector`), poll Prometheus + backend log mỗi 30s, alert về Discord.

## Decision — phương pháp phát hiện lai (hybrid), 2 lớp cho metric + 1 lớp log

1. **Lớp static SLO-anchored:** ngưỡng tĩnh lấy TRỰC TIẾP từ SLO hợp đồng (`onboarding/SLO.md`), không phải số tự chọn — vd checkout 5xx >1%, storefront 5xx >0.5%, p95 >1s. Lý do: vi phạm SLO là sự cố theo định nghĩa, alert không cần baseline "học".
2. **Lớp dynamic 3-sigma:** mỗi `rule × service` giữ rolling window 30 mẫu (~15 phút @ poll 30s, cần ≥5 mẫu mới kích hoạt); alert khi giá trị vượt `mean + 3σ` của chính service đó → bắt suy thoái CHƯA chạm SLO + tự thích nghi baseline per-service (yêu cầu "biết thế nào là bình thường" của đề). 3σ ≈ 0.3% FP theo SPC chuẩn.
3. **Lớp log (5 rule):** đếm phrase/marker máy (`AI_SUMMARY_FALLBACK`, OOMKilled, NXDOMAIN, pool exhaustion, 429) trong cửa sổ 5–10m; `min_count=1` cho lớp sự cố hiếm-nghiêm-trọng (nguyên tắc K2: recall dominates — bỏ lọt = 0 điểm).
4. **Chống spam:** dedup key `rule×service` + cooldown 600s; poll 30s chọn theo SỐ ĐO: MTTD max 35.4s (chaos 5 vòng), vùng hợp lệ [10s,60s] suy từ error budget, chi phí query 5ms — bảng sensitivity trong `03_specs/golden_signals_detection.md` Phụ lục 3.

## Alternatives considered
- **EWMA α=0.2 (spec TF1-49 gốc):** phản ứng có trọng số theo thời gian, tốt hơn rolling-mean với drift chậm. CHƯA thay vì cần backtest trên ≥24h dữ liệu Prometheus EKS thật để chọn α có căn cứ (kế hoạch `#7b`, TF1-71); rolling 3σ hiện tại cùng họ SPC, đơn giản, đủ cho sàn univariate của đề. → Defer sang #7b, không phải reject.
- **Chỉ ngưỡng tĩnh:** mù với suy thoái dưới ngưỡng (slow burn 0.4%/ngày đốt 80% budget không kêu). → Loại, nhưng giữ làm lớp 1.
- **Realtime stream consumer:** mua được ~15–30s MTTD bằng cả một service chạy 24/7 (state, reconnect, RAM trong trần $300) trong khi poll 30s đã pass target ≤2 phút với biên 3.4×. → Loại (trade-off sai).
- **Multi-window burn-rate (SRE workbook):** ĐÚNG chuẩn hơn cho error budget — đã có rule DRAFT `error-budget-burn-fast` (14.4× ở cả 5m và 1h), chờ verify semantics trên EKS vì compose không sinh được 5xx thật. → Nâng cấp có kế hoạch ở #7b, không phát minh lại ngưỡng.

## Consequences
- 13 rule config-driven (`rules.yaml`), thêm tín hiệu không sửa code; mỗi con số có nhãn đo/assumption trong "Sổ đăng ký con số" (05_adrs).
- Trả giá: rolling-mean nhớ ngắn (~15 phút) → baseline "bình thường" theo giờ-trong-ngày chưa mô hình hoá; chấp nhận ở W2, đánh giá lại sau FP-run 24h (TF1-71).
- Phụ thuộc mở: backend log trên EKS chưa tồn tại (collector logs pipeline chỉ export debug) → 5 rule log + Drain3 tạm mù trên production; đã escalate CDO (quyết định thay OpenSearch), detector tự hồi phục khi backend lên, không cần redeploy.

---

### Addendum 16/07/2026 — Red-team nội bộ + hardening tối thiểu (không thêm model mới)

Nhận định ban đầu ("Regex + System Prompt đủ hiệu quả") đúng cho case naive
nhưng **quá cứng trước paraphrase/reorder** — xác nhận bằng attack suite mới
(`docs/ai/evals/test_guardrails_adversarial.py`), chạy trực tiếp trên
`guardrails.py` thật, không phải suy đoán:

| Kỹ thuật tấn công | Kết quả thực tế | Ghi chú |
|---|---|---|
| Đảo thứ tự câu ("...ignore them" ở cuối) | ⚠️ Bypass L1 | Cần L2 (semantic) — xem dưới |
| Đồng nghĩa (forget/reveal configuration) | ⚠️ Bypass L1 | Cần L2 |
| Leetspeak (`1gnore`, `previ0us`) | ⚠️ Bypass L1 | Cần L2 |
| Zero-width-space chèn giữa từ (`ig<ZWSP>nore`) | ✅ Đã vá | Lớp 0 normalize (NFKC + strip ZW/bidi-control), zero-cost |
| Ngôn ngữ thứ 3 (tiếng Pháp) | ⚠️ Bypass L1 | Cần L2 |
| Injection gián tiếp qua roleplay | ⚠️ Bypass L1 | Cần L2 |
| Payload chia 2 field JSON (title/description) | ⚠️ Bypass L1, **L2 vẫn thấy được** | L2 chạy trên JSON đã ghép (`sanitize_json_for_llm` output), không phải per-field |
| Leak đúng "khe hở" giữa các đoạn keyword-sample của output guard | ✅ Đã vá | Đổi thuật toán: trượt cửa sổ N-từ qua OUTPUT thay vì sample cố định từ prompt |

**Quyết định đầu tiên (đã đảo ngược sau review):** định thêm Presidio (NER-PII)
+ 1 ONNX classifier riêng làm Lớp 1.5, đổi base image alpine→debian-slim cho
2 service. **Bị loại bỏ** sau khi cân nhắc lại:
- Mandate 6 nói thẳng *"đừng quăng model to cho xong"* — thêm 1 model thứ hai
  (ngoài LLM chính đã trả tiền) đi ngược đúng câu này, dù nhẹ cỡ nào.
- Đổi base image là đất hạ tầng của CDO (cần co-sign, xem tiền lệ ADR-003),
  và đụng đúng lúc MANDATE-05 (deadline 17/07, sớm hơn MANDATE-06) cũng đang
  chạm 2 Dockerfile này.
- Trong thời gian còn lại không verify được 1 lần inference thật (môi trường
  dev network không ổn định cho package nặng) — mang thứ chưa test lên sát
  deadline là rủi ro thật.
- `product-reviews` đang giới hạn memory 512Mi (`values.yaml`) — không đủ cho
  spaCy NER + DeBERTa-v3 cùng lúc, rủi ro OOMKill đúng pattern sự cố J1 đã ghi
  ở ADR-003.

**Quyết định cuối cùng — tái dùng L2 (Bedrock LLM-judge) đã có sẵn thay vì
thêm model mới:**
- **Lớp 0 (giữ):** Unicode NFKC normalize + strip zero-width/bidi-control char.
  Vá được case zero-width, chi phí ~0, không có dependency mới.
- **Lớp 2 (đăng ký lại + mở rộng phạm vi):** `llmGuardrailLlmJudge` từng tồn
  tại trong code nhưng **chưa từng được khai báo** trong `demo.flagd.json` —
  mọi lần gọi âm thầm resolve về `False`. Đã đăng ký đúng vào cả 2 file flagd
  config. Đồng thời wire thêm vào `copilot_server.py` (trước đây chỉ
  `product_reviews_server.py` có L2 — copilot chỉ có L1 regex). Dùng lại
  `self._bedrock` sẵn có của servicer, **không thêm model/dependency mới**.
- **Output-guard (thuật toán mới, vẫn Lớp 1, không cần L2):** đổi từ "sample n
  phrase cố định từ system_prompt rồi tìm trong output" sang "trượt cửa sổ
  6-từ qua OUTPUT rồi tìm trong system_prompt" — bắt được MỌI đoạn liên tục bị
  leak, không phụ thuộc việc leak có rơi đúng vùng đã sample hay không. Đóng
  gap chunk-boundary bằng thuật toán, không cần model.

**Còn là KNOWN_GAP, cần bật flag `llmGuardrailLlmJudge` để bắt (chưa đo
latency, xem dưới):** đảo thứ tự câu, đồng nghĩa, leetspeak, ngôn ngữ thứ 3,
injection gián tiếp. Split-field JSON: L1 miss nhưng **L2 đã thấy được** vì
chạy trên toàn bộ JSON đã ghép field.

**Rủi ro SLO chưa đo (ASSUMPTION, theo quy ước Phụ lục 12/07):**
`llmGuardrailLlmJudge` mặc định OFF cho tới khi benchmark latency Bedrock
Nova Micro classifier call trên EKS — mandate yêu cầu guardrail không được
kéo p95 vỡ SLO. Kế hoạch: bật flag ở staging, đo p95 trước khi cân nhắc bật
mặc định.

**Chưa làm, cần soát trước 18/07 (không liên quan trực tiếp code guardrail
nhưng chặn việc mentor test được):** `shopping-copilot` đang `enabled: false`
trong `values.yaml` (comment cũ "no source/image yet" — đã lỗi thời, code đã
có đầy đủ); `product-reviews` vẫn chạy root (MANDATE-05, deadline 17/07).

---

# ADR-013: Closed-loop Auto-remediation — dry-run → blast-radius → verify → rollback → CB (TF1-72)

- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-17
- **Người ký:** Nhóm AI (AIO03) — Task Force 1 · Soạn thảo: Thanh Pham Huu Tien (assignee TF1-72)
- **Trụ:** AI (AIOps) / Reliability / Operational Excellence
- **Task:** TF1-72 (con của TF1-78) · hiện thực hoá spec TF1-50 `03_specs/anomaly_remediation.md`

## Context
`RULES.md §4` đặt "vòng tự động hoá xử lý sự cố" (phát hiện → dry-run/blast-radius →
xử lý → verify → rollback/escalate, chạy liên tục) là **cốt lõi**, không phải mở rộng.
W1 (`aiops/detector/`, TF1-53) cố tình chỉ detect+alert — comment trong code ghi rõ
"KHONG tu khac phuc (do la TF1-50)". TF1-72 hiện thực hoá phần còn lại, theo đúng spec
đã duyệt ở `03_specs/anomaly_remediation.md` (mentor xác nhận khớp nguyên văn §4).

## Decision — component tách riêng `aiops/remediation/`, 1 action, 1 kịch bản demo

1. **Kiến trúc tách biệt khỏi detector:** ServiceAccount/RBAC/Deployment riêng
   (`aiops-remediation`, Role namespace-scoped chỉ `pods: get/list/watch/delete` +
   `pods/log: get`). Lý do: detector chạy cố tình với 0 quyền K8s (kể cả đọc) — gộp
   remediation vào cùng pod sẽ phá ranh giới least-privilege đã document khắp repo.
   Đúng kiến trúc 4-participant của spec (Monitor/Engine/K8s/Verify).
2. **Trigger:** tự poll `OpenSearchClient` (tái dùng từ `aiops/detector/sources.py`)
   cho rule `oom-detected` — không sửa `detector.py`/`alerter.py` (tránh đụng PR đang
   mở, và giữ nguyên "1 nguồn phát hiện, nhiều bộ tiêu thụ" thay vì nhân đôi logic).
3. **Xác định pod mục tiêu qua K8s API thật** (`status.containerStatuses[].lastState.
   terminated.reason == "OOMKilled"`), không suy luận từ text log — log OpenSearch
   hiện không có field service/pod name trong `_source` (xem `sources.py`), nên dùng
   trực tiếp K8s API đáng tin cậy hơn parse chuỗi.
4. **1 action duy nhất: `k8s_restart_pod`** (xoá pod, ReplicaSet tự tạo lại) — đúng
   action duy nhất có trong spec đã duyệt. Không làm `scale`/`clear cache` (chỉ là ví
   dụ minh hoạ trong mô tả ticket, không phải trong spec chính thức).
5. **"Rollback" cho action restart-pod = dừng lại + tăng circuit breaker + escalate
   người**, không phải `helm rollback` như ví dụ trong spec — vì restart-pod không đổi
   Helm release/config nào để mà hoàn tác. Quyết định này đã chốt với người phụ trách
   (không tự bịa 1 hành động rollback không có thật để bám câu chữ spec).
6. **5 lớp an toàn** (`remediation_policy.yaml`, tái dùng ngưỡng SLO 0.5% đã có cho
   error-budget thay vì bịa số mới): circuit-breaker check → error-budget check →
   blast-radius check → dry-run gate → action → verify (120s/poll 20s) → reset CB
   hoặc tăng fail-count.

## Ràng buộc sinh tử (RULES.md §8, không thương lượng)
Không module nào trong `aiops/remediation/` được đọc/gọi flagd để quyết định hành vi —
kể cả circuit-breaker, kể cả "phòng thủ". Tiền lệ trong repo: 1 circuit-breaker khác
(LLM/product-reviews) từng bị chấm **vi phạm luật** vì đọc cờ `llmRateLimitError`.
Circuit-breaker/blast-radius ở đây chỉ dựa vào kết quả `verifier.py` đo thật qua K8s
pod-status + Prometheus — có test tường minh canh việc này
(`test_no_flagd_or_helm_reference_anywhere_in_remediation_module`).

## Alternatives considered
- **Gộp vào cùng pod/process với detector:** nhanh hơn (tái dùng vòng poll có sẵn)
  nhưng phá ranh giới least-privilege đã cố tình giữ; phải cấp quyền ghi K8s vào đúng
  pod đang chạy detect-only. → Loại.
- **Detector publish event nội bộ, remediation tiêu thụ:** tránh query OpenSearch 2
  lần, nhưng phải sửa `detector.py`/`alerter.py` đang có PR mở chờ review, tăng phạm
  vi thay đổi ngay sát hạn 19/07. → Loại cho vòng này, có thể cân nhắc lại ở #7b.
  Đánh đổi: query trùng 1 lần/30s, chi phí không đáng kể so với rủi ro đụng code đang
  review.
- **Action `helm rollback` thật cho verify-fail:** bám sát chữ "rollback" trong spec
  hơn, nhưng restart-pod không có "trạng thái cấu hình trước đó" để hoàn tác về — làm
  vậy sẽ là rollback một thứ không tồn tại. → Loại; dùng dừng+CB+escalate (mục 5).
- **Áp dụng action cho nhiều rule khác (latency, error-rate...):** đúng tinh thần
  "action catalog" trong mô tả ticket hơn, nhưng vượt phạm vi 1-kịch-bản-end-to-end mà
  Done criteria yêu cầu, và mỗi rule cần safety-boundary số riêng chưa được đo. → Defer
  sang #7b/vòng sau, không phải reject.

## Consequences
- Config-driven (`remediation_policy.yaml`) — thêm rule→action mới không cần sửa code,
  giống triết lý `rules.yaml` của detector.
- RBAC mới lần đầu trong repo dạng K8s Role thuần (không phải IRSA/IAM) — không có
  tiền lệ để so sánh, cần review kỹ khi lên EKS thật.
- 3 số an toàn (verify 120s, CB 3-fail, blast-radius 1/namespace/giờ) hiện là GIẢ ĐỊNH
  từ spec, CHƯA đo thật — kế hoạch đo qua chaos test `emailMemoryLeak` (xem README.md),
  cập nhật `remediation_policy.yaml` + báo cáo `report/` sau khi đo.
- Nhận biết đánh đổi: blast-radius (1 action/namespace/giờ) mặc định sẽ khiến circuit
  breaker (cần 3 fail LIÊN TIẾP) rất khó tự nhiên đạt tới trong vòng chưa đầy 1 giờ vận
  hành thật — 2 cơ chế này che chắn lẫn nhau theo hướng BẢO THỦ hơn (ít hành động hơn),
  không phải lỗi logic; cần quan sát thêm khi chạy chaos test thật để quyết định có nên
  tách 2 phạm vi tính đếm (namespace vs từng service) ở vòng sau hay không.

---

# ADR-014 — ML Guard Cascade thay Bedrock Guardrails làm primary (MANDATE-06)

- **Status:** Accepted (2026-07-17) — supersedes ADR-012.
- **Context:** TF1-61 / MANDATE-06. Yêu cầu mới: không phụ thuộc Bedrock Guardrails, phải có ML self-host (CDO đã confirm cấp tài nguyên pod).

## Tại sao lật ADR-012 (fact, không vibes)

Docs AWS chính chủ (`guardrails-supported-languages`, đọc 17/07/2026):

| Policy Bedrock Guardrails | Tiếng Việt? |
|---|---|
| Prompt-attack / content filter | Chỉ **Standard tier** (Classic = EN/FR/ES → **vô hiệu với VN**) |
| **Contextual grounding** | ❌ **EN/FR/ES only** + docs ghi rõ *"Conversational QA / Chatbot use cases are not supported"* |
| PII filter | ✅ VN Optimized |

AWS: *"Guardrails are ineffective with languages that aren't supported."* → tính năng grounding (lý do chọn Bedrock ở ADR-012) **không hoạt động cho câu trả lời tiếng Việt**.
Thêm: Bedrock Guardrails tính tiền **mỗi request** ($0.10–0.15/1k text-unit) → attacker spam Ask AI = **economic DoS** độn cost tuyến tính; ML pod self-host = fixed cost.

## Quyết định — cascade 3 tầng (mọi con số đo thật 17/07, local + us-east-1 default profile)

| Tầng | Cơ chế | Kết quả đo | Cost |
|---|---|---|---|
| T0 in-process | regex VN/EN + PII redact + length cap | chặn direct/indirect pattern, 0ms | $0 |
| T1 `ml-guard` pod | **mDeBERTa-v3-base-mnli-xnli** (MIT, XNLI có VN) NLI grounding: `contra≥0.5→block`, `entail≥0.3→pass`, giữa→judge | grounding VN 6/6 (bịa: contra 0.98+; grounded: ≤0.007); RSS 1148MB fp32; p50 1.8s (laptop 2 threads) | $0 marginal (CDO pod) |
| T2 Nova judge | **injection: Nova Lite** few-shot (Micro chỉ 4/7 — trượt VN jailbreak); **grounding neutral-zone: Nova Micro** | injection **7/7**, grounding **4/4**, p50 ~550ms | ~$0.00002–0.00004/check → **<$1/wk** @10.5k req |
| Bedrock Guardrails | flag `LLM_BEDROCK_GUARDRAIL` **default OFF**; giữ code path + TF module làm option nếu cần Standard tier sau | — | $0 khi off |

Eval tổng (`docs/ai/evals/eval_mandate06_v5.py`, tái tạo được): **18/18 pass** (7 injection VN/EN + indirect, 5 grounding, 2 PII, 1 leak, 3 benign không chặn oan), p50 498ms.

Zero-shot NLI cho injection VN đã thử và **loại** (4/7, trượt cả 3 attack VN — đo trước khi chọn judge).

## Cost so sánh cuối

| Option | $/wk | Injection VN | Grounding VN | Spam→cost |
|---|---|---|---|---|
| Bedrock Classic (ADR-012) | ~$15 | ❌ vô hiệu | ❌ | độn tuyến tính |
| Bedrock Standard tier | ~$15–18 | ✅ | ❌ EN-only | độn tuyến tính |
| **Cascade (ADR-013)** | **<$1** | ✅ 7/7 đo | ✅ 4/4 + NLI 6/6 đo | T1 fixed; T2 chỉ sau khi T0/T1 lọc |

## Hành vi lỗi
- INPUT: regex luôn chạy; judge chết → **fail-open có chủ đích** (regex đã chặn tầng thô) — log warning.
- OUTPUT: ml-guard chết → rơi xuống Nova judge; judge chết → fail-open, **PII luôn mask**.
- Action Gate cart (excessive-agency) giữ ở `agent.py` — không đổi.

## Monitoring per-layer (trục "monitor được các layer")
- ml-guard: `/metrics` Prometheus (`ml_guard_decisions_total{action}`, latency avg).
- Services: log có cấu trúc `Grounding BLOCK (ml-guard contra=…)` / `(judge … said NO)` / `[Guardrail INPUT] blocked` — đếm được qua log backend (TF1-76).
- Eval report tự sinh: `docs/ai/evals/eval_mandate06_v5_report.md`.

## Consequences / risks
- Nova Lite injection judge = 1 call LLM phụ mỗi input (~550ms, $0.00002) — chấp nhận vì reviews path best-effort + cache 7d; copilot p95 5.7s vẫn trong trần.
- ml-guard image nướng model (~1.1GB) — build CI lâu hơn; đổi lại pod không egress HF.
- **Tài nguyên cho Local ML (Phase-2)** (áp dụng cho `shopping-copilot` và `product-reviews` pods):
  - **Dung lượng Disk/Image:** Tăng thêm **~1.1GB** (Model ProtectAI DeBERTa ~738MB + SpaCy model ~400MB) tải lúc build/chạy.
  - **Bộ nhớ RAM:** Cần cấp thêm ít nhất **1.5GB - 2.0GB RAM limit** cho mỗi pod (tổng limit tối thiểu khuyến nghị: **2.5GB per pod**) để load mô hình PyTorch và Presidio vào bộ nhớ mà không bị OOM (Out of Memory).
  - **CPU:** Khuyến nghị tăng CPU limit thêm **1.0 Core** per pod để CPU inference cho Local ML chạy mượt mà (giữ latency < 300ms cho phần Local ML check).
- Threshold NLI (0.5/0.3) chọn từ bench 17/07 — tune tiếp bằng eval khi có traffic thật.
- Region judge us-east-1 (default profile / IRSA role tương đương); SSO role bị chặn east-1 — ghi rõ trong integration để CDO cấp IAM đúng region cho pod.
