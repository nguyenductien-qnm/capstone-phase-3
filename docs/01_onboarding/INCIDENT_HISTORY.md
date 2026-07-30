# Lịch sử sự cố

Trích sổ sự cố của đội vận hành trước. Đây là những lần hệ thống từng trục trặc và **đã được xử lý xong**. Đọc để hiểu hệ thống này hay yếu ở đâu - lịch sử thường lặp lại.

> Lưu ý: đây là sự cố **quá khứ đã đóng**. Nó không phải danh sách lỗi hiện tại, cũng không phải gợi ý đáp án. Nhưng nó cho bạn biết những vùng nào của hệ thống mong manh.

---

## INC-1 · Checkout chậm và lỗi giờ cao điểm (đã đóng)

**Khi nào:** đợt khuyến mãi quý trước.
**Triệu chứng:** vào giờ cao điểm, tỉ lệ đặt hàng thành công tụt xuống ~95%, p95 latency checkout vọt lên vài giây. Khách bỏ giỏ.
**Nguyên nhân gốc:** số kết nối tới cơ sở dữ liệu cạn khi tải tăng đột biến; request xếp hàng chờ kết nối rồi timeout.
**Đã xử:** chỉnh lại kích thước connection pool + thêm timeout hợp lý, thêm cảnh báo khi pool gần cạn.
**Bài học còn treo:** hệ thống chưa được kiểm chứng kỹ dưới tải cao; hành vi khi quá tải chưa được thiết kế rõ.

## INC-2 · Mất giỏ hàng sau khi node được lên lịch lại (đã đóng)

**Khi nào:** một lần bảo trì cụm.
**Triệu chứng:** một nhóm khách mất sạch giỏ hàng đang có, phải thêm lại từ đầu.
**Nguyên nhân gốc:** lớp lưu giỏ hàng chạy đơn lẻ, không có bản sao; khi pod bị lên lịch lại thì state trong bộ nhớ mất theo.
**Đã xử:** khôi phục dịch vụ, thông báo khách. Bản sao/độ bền dữ liệu được đưa vào danh sách việc nhưng **chưa làm dứt điểm**.
**Bài học còn treo:** vài thành phần vẫn là điểm chết đơn lẻ (single point of failure).

## INC-3 · Lỗi thanh toán trong lúc deploy (đã đóng)

**Khi nào:** một lần release thường kỳ.
**Triệu chứng:** trong vài phút lúc deploy, một phần request thanh toán lỗi dù bản mới không có bug.
**Nguyên nhân gốc:** traffic bị đẩy vào pod mới **trước khi nó sẵn sàng** - thiếu readiness gating nên request rơi vào instance chưa lên xong.
**Đã xử:** thêm kiểm tra sẵn sàng cho service đó; lần deploy sau êm.
**Bài học còn treo:** cơ chế deploy an toàn (probe, rollout có kiểm soát, rollback) chưa được áp đồng bộ cho toàn hệ.

---

**Điểm chung:** ba sự cố trên đều xoay quanh **độ tin cậy dưới áp lực** - quá tải, mất node, deploy. Hệ thống chạy tốt lúc bình thường nhưng chưa được làm cứng cho lúc có biến. Khi bạn tiếp quản, đây là vùng đáng soi trước tiên.
