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
  - **TTL (Time To Live):** 24 giờ (86400 giây).
  - **Bypass Flag:** Sử dụng OpenFeature flag `llmReviewsCacheEnabled` (kiểm soát qua flagd) để tắt cache nhanh khi cần kiểm thử hoặc cập nhật.
- **Phương án khác đã cân:**
  - *Option A - Sử dụng Amazon ElastiCache (Redis managed):* Độ bền cao và bảo mật hơn, tuy nhiên tăng chi phí cố định tối thiểu ~$30/tuần -> Vi phạm trần ngân sách AWS $300/tuần. Quyết định: Bỏ qua và dùng Valkey in-cluster.
- **Cost Δ:** Tiết kiệm khoảng **85% - 90%** chi phí gọi Bedrock API (giảm từ ~$80/tuần xuống còn ~$8/tuần cho các sản phẩm hot).
- **Ảnh hưởng SLO:** Giảm p95 latency của trang chi tiết sản phẩm từ **2.5s xuống < 100ms** khi cache hit, giữ vững cam kết SLO (< 1s).
- **Rollback:** Chuyển đổi flag `llmReviewsCacheEnabled` sang `false` để bypass cache và gọi trực tiếp Bedrock. Nếu Valkey bị sập, Reviews service tự động bỏ qua cache và log error.
- **Hệ quả:**
  - ✅ *Lợi ích:* Tiết kiệm chi phí vượt trội, cải thiện trải nghiệm khách hàng cực lớn.
  - ⚠️ *Đánh đổi:* Dữ liệu tóm tắt review bị trễ tối đa 24h so với các review mới cập nhật (chấp nhận được đối với hành vi người dùng).

---

## ADR-002 - Cơ chế Model Fallback & Retry cho cuộc gọi AWS Bedrock
- **Trạng thái:** Chấp nhận (Accepted)
- **Ngày:** 2026-07-08
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

