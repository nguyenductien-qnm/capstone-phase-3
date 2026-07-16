# [DIRECTIVE #1] Storefront công khai, mọi cổng vận hành phải riêng tư

**Từ:** Ban Hạ tầng & Bảo mật - TechX Corp
**Hiệu lực:** ngay khi nhận · hoàn tất trước **thứ Ba 14/07/2026**
**Áp dụng:** toàn bộ Task Force

---

## Bối cảnh
Hiện các cổng nội bộ của hệ thống (dashboard, observability, control-plane triển khai…) đang hoặc có nguy cơ phơi ra internet cùng với storefront. Đây là bề mặt tấn công lớn - những công cụ này để lộ dữ liệu vận hành, thông tin hệ thống, thậm chí quyền triển khai. Khách hàng chỉ cần vào được storefront; mọi thứ còn lại không được để công khai.

## Yêu cầu
1. **Storefront giữ công khai.** Trang bán hàng (cổng khách vào) phải truy cập được qua internet công khai, không gián đoạn, không tụt SLO checkout.
2. **Mọi cổng vận hành / nội bộ phải riêng tư** - chỉ vào được qua **VPN / tunnel / mạng riêng**, không phơi ra internet công khai. Gồm (không giới hạn):
   - Observability: **Grafana, Jaeger**, các dashboard, UI xem log/metric/trace.
   - Control-plane triển khai: **ArgoCD** / CD UI và mọi console/admin tương tự.
3. **Cách truy cập riêng tư do TF tự chọn.** Dùng VPN, tunnel, hay bastion là tùy các bạn - BTC **không chỉ định công cụ**. Chỉ cần đạt hai điều: internet công khai **không** vào được các cổng này, người có quyền **vẫn** vào được.
4. **BTC / người chấm phải truy cập được để đánh giá.** Cung cấp cho BTC cách vào các cổng vận hành khi được yêu cầu (mời VPN / tunnel / hướng dẫn truy cập).

## Ràng buộc
- Không làm gián đoạn storefront và không phá SLO trong lúc cắt chuyển.
- Nằm trong ngân sách hiện tại.
- Không đụng / vô hiệu hóa cơ chế sự cố (flagd) - xem Luật chơi trong RULES.

## Phải nộp
- **Cách truy cập vào các cổng vận hành** (VPN / tunnel / đường riêng) để **mentor tự vào kiểm tra**. Mentor sẽ tự xác nhận: storefront vẫn vào được công khai, còn Grafana / Jaeger / ArgoCD chỉ vào được qua đường riêng.

## Được nhìn ở trụ nào
Chính là **Security** (giảm bề mặt tấn công, least-exposure, kiểm soát truy cập). Chạm thêm **Reliability** (không phá storefront khi cắt chuyển) và **Auditability** (ghi lại ai truy cập cổng vận hành, khi nào).

> Đây là directive bắt buộc toàn TF, thực thi trong ràng buộc, không thương lượng phạm vi. Cách các bạn thiết kế và cắt chuyển an toàn là phần được đánh giá.
