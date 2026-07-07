# Decision Log (ADR) - TF1 / AI Team (AIO03)

---

## ADR-001 - Sử dụng Valkey Caching cho Review Summary
- **Trạng thái:** Đề xuất (Proposed)
- **Ngày:** 2026-07-07
- **Người ký:** Định Nguyễn (AI Team Lead) & AI Team
- **Trụ:** Cost Optimization & Performance Efficiency
- **Bối cảnh:** Lời gọi LLM AWS Bedrock để sinh tóm tắt reviews sản phẩm tiêu thụ lượng tokens lớn và tốn độ trễ (1.5s+ latency). Khi CDO chạy các kịch bản load-test giả lập tải người dùng cao, chi phí token sẽ tăng đột biến và nhanh chóng làm cháy ngân sách $300/tuần.
- **Quyết định:** Tích hợp hệ thống lưu trữ đệm **Valkey (Redis-compatible)**. Bản tóm tắt của mỗi `product_id` sẽ được cache lại với thời gian sống (TTL) là 24 giờ. Khi có request xem sản phẩm, server AI sẽ kiểm tra cache trước; nếu cache hit thì trả về luôn, nếu cache miss mới gọi Bedrock và ghi đè vào cache.
- **Phương án khác đã cân:**
  - *Option A: Lưu cache cục bộ trong RAM (In-memory cache)* $\rightarrow$ Bị loại vì hệ thống chạy nhiều bản sao (replicas), cache RAM sẽ bị bất đồng bộ dữ liệu giữa các pods.
  - *Option B: Không dùng cache* $\rightarrow$ Bị loại vì chi phí token Bedrock quá cao và không đạt SLO độ trễ dưới tải lớn.
- **Cost Δ:** Tiết kiệm khoảng $60 - $120/tuần tiền token Bedrock dưới tải cao. Chi phí chạy thêm 1 pod Valkey trong cụm rất nhỏ (~$5/tuần tài nguyên EKS).
- **Ảnh hưởng SLO:** Giảm độ trễ phản hồi trang sản phẩm (p95 latency) từ >1.5s xuống <100ms cho các trường hợp cache hit, giữ vững SLO storefront.
- **Rollback:** Cấu hình qua Flagd feature flag `llmReviewsCacheEnabled`. Nếu có sự cố cache, chuyển flag về `false` để gọi thẳng Bedrock mà không cần build/redeploy code.
- **Hệ quả:** 
  - ✅ Giảm thiểu chi phí token Bedrock và giảm độ trễ phản hồi cực lớn cho người dùng.
  - ⚠️ Dữ liệu tóm tắt review có thể bị lệch thông tin tối đa 24 giờ nếu sản phẩm nhận thêm review mới trong ngày (chấp nhận được đối với tính năng tóm tắt).

---

## ADR-002 - Cơ chế định tuyến và dự phòng (Fallback & Routing) cho API LLM
- **Trạng thái:** Đề xuất (Proposed)
- **Ngày:** 2026-07-07
- **Người ký:** Định Nguyễn (AI Team Lead) & AI Team
- **Trụ:** Reliability
- **Bối cảnh:** API AWS Bedrock có thể gặp lỗi mạng, lỗi quá tải (HTTP 429 Rate Limit) hoặc timeout phản hồi chậm. Nếu không có cơ chế dự phòng, Storefront sẽ bị treo phần review sản phẩm hoặc hiển thị trang trắng cho khách hàng.
- **Quyết định:** Thiết lập cơ chế định tuyến và dự phòng tự động:
  1. Mặc định gọi model chất lượng cao **Claude 3.5 Sonnet** để sinh tóm tắt chất lượng nhất.
  2. Nếu gặp lỗi 429, 500 hoặc cuộc gọi bị timeout quá 1.0 giây $\rightarrow$ Tự động chuyển hướng (fallback) cuộc gọi sang **Claude 3.5 Haiku** (tốc độ nhanh hơn, rẻ hơn, giới hạn rate limit riêng biệt).
  3. Nếu Haiku vẫn lỗi $\rightarrow$ Trả về bản tóm tắt mặc định/mock và ghi nhận lỗi hệ thống.
- **Phương án khác đã cân:**
  - *Option A: Chỉ thực hiện cấu hình Retry (exponential backoff)* $\rightarrow$ Bị loại vì nếu Bedrock bị sập hoặc rate limit kéo dài, retry liên tục sẽ làm tăng độ trễ p95 và làm treo cổng thanh toán/storefront.
- **Cost Δ:** Giảm chi phí token khi hệ thống tự động chuyển vùng gọi sang Haiku (giá chỉ bằng 1/5 Sonnet) trong thời gian cao điểm.
- **Ảnh hưởng SLO:** Đảm bảo tỷ lệ lỗi (error rate) của các dịch vụ AI luôn dưới 0.1%, giữ vững SLO độ trễ storefront dưới 1s.
- **Rollback:** Cấu hình qua Flagd feature flag `llmReviewsFallbackEnabled` để bật/tắt cơ chế này.
- **Hệ quả:**
  - ✅ Đảm bảo tính sẵn sàng rất cao cho trang web ngay cả khi dịch vụ LLM đám mây gặp sự cố.
  - ⚠️ Chất lượng tóm tắt của Haiku có thể kém hơn Sonnet một chút trong thời gian sự cố (chấp nhận được để giữ đèn hệ thống sáng).
