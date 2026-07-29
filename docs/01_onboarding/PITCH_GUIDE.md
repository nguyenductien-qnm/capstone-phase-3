# Buổi Pitch bảo vệ ưu tiên (cuối Tuần 1)

Đây là mốc đánh giá tư duy quan trọng nhất của Phase 3. Tài liệu này giải thích cụ thể buổi pitch là gì, bạn phải làm gì, và hội đồng sẽ vặn bạn thế nào.

## Bối cảnh

Cuối Tuần 1, sau khi đã dựng baseline chạy được và tự đánh giá hệ thống, mỗi TF trình bày **backlog ưu tiên** của mình trước một **hội đồng**. Hội đồng do mentor/BTC đóng vai ba stakeholder có lợi ích trái chiều - giống một buổi họp priority thật ở công ty:

| Vai | Quan tâm | Sẽ vặn bạn về |
|---|---|---|
| **PM** (Product) | Khách hàng, trải nghiệm, tính năng | "Khách được gì? Sao lo hạ tầng mà không cải thiện thứ khách thấy?" |
| **CFO** (Tài chính) | Chi phí, ROI | "Tốn bao nhiêu? Trong trần ngân sách chịu nổi không? Chứng minh đáng tiền." |
| **SRE lead** (Reliability) | Độ tin cậy, rủi ro kỹ thuật | "Rủi ro gì? Đã test chưa? Nếu làm sai thì sao?" |

## Bạn trình gì (15-20 phút)

1. **Hiểu hệ thống** - tóm tắt kiến trúc, SLO đang phải giữ, và những rủi ro lớn nhất bạn nhìn ra.
2. **Backlog ưu tiên** - danh sách việc top-N, đã xếp hạng rõ ràng.
3. **Bảo vệ thứ tự** - vì sao việc A trước việc B, và **cố ý bỏ gì lúc này**. Bỏ đúng cũng là một kỹ năng được chấm.

## Xếp ưu tiên theo cái gì

Công thức:

> **Ưu tiên = Rủi ro (khả năng xảy ra × mức nghiêm trọng) × Tác động business (hậu quả với khách / doanh thu / SLA / chi phí / uy tín).**

**Tác động business đo bằng chính onboarding packet, KHÔNG phải bằng "có phải feature hay không":**
- [SLO](SLO.md) → luồng nào ra tiền (checkout ≥ 99% là revenue-critical) → hỏng thì mất doanh thu trực tiếp.
- [BUDGET](BUDGET.md) → việc này tốn/tiết kiệm bao nhiêu trong trần.
- [INCIDENT_HISTORY](INCIDENT_HISTORY.md) + [ARCHITECTURE](ARCHITECTURE.md) → chỗ nào từng làm khách khổ, chỗ nào là điểm chết đơn lẻ.

Ví dụ một dòng backlog bảo vệ được: *"Ưu tiên 1: thêm replica + probe cho luồng checkout - hiện là single-replica (SPOF), nếu sập thì luồng ra tiền chết → impact business rất cao, mà chi phí thấp, nằm gọn trong ngân sách."*

## Hội đồng sẽ bắt bẻ thế nào

Họ vặn theo vai để stress-test tư duy và khả năng bảo vệ quyết định dưới áp lực:
- CFO: *"Thêm replica + Multi-AZ tốn bao nhiêu/tháng? Trong ~$300/tuần chịu nổi không? ROI đâu?"*
- SRE: *"Readiness probe set threshold gì? Đã test drain/failover chưa? Sai thì sao?"*
- PM: *"Tuần này khách được gì? Sao không ưu tiên thứ khách thấy trước?"*

Bị vặn là bình thường và được mong đợi. Điều được nhìn là bạn **giữ được lập luận, có số liệu, và điều chỉnh hợp lý khi bị phản biện** - hay lúng túng và bảo vệ bằng cảm tính.

## Cái gì làm nên một pitch tốt

- Đây là buổi của cả **nhóm** - cùng trình, cùng bảo vệ.
- Điều được nhìn là **tư duy, không phải slide đẹp**: chọn đúng việc đáng làm, quy được về rủi ro × business, đánh đổi rõ ràng, và giữ được lập luận khi bị vặn.

## Vì sao quan trọng nhất

Phase 3 đo *judgment* nhiều hơn *code*. Chọn sai ưu tiên = cày nhầm việc suốt hai tuần còn lại. Pitch là nơi lộ rõ nhất nhóm có nhìn ra đúng việc và bảo vệ được hay không - **trước khi** bắt tay làm. Chuẩn bị nó nghiêm túc.
