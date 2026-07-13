# [DIRECTIVE #2] Chịu được flash sale mà không tăng ngân sách

**Từ:** Ban Sản phẩm & Tài chính - TechX Corp
**Hiệu lực:** ngay khi nhận · hoàn tất trước **thứ Ba 14/07/2026**
**Áp dụng:** toàn bộ Task Force

---

## Bối cảnh
Marketing sắp chạy một đợt **flash sale** - dự kiến traffic tăng vọt nhiều lần so với ngày thường, dồn vào luồng browse/search và checkout. Tài chính **không duyệt tăng ngân sách hạ tầng** cho đợt này. Nói cách khác: hệ thống phải gánh tải lớn hơn hẳn mà vẫn giữ cam kết dịch vụ, trong đúng trần chi phí đang có. Không được xử bằng cách "quăng thêm tài nguyên cho xong".

## Yêu cầu
1. **Chịu được tải flash sale** - mục tiêu **200 user đồng thời (qua load-generator), giữ trong 15 phút** - mà vẫn **giữ SLO**: checkout ≥ 99%, browse/cart ≥ 99.5%, storefront p95 < 1s (xem `onboarding/SLO.md`). Cùng một cấu hình tải cho cả 4 TF để so công bằng.
2. **Không vượt trần ngân sách hiện tại** (~$300/tuần/TF, xem `onboarding/BUDGET.md`). **Chi phí trên mỗi đơn / mỗi request không được phình** khi tải tăng - đây là thước đo hiệu quả, không phải tổng chi.
3. **Tự tìm và xử điểm nghẽn.** Dưới tải, các nút thắt hiện có sẽ lộ ra (chia tài nguyên chưa hợp lý, service bão hòa, thiếu co giãn, hết bộ nhớ…). BTC không phát danh sách - các bạn tự phát hiện và xử.
4. **Co lên rồi phải co xuống.** Sau đỉnh tải, hệ thống trả tài nguyên về mức thường - không để tài nguyên (và tiền) neo ở đỉnh.

## Ràng buộc
- Giữ SLO trong suốt bài test, không gián đoạn khách.
- Storefront vẫn công khai; các cổng vận hành vẫn riêng tư (xem Directive #1).
- Không đụng / vô hiệu hóa cơ chế sự cố (flagd) - xem Luật chơi trong RULES.
- Tối ưu trong ngân sách, không phá kiến trúc để lấy điểm số ngắn hạn.

## Phải nộp
- **Kết quả load test** ở mức tải mục tiêu: cho thấy **SLO được giữ** và **chi phí nằm trong trần** (kèm cost trước/sau, hoặc cost trên mỗi đơn). Cho mentor cách chạy lại hoặc chứng kiến bài test để tự xác nhận.

## Được nhìn ở trụ nào
Đúng hai trụ **Performance Efficiency** (chịu tải, co giãn, tối ưu độ trễ, khử điểm nghẽn) và **Cost Optimization** (hiệu quả chi phí dưới tải, không phình cost khi scale). Chạm thêm **Reliability** (giữ SLO khi có biến).

> Directive bắt buộc toàn TF, thực thi trong ràng buộc. Điểm nằm ở chỗ **đánh đổi perf ⇄ cost được giải quyết khéo tới đâu**: gánh được tải mà vẫn gọn chi phí, không phải chọn một trong hai.
