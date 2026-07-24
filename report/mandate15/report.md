# Báo cáo — AI MANDATE #15 (Detection đáng tin: bận vs hỏng)

**Hạn:** thứ Bảy 25/07/2026 · **Trạng thái tại 2026-07-24:** code + harness + ADR xong, chạy sống PENDING (xem mục 4).

## 1. Yêu cầu mandate (tóm tắt từ `mandates/MANDATE-15-aiops-detection-standard.md`)

1. Bắt đúng — precision/recall/lead-time trên bộ có nhãn.
2. Không bị che (masking) — spike/nhiễu đơn không làm bỏ sót sự cố thật khác.
3. Không kêu oan khi bận — dựa trên độ lệch khỏi mức bình thường CỦA CHÍNH service.
4. Chạy liên tục + trên trunk.
5. Tự sinh incident summary, đẩy ra kênh thật.
6. MTTD before/after.
7. Chịu được bộ kịch bản ẩn BTC bơm lúc chấm (1 sự cố thật, 1 ca masking, 1 cửa sổ tải-cao-nhưng-khoẻ).

## 2. Đối chiếu từng điểm

| # | Yêu cầu | Đáp ứng bằng | Trạng thái |
|---|---|---|---|
| 1 | precision/recall/lead-time | `aiops/incident_replay.py` (dùng chung #7b) | Code ✅ / chạy sống PENDING |
| 2 | Masking-resistance | Fix winsorize `detector.py` (commit `4f48465`) + test `test_dynamic_detection_not_masked_by_prior_spike` | ✅ đã fix + unit test pass |
| 3 | Độ lệch theo chính service | Đã có sẵn từ #7a (`metric_history` khoá `rule_id:service`, ADR-012) | ✅ không cần đổi |
| 4 | Chạy liên tục + trunk | `Deployment` ArgoCD-managed, đã merge. Trunk = `develop` (định nghĩa ở ADR-012 addendum) | ✅ |
| 5 | Incident summary | Grouped alert (K3) của `alerter.py` — mức MVP, không phải tường thuật root-cause (ghi rõ ở ADR-015, không overclaim) | ✅ mức MVP |
| 6 | MTTD before/after | Before: `report/flagd1/postmortem-INC-01.md` (~2 phút, thủ công, EKS thật 14/07). After: `docs/ai/evals/measure_detection_pipeline.py` (mean 19.6s/max 35.4s, compose). Caveat khác môi trường ghi rõ ADR-015 | ✅ có số, có caveat |
| 7 | Bộ kịch bản ẩn | `aiops/incident_scenarios/case_masking.json` + `case_healthy_load.json` tự dựng để self-validate trước ngày chấm | Code ✅ / chạy sống PENDING |

## 3. Fix quan trọng nhất: bug masking thật

`detector.py:99-102` (trước fix) nạp thẳng giá trị outlier vừa gây alert vào
`metric_history` — spike kéo méo mean/std ~30 chu kỳ sau (~15 phút @ poll 30s), đúng cơ
chế "bị che" mandate mô tả. Đã sửa: winsorize giá trị trước khi nạp (giới hạn trong
`dynamic_threshold` một khi đã có baseline). Commit `4f48465`. Regression test khoá lại
hành vi: `aiops/detector/test_detector.py::test_dynamic_detection_not_masked_by_prior_spike`.

## 4. Bằng chứng chạy thật — **PENDING**

Fix ghi file EKS (`emptyDir`, xem addendum ADR-012) đã merge + sync xong ở PR MANDATE-07
`#7b` (xác nhận qua `kubectl logs` — hết lỗi "Read-only file system", pod ghi được
`/data/`). Chạy cả 3 kịch bản:

```bash
python aiops/incident_replay.py run aiops/incident_scenarios/case_real_incident.json
python aiops/incident_replay.py run aiops/incident_scenarios/case_masking.json
LOCUST_HOST=http://<frontend-host>:8080 \
  python aiops/incident_replay.py run aiops/incident_scenarios/case_healthy_load.json
```

`[PENDING: 3 ảnh/log + verdict PASS/FAIL từng case — image/case-real.png, image/case-masking.png, image/case-healthy-load.png]`

**Ngày chấm (BTC bơm kịch bản ẩn):** chạy `incident_replay.py score` với `--start/--end`
quan sát được thay vì tự inject — xem `aiops/incident_scenarios/README.md`.

## 5. Link ADR

`docs/ai/05_adrs.md` — **ADR-015** (đầy đủ 6 quyết định + alternatives + consequences cho mandate này).

## 6. Nội dung dán vào Jira ticket `AI MANDATE #15`

```
1. PR/commit: <điền URL PR sau khi tạo> (nhánh feat/mandate15-masking-resistance, merge vào develop)
   Harness dùng chung đã merge trước ở PR MANDATE-07 #7b (#342).

2. Repro:
   python aiops/incident_replay.py run aiops/incident_scenarios/case_masking.json
   python aiops/incident_replay.py run aiops/incident_scenarios/case_healthy_load.json
   (cửa replay nhận kịch bản ngoài: `incident_replay.py score <file> --start --end`
   cho ngày BTC tự bơm)

3. Bằng chứng chạy thật: <điền sau khi chạy — xem mục 4 report.md>
   MTTD before/after: ~2 phút (thủ công, INC-01) -> mean 19.6s (tự động) — xem ADR-015 mục 5.

4. ADR: docs/ai/05_adrs.md#adr-015
```
