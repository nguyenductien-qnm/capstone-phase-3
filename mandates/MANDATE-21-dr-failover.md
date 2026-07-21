# [DIRECTIVE #21] Mất nguyên một vùng hạ tầng - khách gần như không hay biết

**Từ:** Ban Rủi ro & Liên tục Kinh doanh (BCP/DR) - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 31/07/2026**
**Áp dụng:** toàn bộ Task Force · **tiên quyết: đã hoàn tất Directive #20 (backup + restore drill)**

---

## Bối cảnh
Backup (Directive #20) cho bạn lấy lại dữ liệu **sau khi** mất. Nhưng khi **mất đột ngột cả một vùng hạ tầng** - một Availability Zone chết vì mất điện, đứt mạng, hoặc một sự cố AZ của AWS - hệ phải **tự đứng vững hoặc phục hồi nhanh mà khách gần như không thấy**, không ngồi chờ ai restore tay. Directive #3 là **bảo trì có kế hoạch** (mình chủ động drain, biết trước). Directive này là thứ khó hơn hẳn: **mất không báo trước, giữa lúc có tải** - đúng cái phân biệt một hệ "chạy được" với một hệ **sống sót qua sự cố hạ tầng thật**.

> Directive này về **chịu mất hạ tầng và failover**. Phần backup/restore dữ liệu là #20 - ở đây coi như **đã có** và không chấm lại.

## Điều kiện chung (áp cho MỌI yêu cầu bên dưới)
- Drill **dưới tải thật** (giữ một mức tải liên tục qua load-generator), mentor xem **live**.
- Thước đo là **RTO thực** (bao lâu luồng ra tiền phục hồi SLO sau khi mất vùng) và **RPO** (có mất dữ liệu không). Không đo bằng "đã bật Multi-AZ".
- **Bar bắt buộc:** mất **1 AZ** → **0 mất dữ liệu** và luồng ra tiền phục hồi trong RTO đã cam kết (hoặc **không rớt SLO** nếu đã multi-AZ chịu tải song song). Chứng minh bằng số trên dashboard.

## Yêu cầu
1. **Chịu mất 1 AZ, không mất dữ liệu (bắt buộc).** Store managed chạy **Multi-AZ** (RDS/Aurora Multi-AZ; DynamoDB vốn multi-AZ); node group EKS trải **≥ 2-3 AZ**; workload luồng ra tiền có đủ replica trải AZ + PDB + topology-spread để mất 1 AZ không sập.
2. **Không SPOF theo AZ trên luồng ra tiền.** Không một service quan trọng nào nằm gọn trong một AZ mà AZ đó chết là đứt cả luồng browse → cart → checkout.
3. **Chịu một cú mất AZ thật, dưới tải (tâm điểm).** Đây **không** phải drain node êm ả (bảo trì chủ động) - mà là một AZ **biến mất đột ngột**: node mất kết nối giữa chừng, request in-flight đứt, endpoint phải tự bị gỡ, traffic phải dồn sang AZ lành, store managed phải tự failover. Cách chấm: **mentor sẽ chủ động gây mất một AZ, dưới tải, vào thời điểm bất chợt** - bạn **không biết trước AZ nào, lúc nào** - nên phải xây để chịu được **bất kỳ** AZ nào rơi, **bất kỳ lúc nào. Be ready.** Kết quả cần đạt: luồng browse → cart → checkout **phục hồi trong RTO cam kết**, **0 mất dữ liệu**, đơn đang checkout không mất.
4. **Phục hồi tự động, có kỷ luật.** Reschedule pod + failover store xảy ra **tự động** (K8s scheduler + managed failover), không phải người vào bấm tay từng bước mới lên lại; phần nào cần người thì có **runbook** rõ ràng, đo được trong RTO.
## Ràng buộc
- Trong ngân sách hiện tại (~$300/tuần/TF). Multi-AZ cho managed store + node trải AZ làm chi phí tăng **vừa phải** - chấp nhận. **Đừng** đốt credit dựng standby đắt tiền rồi để đó không drill được - mọi đồng chi phí phải đi kèm khả năng chứng minh chịu được sự cố.
- **Không hạ SLO / không nhân đôi bừa cho chắc** - phải đo được RTO thật khi mất AZ, không phải "bơm tài nguyên rồi khoe SLO đẹp".
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hoá flagd - xem Luật chơi trong RULES.
- **Tiên quyết #20**: phải có backup + đã restore drill được.

## Cách đo & nộp
- **Mentor test bất chợt, HV không tự dàn cảnh.** Dưới tải, mentor sẽ **chủ động gây mất một AZ** vào thời điểm không báo trước rồi quan sát hệ của bạn phục hồi. Nhiệm vụ của bạn là **xây hệ chịu được từ trước** - be ready mọi lúc, không phải chuẩn bị riêng cho buổi chấm. Cần thấy trên dashboard: traffic dồn sang AZ lành, store managed tự failover, **SLO dip rồi recover**. **RTO** = từ lúc SLO dip đến khi về ngưỡng; **RPO** = số đơn checkout mất (kỳ vọng 0). Console kèm: RDS Multi-AZ (AZ của primary đổi sau failover), node trải AZ, pod topology-spread.
- **ADR ký tên**: thiết kế DR đã chọn và **vì sao**, **RTO/RPO cam kết** (ít nhất ở mức mất 1 AZ), cái gì tự động cái gì cần runbook.

## Được nhìn ở trụ nào
Chính là **Reliability** (chịu mất AZ, không SPOF theo vùng, failover) và **Performance Efficiency** (phục hồi nhanh, giữ SLO khi mất một vùng). Chạm thêm **Operational Excellence** (DR runbook + drill có kỷ luật) và **Cost Optimization** (đánh đổi DR - chọn đúng mức dự phòng, không đốt tiền dựng dư thừa khi mức cần thiết đã đủ).

> Directive bắt buộc toàn TF, và là bài nặng nhất nhóm Reliability. Điểm nằm ở chỗ: **mất nguyên một AZ giữa giờ cao điểm mà khách gần như không hay biết, không mất một dòng dữ liệu** - đúng cái một hệ thống production trong ngành phải chịu được, không phải "chạy được lúc trời yên".
