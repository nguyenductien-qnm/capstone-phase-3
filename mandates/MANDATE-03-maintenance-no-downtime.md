# [DIRECTIVE #3] Bảo trì trong giờ vận hành - luồng ra tiền không được rớt

**Từ:** Ban Vận hành (SRE) - TechX Corp
**Hiệu lực:** 14/07/2026 · hoàn tất & nộp trước **16/07/2026**
**Áp dụng:** toàn bộ Task Force

---

## Bối cảnh
Hạ tầng cần bảo trì định kỳ ngay trong giờ có khách - thay / khởi động lại node, rollout phiên bản mới. Đây là việc thường ngày của một hệ thống production. Hiện luồng ra tiền (browse → cart → checkout) chưa chắc chịu được những việc đó mà không gây gián đoạn. Nhóm sẽ **tự thực hiện một đợt bảo trì (drain node / rolling-restart) trong một khung giờ hẹn trước với mentor** và cho thấy hệ thống chịu được, khách không bị ảnh hưởng.

## Yêu cầu
1. **Không downtime khách khi bảo trì.** Khi nhóm drain một node hoặc rolling-restart, luồng browse → cart → checkout phải **giữ SLO** (checkout ≥ 99%, browse/cart ≥ 99.5%, storefront p95 < 1s) - không rớt request khách.
2. **Không còn điểm chết đơn lẻ trên luồng ra tiền.** Không một service quan trọng nào được để "chết một cái là sập cả luồng".
3. **Chịu được pod chưa sẵn sàng.** Pod đang khởi động / chưa healthy không được nhận traffic khách.

BTC không kê cách làm - các bạn tự tìm chỗ mong manh và xử.

## Ràng buộc
- Trong ngân sách hiện tại (~$300/tuần/TF) - đừng chỉ nhân đôi mọi thứ cho chắc.
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hóa flagd (Luật chơi).

## Phải nộp
- Nhóm **hẹn mentor một khung giờ**, rồi **tự thực hiện drain node / rolling-restart** trước mặt mentor, đồng thời **show cách nhóm theo dõi SLO** (dashboard) trong suốt quá trình. Mentor thấy **SLO không rớt** + cách nhóm monitor → **confirm OK là đạt**.

## Được nhìn ở trụ nào
Chính là **Reliability** - bỏ điểm chết đơn lẻ, chịu được bảo trì / mất node, readiness đúng. Chạm thêm **Performance Efficiency** (làm gọn trong ngân sách) và **Auditability** (ghi lại thay đổi).

> Directive bắt buộc toàn TF. Điểm nằm ở chỗ hệ thống **chịu được việc thường ngày (deploy, mất node) mà khách không hề hay biết**.
