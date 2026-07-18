# [DIRECTIVE #11 · chỉ TF4] Bắt tại trận - phát hiện, không chỉ điều tra

**Từ:** Ban Kiểm toán & An ninh - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 20/07/2026**
**Áp dụng:** **chỉ Task Force 4** (nhóm CDO chuyên trách Auditability)

---

## Bối cảnh
Ở Directive #4, các bạn đã chứng minh **dựng lại được sự thật SAU khi có chuyện**. Nhưng kiểm toán hỏi tiếp một câu khó hơn: **khi một hành động nguy hiểm đang diễn ra, hệ của các bạn có KÊU không, và kêu sau bao lâu?** Log nằm im chờ điều tra không phải là phát hiện. Một kẻ tấn công có thể thao tác hàng giờ trước khi ai đó tình cờ mở log ra xem - lúc đó đã muộn. Bài này bắt các bạn biến audit trail thụ động thành **cảnh báo chủ động, đo được**.

## Yêu cầu
1. **Danh mục hành động nguy hiểm cần bắt.** Tự liệt kê + biện minh những sự kiện đáng báo động, ví dụ: tắt/sửa đường ghi log (CloudTrail StopLogging/UpdateTrail), thay đổi IAM/quyền (CreateAccessKey, AttachRolePolicy, CreateUser/Role, sửa trust policy), thêm EKS access entry, truy cập secret bất thường, hành động admin từ IP/vị trí lạ, xóa log hoặc tài nguyên hàng loạt. Không cần đủ hết - cần **đúng cái nguy hiểm nhất và giải thích được vì sao chọn**.
2. **Cảnh báo chạy thật, tới tay người.** Mỗi sự kiện nguy hiểm → một cảnh báo **có định tuyến** (kênh chat / email / on-call), kèm đủ ngữ cảnh **ai - gì - khi - từ đâu** để người nhận bắt tay điều tra ngay, không phải đi đào lại từ đầu.
3. **Đo được thời gian phát hiện.** Không dừng ở "có cảnh báo" mà phải biết **kêu sau bao lâu** kể từ lúc hành động xảy ra (time-to-detect). Nêu con số mục tiêu và chứng minh đạt.
4. **Đáng tin, không nhiễu.** Phân biệt hành động hợp lệ (CI/CD, bảo trì on-call có kế hoạch) với bất thường - cảnh báo phải đủ tin để không ai tắt tiếng nó. Nói rõ cách các bạn giảm nhiễu.

## Ràng buộc
- Trong ngân sách hiện tại (~$300/tuần/TF).
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hóa flagd.

## Phải nộp
Cho mentor **tự bấm nút kiểm**, không nghe khai:
- Mentor tự thực hiện **một hành động nguy hiểm vô hại** (ví dụ tạo một IAM access key test, thêm một EKS access entry, hoặc tắt-rồi-bật một trail test) → **cảnh báo của team phải kêu trong ngưỡng đã cam kết**, hiện đủ ai/gì/khi/đâu.
- Cho xem **đường cảnh báo đi tới đâu** (nguồn sự kiện → xử lý → người nhận) và **con số time-to-detect** đo được.

## Được nhìn ở trụ nào
Chính là **Auditability** (biến log thành tín hiệu sống) và **Security** (phát hiện tấn công đang diễn ra). Chạm **Operational Excellence** (kỷ luật cảnh báo - đúng việc, đúng người, ít nhiễu).

> Directive riêng cho team Audit TF4. Điểm nằm ở chỗ: khi có kẻ làm điều nguy hiểm, hệ của các bạn **kêu lên đúng lúc và đúng người** - chứ không đợi tới lúc ai đó mở log ra mới biết.
