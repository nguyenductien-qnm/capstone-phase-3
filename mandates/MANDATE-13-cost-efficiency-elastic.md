# [DIRECTIVE #13] Cắt hoá đơn compute mà khách không hay biết

**Từ:** Ban Sản phẩm & Tài chính - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 24/07/2026**
**Áp dụng:** toàn bộ Task Force (phần cluster / cost - do nhóm CDO cầm)

---

## Bối cảnh
Finance soi lại hoá đơn AWS và thấy phần lớn tiền đổ vào **EC2 node của EKS** - chạy toàn on-demand, node bật 24/7 kể cả lúc ít khách. Đây là chỗ cắt được nhiều nhất mà gần như **không phải đụng vào app**: chạy trên capacity rẻ hơn (**spot**) và chỉ trả tiền cho tài nguyên đang thật sự cần (**autoscale theo demand, co lại lúc rảnh**). Cái khó - và là thứ phân biệt đội vận hành giỏi - là làm được thế mà **khách không hề hay biết**: một spot node bị thu hồi bất ngờ, hay cluster co lại sau peak, đều không được rớt một request nào trên luồng ra tiền. Directive #2 đã hỏi "sống được lúc flash-sale không"; lần này hỏi thứ khác - **chạy có gọn tiền không, trên cả ngày chứ không chỉ lúc đỉnh**.

## Điều kiện chung (áp cho mọi yêu cầu bên dưới)
- Đo trên một **đường cong tải biến thiên** (thấp → cao → thấp) chạy qua load-generator, không phải flat hay idle - để nhìn được cả lúc scale up lẫn scale down.
- Thước đo là **số giờ-node (node-hours) phục vụ cùng một lượng tải** cùng với **% spot / % Graviton**, **không phải hoá đơn $** (account đang chạy credit nên cột $ ≈ 0, không dùng được). "Rẻ" = cùng tải mà tốn ít giờ-node hơn + chạy trên capacity rẻ hơn. Luôn đi kèm SLO có giữ hay không - rẻ mà rớt khách thì không tính.

## Yêu cầu
1. **Chạy trên capacity rẻ.** Đưa các workload stateless đủ điều kiện sang **spot** (capacity type spot cho node group / Karpenter) - mục tiêu **> 50% compute chạy trên spot**, cost/node-hour giảm đo được.
2. **Trả tiền theo demand.** Cluster autoscaler / Karpenter: tải lên thì thêm node giữ SLO, **tải xuống thì drain + bỏ node** - không để node bật 24/7 lúc vắng khách. Phải thấy được lúc tải thấp số node (và tiền) **tụt xuống thật**, không park ở đỉnh.
3. **Sống sót spot interruption (phần khó nhất).** Kill một spot node giữa lúc đang có tải → luồng browse → cart → checkout **không rớt request nào**. Cần PDB + đủ replica + reschedule mượt + drain graceful. Đây là cái giá của việc xài spot, và là chỗ chấm nặng.
4. **Đủ tín hiệu để scheduler quyết đúng.** Set request "vừa đủ" cho các service để HPA/autoscaler ra quyết định chuẩn - **không cần rightsize hoàn hảo từng pod**, chỉ cần đủ để scale hoạt động đúng, không bị chèn hay OOM.
5. **Đo được, so được (bằng console, không cần viết script).** Chứng minh trên cùng đường cong tải: **giờ-node cho cùng lượng tải giảm ≥ 30%** so baseline, **spot ≥ 50%**, có **Graviton**, và cluster **co xuống thật** lúc tải giảm - trong khi SLO vẫn giữ (checkout ≥ 99%, browse/cart ≥ 99.5%, storefront p95 < 1s). Đọc thẳng từ 3 màn hình ở phần **Cách đo & nộp**.

## Ràng buộc
- **Không hạ SLO để lấy cost** - rẻ mà rớt khách là fail.
- **Không giữ SLO bằng cách bơm on-demand cho chắc** - phải thật sự rẻ hơn baseline, không phải quăng tiền mua node rồi khoe SLO đẹp.
- Trong ngân sách hiện tại (~$300/tuần/TF). Storefront vẫn public, cổng vận hành vẫn private (Directive #1); không đụng / disable cơ chế sự cố (flagd) - xem Luật chơi trong RULES.

## Cách đo & nộp (quay video console - không cần viết script)
Không dùng hoá đơn $ (credit che thành ~$0). Chứng minh bằng **3 màn hình console**, quay video **before/after** trên cùng đường cong tải:

**① EC2 → Instances** — thêm cột **Lifecycle** + **Instance type** (+ Architecture): quay để thấy node nào là **spot**, họ instance gì, **arm64 hay x86**. → chứng minh lever Spot + Graviton, tức thì.

**② Cost Explorer → report Usage Quantity** (đây là **Usage**, KHÔNG phải Cost - vì credit chỉ che cột $, còn giờ chạy vẫn thật):
- Metric = **Usage quantity (Hours)** · Filter Service = **EC2 - Compute**
- Group by **Purchase Option** → cột **Spot vs On-Demand** (before: toàn on-demand; after: spot phình lên)
- Đổi Group by **Instance Type** → thấy x86 (t3/t3a) chuyển sang Graviton (t4g/c7g…)
- Granularity **Daily/Hourly** → **giờ-node tụt lúc tải thấp** = bằng chứng scale-down.

**③ Grafana (đã có sẵn)** — quay **live** trong lúc chạy load-curve:
- Panel **số node theo thời gian**: tải lên node lên, **tải xuống node xuống** (không park ở đỉnh).
- Panel **checkout success ≥ 99% + p95 < 1s** chạy suốt → SLO giữ trong khi cost giảm.

**Live (trước mặt mentor hoặc quay lại):** phần nặng nhất - **kill một spot node giữa lúc có tải → 0 request khách rớt** (nhìn trên panel ③).

Kèm **ADR ký tên**: chọn instance/spot pool nào, autoscaler/Karpenter cấu hình ra sao, chịu spot interruption bằng gì (PDB/replica/drain).

> Lưu ý: Cost Explorer trễ ~24h - dùng **②** cho trend/history, **①③** cho tức thì trong video. Đừng chờ CE cập nhật trong lúc đang quay.

## Được nhìn ở trụ nào
Chính là **Cost Optimization** (spot, pay-per-demand, không neo tiền ở đỉnh) và **Reliability** (chịu spot interruption, không SPOF khi node biến mất). Chạm thêm **Performance Efficiency** (co giãn theo tải) và **Operational Excellence** (đo đạc & tune có kỷ luật, không đoán).

> Directive bắt buộc toàn TF, thi head-to-head cùng một đường cong tải. Điểm nằm ở chỗ: bạn **cắt được hoá đơn compute đi đáng kể - chạy trên capacity rẻ, co theo demand - mà khách không hề hay biết, kể cả khi một spot node bị thu hồi giữa giờ cao điểm**. Đó là cái một đội vận hành cloud trưởng thành thực sự làm được, không phải "chạy được là xong".
