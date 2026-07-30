# [DIRECTIVE #12 · chỉ TF4] Kiểm toán không thể bị đánh bại

**Từ:** Ban Kiểm toán & An ninh - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 20/07/2026**
**Áp dụng:** **chỉ Task Force 4** (nhóm CDO chuyên trách Auditability)

---

## Bối cảnh
Ở Directive #4, các bạn đã chứng minh log **không xóa được** (Object Lock). Nhưng một kẻ tấn công khôn ngoan có **ba cách vô hiệu hóa kiểm toán mà không cần xóa dòng nào**:
- **Làm mù** - tắt/dừng đường ghi log trước khi ra tay (blind window).
- **Làm hụt** - hoạt động ở chỗ **không được ghi** (ví dụ đọc dữ liệu / kéo secret khi data-event log tắt → exfiltration vô hình).
- **Làm mỏng** - log ở mức quá sơ sài để không dựng lại được **nội dung** đã thay đổi.

Bài này bắt các bạn **bịt cả ba** và chứng minh audit trail **đủ và toàn vẹn về mật mã**, không phải "append-only" nói suông.

## Yêu cầu
1. **Không có cửa sổ mù.** Không ai - kể cả admin của chính TF4 - **tắt/dừng được đường ghi log mà không bị chặn hoặc không để lại vết báo động**. Chứng minh bằng thiết kế: đường ghi log nằm ngoài tầm với của người vận hành (ví dụ trail ở phạm vi tổ chức / chặn quyền StopLogging bằng SCP), và bản thân lệnh tắt cũng là một sự kiện được ghi + kêu.
2. **Log đúng thứ cần - đóng coverage gap.** Hành động **đọc dữ liệu nhạy cảm** (object trong S3, secret) và **thay đổi cấu hình quan trọng** phải để lại vết, không chỉ các sự kiện quản trị (management events). Chỉ rõ: nếu kẻ tấn công đọc trộm secret hoặc kéo cả bucket, các bạn **có vết để biết không**.
3. **Chứng minh log toàn vẹn + đủ về mật mã.** Không phải "log của chúng em append-only" mà là bằng chứng kỹ thuật: chuỗi digest ký số / cơ chế xác minh (ví dụ CloudTrail log file integrity validation) chứng minh **không một sự kiện nào bị thêm, xóa hay sửa lén**, và không có khoảng trống bị nuốt.
4. **Giữ đủ lâu.** Thời gian lưu trữ đủ để điều tra một cuộc tấn công **kéo dài** - kẻ có thể ở trong hệ nhiều ngày trước khi lộ. Nêu rõ retention và vì sao đủ.

## Ràng buộc
- Trong ngân sách hiện tại (~$300/tuần/TF).
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hóa flagd.

## Phải nộp
Cho mentor **tự thử đánh bại**, không nghe khai - ba đòn:
- **Làm mù:** mentor thử **tắt/dừng ghi log** (StopLogging) hoặc xóa cấu hình trail → phải **bị chặn, hoặc kêu ngay**, và chỉ ra vết cuối cùng "ai tắt, lúc mấy giờ".
- **Làm hụt:** mentor thực hiện một hành động **đọc dữ liệu** → team chỉ ra **vết trong log** (nếu không có vết = coverage gap chưa bịt).
- **Làm mỏng/sửa:** team chạy **xác minh toàn vẹn** (log file integrity validation hoặc tương đương) ngay trước mặt, chứng minh chuỗi log không bị thêm/xóa/sửa.

## Được nhìn ở trụ nào
Chính là **Auditability** (độ tin cậy của bản ghi: không mù, không hụt, không sửa được, giữ đủ lâu) và **Security** (chống lại chính đòn nhắm vào hệ kiểm toán). Chạm **Operational Excellence** (kỷ luật cấu hình log).

> Directive riêng cho team Audit TF4, nối tiếp #4. Ở #4 các bạn chứng minh **log không xóa được**; ở đây chứng minh **kẻ tấn công không thể làm hệ kiểm toán của các bạn mù, hụt hay giả** - và bản ghi đứng vững như bằng chứng.
