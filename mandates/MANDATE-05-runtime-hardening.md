# [DIRECTIVE #5] Runtime Hardenning - chặn cấu hình nguy hiểm ngay khi apply

**Từ:** Ban Platform Security - TechX Corp
**Hiệu lực:** ngay khi nhận · hoàn tất & nộp trước **thứ Sáu 17/07/2026**
**Áp dụng:** toàn bộ Task Force

---

## Bối cảnh
Trong một đợt review bảo mật, trên cluster có nhiều cấu hình "sung sướng": nhiều container **chạy quyền root**, image gắn tag di động (**không pin version**), một số workload **không define limit và request cho resources**, và cấu hình bảo mật container để trống. Với một hệ có khách thật, đây là rủi ro vận hành khó chấp nhận được - root trong container dễ thành root trên node, tag di động khiến không ai biết chính xác đang chạy version nào, một pod không giới hạn resources có thể kéo sập cả cluster. Ban security không chỉ muốn các bạn dọn hiện trạng, mà muốn **chặn nó tái diễn**: lần sau ai lỡ đẩy một manifest nguy hiểm, hệ thống phải **từ chối ngay**, không để đến user phản ánh.

## Yêu cầu
1. **Không container nào chạy root.** Buộc `runAsNonRoot`, drop mấy capability thừa - chỉ giữ đúng cái thật sự cần.
2. **Không xài image trôi.** Cấm tag kiểu `latest`; pin theo digest hoặc tag cố định để biết chính xác đang chạy version nào.
3. **Mọi workload phải define request/limit cho resources.** Để trống là một pod có thể ngốn sạch resources của node rồi kéo sập cả cluster.
4. **Enforce tự động, đừng rà tay.** Đẩy mấy luật trên vào **admission** (policy-as-code): manifest vi phạm bị **từ chối ngay lúc apply**, áp cho cả thay đổi sau này - chứ không phải một cái checklist ngồi soi bằng mắt.

## Ràng buộc
- Gần như **không tốn thêm chi phí hạ tầng** - đây là policy/config chạy trong cluster sẵn có, không phải dựng thêm service. Đừng mượn cớ directive này để xin thêm resources.
- **Không phá SLO lúc siết.** Bật enforce đột ngột dễ chặn nhầm cả workload đang chạy ngon - nên đi từ **audit** (chỉ cảnh báo) sang **enforce** (chặn thật) có kiểm soát, đừng làm rớt user thật.
- Storefront vẫn public, các cổng vận hành vẫn private (Directive #1); không đụng / disable cơ chế sự cố (flagd) - xem Luật chơi trong RULES.

## Phải nộp
- Cho mentor **tự apply thử một manifest vi phạm** (chạy root / tag `latest` / thiếu limit) và tận mắt thấy nó **bị từ chối**; đồng thời cluster đang chạy **không còn workload nào vi phạm**.
- **ADR ký tên**: luật nào đã enforce, luật nào còn để audit và vì sao, cắt chuyển audit→enforce ra sao để không chặn nhầm đồ thật.

## Được nhìn ở trụ nào
Chính là **Security** - least-privilege runtime, hardening container, giảm blast radius khi một pod bị chiếm. Chạm thêm **Operational Excellence** (guardrail tự động ràng buộc mọi deploy về sau) và **Cost Optimization** (bắt buộc define limit → scheduler xếp tải gọn, không cho một pod ngốn cả node).

> Directive bắt buộc toàn TF. Điểm nằm ở chỗ: sau directive này, một manifest nguy hiểm **không cách nào lọt vào cluster** - và team chứng minh bằng một lần apply thử bị chặn, không phải bằng lời hứa "sẽ để ý".
