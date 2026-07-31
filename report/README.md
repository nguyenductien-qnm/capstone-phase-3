# Báo cáo và bằng chứng vận hành

Thư mục này lưu các artifact có thể kiểm tra lại: báo cáo Markdown, kết quả replay,
log JSONL và manifest dùng để tái hiện phép đo. Mỗi thư mục con phải phân biệt rõ:

- **Bằng chứng live:** lấy từ hệ thống/cluster đang chạy và giữ nguyên dữ liệu gốc.
- **Bằng chứng test/replay:** sinh từ test hoặc dữ liệu lịch sử, không được gọi là live.
- **Giới hạn:** phần nào chưa được deploy, chưa đo, hoặc dữ liệu nào có thể mất.

## Chỉ mục

| Artifact | Nội dung |
|---|---|
| [`tf1-103-structured-audit/`](tf1-103-structured-audit/) | Structured audit `trigger → action → verify → rollback` và postmortem cho TF1-103 |
| [`mandate22-thresholds/`](mandate22-thresholds/) | Đo threshold, circuit breaker và blast radius trên EKS |
| [`mandate22-mttr/`](mandate22-mttr/) | Đo MTTR trước/sau |
| [`mandate22-detection-gaps/`](mandate22-detection-gaps/) | Backtest các detection gap |
| [`mandate15/`](mandate15/) | Calibration detector và incident replay |
| [`mandate15-eks/`](mandate15-eks/) | Evidence detector trên EKS |
| [`mandate07b/`](mandate07b/) | Evidence alert routing |
| [`mandate5/`](mandate5/) | Báo cáo mandate 5 |
| [`credit-incident/`](credit-incident/) | Postmortem sự cố tài khoản/cloud cá nhân |

