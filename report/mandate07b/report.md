# Báo cáo — AI MANDATE #7b (Detection: chạy thật + đo đạc)

**Hạn:** thứ Bảy 25/07/2026 · **Trạng thái tại 2026-07-24:** code + harness xong, chạy sống PENDING (xem mục 4).

## 1. Yêu cầu mandate (tóm tắt từ `mandates/MANDATE-07-aiops-detection.md`)

- Ảnh/log detector kêu **end-to-end** khi bơm 1 sự cố + cách chạy lại.
- **Precision/recall/lead-time** đo trên **một bộ sự cố có nhãn** (K sự cố + giai đoạn bình thường), KHÔNG phải per-service.
- Cảnh báo theo mức ảnh hưởng (burn-rate, không spam) + mở rộng thêm service.

## 2. Đã có sẵn từ #7a (ADR-012, không lặp lại)

Detector hybrid static+3-sigma per-service, 13 rule live trên ≥6 service (checkout/cart/product-reviews/frontend/product-catalog/email), burn-rate multi-window, cooldown+dedup 2 lớp. Deploy `Deployment` liên tục trên EKS (`techx-tf1`).

## 3. Việc mới cho #7b (2026-07-24)

| Việc | File | Trạng thái |
|---|---|---|
| Bộ sự cố có nhãn commit trong repo (thay `evaluate_detector.py` — tự khai không dùng được làm KPI hệ thống) | `aiops/incident_scenarios/case_real_incident.json` | ✅ |
| Harness inject + tính precision/recall/lead-time đúng công thức mandate | `aiops/incident_replay.py` | ✅ (unit test 13/13 pass, `aiops/test_incident_replay.py`) |
| `repro` bắt buộc phải nộp | `aiops/incident_scenarios/README.md` | ✅ |
| Fix hạ tầng chặn ghi bằng chứng thật trên EKS (`readOnlyRootFilesystem` không có volume ghi được) | `aiops/detector/deploy/deployment.yaml` | ✅ code, chờ ArgoCD sync |

## 4. Bằng chứng chạy thật — **PENDING**

Chờ PR merge vào `develop` + ArgoCD sync xong (fix ở mục 3), rồi chạy:

```bash
python aiops/incident_replay.py run aiops/incident_scenarios/case_real_incident.json
```

Sau khi chạy: dán ảnh terminal (report có precision/recall/lead-time) + nội dung
`case_real_incident.result.json` vào đây, kèm ảnh alert Discord nếu có.

`[PENDING: ảnh/log chạy thật — image/case-real-incident-run.png]`

## 5. Link ADR

`docs/ai/05_adrs.md` — ADR-012 (phương pháp gốc #7a) + addendum "2026-07-24 — MANDATE-07 #7b" (harness, định nghĩa trunk=develop, trạng thái bằng chứng).

## 6. Nội dung dán vào Jira ticket `AI MANDATE #7b`

```
1. PR/commit: <điền URL PR sau khi tạo> (nhánh feat/mandate07b-incident-replay-harness, merge vào develop)

2. Repro:
   python aiops/incident_replay.py run aiops/incident_scenarios/case_real_incident.json
   (bơm paymentFailure=100% qua flagd trên checkout, tự tính precision/recall/lead-time)

3. Bằng chứng chạy thật: <điền sau khi chạy — xem mục 4 report.md>

4. ADR: docs/ai/05_adrs.md#adr-012 (+ addendum 2026-07-24)
```
