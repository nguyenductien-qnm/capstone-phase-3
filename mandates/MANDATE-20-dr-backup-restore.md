# [DIRECTIVE #20] Khôi phục được khi mất dữ liệu - chứng minh bằng một lần restore thật

**Từ:** Ban Rủi ro & Liên tục Kinh doanh (BCP/DR) - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 27/07/2026**
**Áp dụng:** toàn bộ Task Force (tầng dữ liệu + cấu hình cụm - do nhóm CDO cầm)

---

## Bối cảnh
Một hệ có khách thật sẽ có ngày mất dữ liệu - không phải "nếu" mà là "khi nào": ai đó lỡ tay `DROP`, một migration hỏng, một bug ghi đè, hoặc tệ hơn là bị mã hoá tống tiền. Directive #8 lo phần **thay đổi có kế hoạch** khi hệ đang chạy; directive này lo phần ngược lại - **mất mát ngoài kế hoạch**. Ai cũng nói "có backup rồi". Thứ phân biệt một đội vận hành trưởng thành không phải là **có bật backup**, mà là **restore lại được trong một khung thời gian cam kết, mất tối đa một cửa sổ dữ liệu cam kết** - và chứng minh bằng **một lần khôi phục thật**, không phải bằng ảnh chụp màn hình "đã bật".

> Directive này chỉ về **dữ liệu: backup, restore, độ bền**. Phần **chịu mất cả một vùng hạ tầng** (mất AZ/region, failover dưới tải) là **chuyện khác, không nằm trong directive này** - ở đây **không** đụng tới đó.

## Điều kiện chung (áp cho MỌI yêu cầu bên dưới)
- Thước đo là **RPO** (mất tối đa bao nhiêu dữ liệu - đo bằng thời gian) và **RTO** (khôi phục xong trong bao lâu) - **không** đo bằng "đã bật backup". Cam kết một con số RPO/RTO cho từng tầng dữ liệu và chứng minh đạt.
- Chứng minh bằng **drill thật**: gây mất/hỏng dữ liệu có kiểm soát rồi khôi phục. Restore vào **môi trường tách biệt**, không đè lên production đang chạy.
- Không dùng cột **$** để đánh giá (account chạy credit → $ ≈ 0). Đánh giá bằng RPO/RTO đạt được + độ toàn vẹn dữ liệu sau restore.

## Yêu cầu
1. **Không sót store nào trên luồng ra tiền.** Backup tự động cho **mọi** stateful store phục vụ browse → cart → checkout: RDS/Aurora (automated backup + snapshot), DynamoDB (PITR), volume/EBS (snapshot), và **trạng thái cụm/hạ tầng** (manifest GitOps/IaC, tham chiếu secret, config) để dựng lại được - không phải chỉ backup mỗi database.
2. **Đặt RPO/RTO rõ ràng, có cadence tương xứng.** Ghi trong ADR mục tiêu RPO/RTO cho từng tầng dữ liệu; tần suất backup phải **đủ để đạt RPO** đã cam kết (RPO 1 giờ mà backup mỗi ngày là mâu thuẫn).
3. **Point-in-time restore chứng minh được.** Khôi phục một store về **một mốc thời gian trước sự cố**, ra môi trường tách biệt - không chỉ restore snapshot mới nhất.
4. **Tested restore drill (tâm điểm).** Giả lập mất/hỏng dữ liệu (drop bảng / xoá item / ghi hỏng) rồi **khôi phục và chứng minh dữ liệu trở lại đúng**, trong **RTO đã cam kết**. Không chấp nhận "đã bật backup nhưng chưa từng restore thử" - đó chính là chỗ hầu hết đội gãy.
5. **Backup phải an toàn.** Mã hoá at-rest; **tách quyền** để người vận hành thường **không xoá được backup** (chống nhầm tay và ransomware); retention hợp lý - đủ để khôi phục, không giữ vô tận.

## Ràng buộc
- Trong ngân sách hiện tại (~$300/tuần/TF). Backup/snapshot storage rẻ - **đừng** lấy cớ directive này để dựng standby đắt tiền (đó là chuyện khác, không phải backup).
- **Không đè / không phá production** khi drill - restore ra môi trường tách biệt, không làm rớt khách thật.
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hoá cơ chế sự cố (flagd) - xem Luật chơi trong RULES.

## Phải nộp
- **Làm trước mặt mentor** (hoặc hẹn khung giờ, quay video): gây **mất dữ liệu có kiểm soát → restore → chứng minh dữ liệu trở lại đúng**, và **đo RTO thực**. Mentor xem console (RDS automated backup/PITR, DynamoDB PITR, danh sách snapshot, chính sách xoá) + toàn bộ drill.
- **ADR ký tên**: RPO/RTO từng tầng dữ liệu, chiến lược backup + cadence, retention, **ai được xoá backup** (tách quyền), và cách chạy drill khôi phục.

## Được nhìn ở trụ nào
Chính là **Reliability** (độ bền dữ liệu, khôi phục được sau mất mát) và **Operational Excellence** (drill có kỷ luật, có runbook restore - không phải "backup trên giấy"). Chạm thêm **Security** (mã hoá backup, tách quyền chống xoá/ransomware) và **Cost Optimization** (retention hợp lý, không giữ backup vô tận).

> Directive bắt buộc toàn TF. Điểm nằm ở chỗ: khi dữ liệu mất, bạn **lấy lại được trong thời gian đã cam kết, mất không quá cửa sổ đã cam kết** - và bạn chứng minh điều đó bằng **một lần restore thật ngay trước mặt mentor**, không phải bằng lời hứa "có backup rồi".
