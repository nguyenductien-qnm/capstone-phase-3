# [DIRECTIVE #18] Hoá đơn ẩn - cắt tiền ngoài node compute

**Từ:** Ban Sản phẩm & Tài chính - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 22/07/2026**
**Áp dụng:** toàn bộ Task Force (phần CDO)

---

## Bối cảnh
Directive #13 đã cắt phần lớn tiền ở **node compute** (spot, autoscale, right-size). Nhưng hoá đơn AWS còn nhiều dòng **ẩn** mà ít ai để ý - và trên một hệ microservice + observability dày như thế này thì không nhỏ: **truyền dữ liệu cross-AZ / NAT gateway**, **storage** (EBS sai loại/thừa, volume mồ côi, snapshot giữ vô hạn), và **khối lượng telemetry** (log/trace/metric sinh ra khổng lồ, giữ full-fidelity vô hạn). Đây là chỗ rò tiền lặng lẽ, cắt được mà **gần như không đụng app**.

## Điều kiện chung
- Account đang chạy credit nên cột **$ ≈ 0, không dùng được** - đo bằng **Usage** (GB-months storage, GB data-transfer, volume telemetry/span-per-giây, số giờ NAT). "Rẻ hơn" = cùng chức năng mà tiêu ít đơn vị hơn.
- Cắt gì cũng phải **không mất khả năng vận hành/điều tra** - đừng tắt observability tới mù, đừng xoá nhầm dữ liệu đang cần.

## Yêu cầu
1. **Không tài nguyên mồ côi.** Không EBS volume ở trạng thái available (unattached), không EIP không gắn, không snapshot/AMI rác, không load balancer / target group không dùng. Dọn sạch thứ đang tính tiền mà không phục vụ gì.
2. **Storage đúng loại + có vòng đời.** EBS chuyển gp2 → **gp3** (rẻ hơn ở cùng hiệu năng), right-size dung lượng theo dùng thật; snapshot có **lifecycle** (không giữ vô hạn); S3 (nếu có) có lifecycle/tier.
3. **Cắt data-transfer ẩn.** Giảm traffic **cross-AZ** không cần thiết (đặt traffic/replica khôn); thay **NAT gateway** bằng **VPC endpoint** cho các call nội bộ AWS (S3/ECR/API) để bớt giờ NAT + data processing.
4. **Telemetry không đốt tiền.** Log/trace/metric có **sampling** hợp lý + **retention** hữu hạn + kiểm **cardinality** (label/metric nổ) - giữ đủ để vận hành, không giữ full-fidelity vô thời hạn.
5. **Chỉ ra top cost-driver ngoài compute và đã cắt.** Biết dòng nào ngoài node đang tốn nhất, và chứng minh nó giảm.

## Ràng buộc
- Giữ SLO và **giữ khả năng quan sát/điều tra** - cắt telemetry mù là fail.
- Trong ngân sách (~$300/tuần/TF). Storefront public, cổng vận hành private (Directive #1); không đụng flagd.

## Phải nộp
- Cho mentor xem (đọc console, không cần script): **danh sách tài nguyên mồ côi đã dọn**, **EBS gp3 + volume right-size**, **NAT → VPC endpoint** (hoặc lý do), **telemetry volume/retention trước-sau**, và **top cost-driver ngoài compute** đã cắt - kèm bằng chứng SLO + khả năng điều tra vẫn giữ.

## Được nhìn ở trụ nào
Chính là **Cost Optimization** - phần chi phí ẩn ngoài compute (storage, data-transfer, telemetry). Chạm **Performance Efficiency** (storage đúng loại, bớt hop mạng) và **Operational Excellence** (kỷ luật vòng đời tài nguyên/telemetry).

> Directive bắt buộc toàn TF. Directive #13 cắt tiền node; directive này cắt **phần tiền còn lại mà không ai nhìn** - và chứng minh bằng usage, không phải bằng lời.
