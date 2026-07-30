# [DIRECTIVE #9] Vận hành managed ở mức trưởng thành - thay đổi dưới tải, không rớt một request

**Từ:** Ban Vận hành (SRE) - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 19/07/2026**
**Áp dụng:** TF đã chạy trên managed service từ trước (đội chưa managed làm Directive #8 thay cho directive này - mỗi đội chỉ làm một trong hai)

---

## Bối cảnh
Đưa được store lên managed là một chuyện. Việc khó hơn hẳn - và là thứ phân biệt một đội vận hành trưởng thành - là **thay đổi hạ tầng dữ liệu khi nó đang phục vụ khách dưới tải, mà không một request nào rớt**. Đổi schema, nâng version, xoay credential trên một data store đang chạy live là chỗ ngay cả đội giỏi cũng hay làm hỏng: lock bảng, rớt kết nối, mất đơn giữa chừng.

> Directive này chỉ về **thay đổi có kế hoạch, zero-downtime, dưới tải**. Phần chịu-sự-cố / khôi-phục dữ liệu (DR, backup, restore) có directive **riêng** - ở đây **không** đụng tới đó.

## Điều kiện chung (áp cho MỌI yêu cầu bên dưới)
- Thực hiện **trong khi hệ thống đang chịu tải thật** (không phải lúc idle) - giữ một mức tải liên tục qua load-generator suốt thao tác.
- **Bar khắt khe hơn**: không phải "SLO ≥ 99%" mà là **0 request khách bị rớt** trong toàn bộ cửa sổ thay đổi. Chứng minh bằng số (error count = 0).

## Yêu cầu
1. **Online schema migration dưới tải (tâm điểm).** Áp một thay đổi schema phá vỡ trên một bảng lớn đang có traffic - ví dụ thêm cột NOT NULL, đổi kiểu cột, hoặc thêm index - theo kiểu **expand → backfill → dual-read/write → contract**, **không lock, không downtime, không rớt request**. Đây là bài app + DB phối hợp, không có tooling làm hộ.
2. **Nâng version lớn, zero-downtime.** Nâng engine version của ít nhất một store managed, dưới tải, khách không thấy gián đoạn.
3. **Đổi tham số cần reboot, zero-downtime.** Áp một thay đổi parameter-group loại bình thường phải restart instance, mà không gây downtime khách.
4. **Xoay credential live.** Rotate credential của store (Secrets Manager rotation) trong khi app vẫn chạy - app nhận credential mới live, không restart gây rớt.
5. **App chịu được lúc kết nối đổi.** Trong mọi thao tác trên, kết nối tới store đổi trong tích tắc - app phải nuốt được (retry / connection pool / RDS Proxy), không rớt request khách.

## Ràng buộc
- Trong ngân sách.
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hóa flagd.
- **Không** được giải quyết bằng "cắt bảo trì lúc vắng khách" - phải làm trong giờ vận hành, dưới tải, chấm bằng việc khách không bị ảnh hưởng.

## Phải nộp
- **Làm trước mặt mentor** (hoặc hẹn khung giờ): thực hiện **schema migration + nâng version + đổi param + xoay credential** trên managed layer **dưới tải**, mentor xem **error count = 0** suốt quá trình. Nộp kèm cách app xử lý blip kết nối (retry/pool/proxy) và cách schema migration giữ tương thích ngược (expand-contract).

## Được nhìn ở trụ nào
Chính là **Reliability** (thay đổi zero-downtime dưới tải) và **Operational Excellence** (kỷ luật thay đổi trên production). Chạm **Performance Efficiency** (chịu tải khi đổi), **Security** (credential rotation, encryption) và **Cost Optimization** (đánh đổi khi nâng/resize).

> Directive cho đội đã ở tầng managed - và là bài khó nhất trong nhóm này. Điểm nằm ở chỗ bạn **đổi được cả schema lẫn hạ tầng dữ liệu đang phục vụ khách dưới tải mà không một request nào rớt** - đúng cái một đội vận hành managed thực sự trưởng thành phải làm được.
