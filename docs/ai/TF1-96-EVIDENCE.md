# 📋 EVIDENCE PACK — TF1-96
**Mã Task:** `TF1-96` | **Assignee:** Lê Kim Dũng (`03 lê kim dũng`)
**Sub-team:** AIE / Task Force 1 | **Branch:** `feat/TF1-96-multi-window-burn-rate`

---

## 1. Phương pháp & Cấu hình (Methodology)
Verify các câu query PromQL Error Budget Burn Rate theo chuẩn **Google SRE Workbook (Chapter 5: Multi-window Multi-burn-rate)**:
- **Fast Burn Rate (Critical/Page):** Cửa sổ `5m` **AND** `1h` (ngưỡng `> 14.4x`) cho Non-checkout (SLO 99.5%) và Checkout (SLO 99.0%).
- **Slow Burn Rate (Warning/Ticket):** Cửa sổ `30m` **AND** `6h` (ngưỡng `> 6.0x`).
- Toán tử `AND` giúp triệt tiêu các cảnh báo ảo (False Positive) ngắn hạn.

## 2. Các file thay đổi trong Task TF1-96
- `aiops/detector/rules.yaml`: 4 rules burn rate được cập nhật, bỏ nhãn DRAFT $\rightarrow$ `SEMANTICS-VERIFIED 21/07`.
- `aiops/detector/k8s_status.py`: Bổ sung try/except import safety.
- `detector_kpi_metrics.json`: Output KPI metrics.

## 3. Kết quả Kiểm thử (Verification)
- **Unit Tests:** `python -m pytest aiops/detector/test_detector.py -v` $\rightarrow$ **7/7 PASSED (100%)**.
- **Hiệu suất Detector (`evaluate_detector.py`):** Precision 68.75%, **Recall 91.67%**, F1 Score 78.57%, TTD 5 steps.

## 4. Audit Trail
| Trường | Giá trị |
|---|---|
| Change owner | Lê Kim Dũng (03 lê kim dũng) |
| Reviewer | Nguyễn Hữu Định (AI Lead) |
| Task ID | TF1-96 |
| Branch | `feat/TF1-96-multi-window-burn-rate` |
