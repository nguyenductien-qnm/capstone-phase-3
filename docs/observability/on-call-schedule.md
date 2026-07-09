# Observability On-Call Schedule & Handover

## Mục tiêu (Goals)
- Đảm bảo hệ thống TechX-Corp luôn có người trực (On-call) để giám sát và xử lý sự cố.
- Đạt được chỉ số MTTD (Mean Time To Detect) **< 5 phút** cho các sự cố P0 (như Checkout bị lỗi).

## Lịch trực luân phiên (On-Call Rotation - 7 ngày)

Dưới đây là lịch trực luân phiên tiêu chuẩn. Lưu ý: **Observability Engineer (On-Call Captain)** luôn ở trạng thái standby để hỗ trợ, không trực tiếp cầm primary. **TechLead** là điểm leo thang (escalation) cuối cùng.

| Ngày | Vai trò (Primary) | Thành viên | Ghi chú |
|---|---|---|---|
| Ngày 1 - 2 | Reliability Eng #2 | [Tên thành viên] | Giám sát Checkout & Payment |
| Ngày 3 - 4 | Reliability Eng #1 | [Tên thành viên] | Giám sát Frontend & Store |
| Ngày 5 | Cost/Platform Eng | [Tên thành viên] | Giám sát Kafka & Cost Burn |
| Ngày 6 | Reliability Eng #3 | [Tên thành viên] | Giám sát Product & Recommendations |
| Ngày 7 | Build Engineer | [Tên thành viên] | Giám sát CI/CD & ArgoCD pipelines |

## Quy trình Bàn giao ca (Handover) mỗi Standup
Mỗi ngày trong cuộc họp Standup, người trực ca trước sẽ bàn giao cho người trực ca sau các thông tin sau:
1. **Các Alerts đã kích hoạt trong 24h qua**: Số lượng báo động giả (False Positives) và cách giảm thiểu.
2. **Các Sự cố (Incidents)**: Tóm tắt nguyên nhân gốc (Root Cause) và giải pháp (Sử dụng Jaeger tracing).
3. **Chỉ số MTTD/MTTR**: Cập nhật báo cáo hàng tuần.

## MTTD/MTTR Weekly Report (Mẫu)
Báo cáo này được tổng hợp hàng tuần cho PM (Ops Review):
- **Tuần:** ...
- **Tổng số Incidents (P0/P1):** ...
- **MTTD trung bình:** ... (Mục tiêu: < 5p)
- **MTTR trung bình:** ...
- **Cost Burn Alert:** ... (Có cảnh báo nào về chi phí Kafka/EKS không)
