# MANDATE-22: Closed-loop Auto-mitigate — Evidence

**Người chịu trách nhiệm:** Thanh Pham Huu Tien (`phamthanh.forwork@gmail.com`)
**Ngày cập nhật:** 2026-07-28 · **Ticket:** TF1-108 (doc + ADR ký cá nhân)
**Cụm đo:** `ecommerce-dev-eks` (us-east-1), namespace `techx-tf1` — **EKS thật, không phải docker-compose**

> **Lưu ý về đánh số:** MANDATE-22 không nằm trong `mandates/` (danh sách chính thức chỉ tới
> #21). Đây là directive #22 nhóm nhận thêm. Doc này gom toàn bộ bằng chứng cho nó.

---

## 1. Vòng khép kín — component và code

| Thành phần | Đường dẫn | Vai trò |
|---|---|---|
| Detector | `aiops/detector/` | phát hiện, sinh alert `oom-detected` |
| Remediation | `aiops/remediation/` | dry-run → error budget → blast radius → hành động → verify → circuit breaker |
| Policy | `aiops/remediation/remediation_policy.yaml` | config-driven, đổi số **không cần sửa code** |
| Harness chấm điểm | `aiops/incident_replay.py` | bộ kịch bản có nhãn, logic chấm là Python thuần đọc được |

**Thứ tự các cổng** trong `process_oom_policy()` — quan trọng để đọc mọi số dưới đây:

> circuit breaker → error budget → **blast radius** → dry-run → hành động → verify

## 2. PR đã giao

| PR | Nội dung | Trạng thái |
|---|---|---|
| #459 | tạm tắt dry-run để đo MTTR (TF1-106) | Merged |
| #460 | **trả** dry-run về `true` sau khi đo xong (TF1-106) | Merged |
| #473 | TF1-107 — validate ngưỡng bằng chaos OOM thật | Merged |
| #475 | TF1-106 — MTTR before/after | Open |

## 3. Số đo — tất cả trên EKS thật

### 3.1 MTTR before/after (TF1-106)

| | MTTR | Đường phục hồi |
|---|---|---|
| **Before** | **310.3s** | kubelet tự restart, CrashLoopBackOff |
| **After** | **67.2s** | remediation xoá pod, backoff reset |

`61.0s` trong đó khớp đúng hai chu kỳ poll nối tiếp: detector 30s + remediation ~31s.

> ⚠️ **Không được trích "4.6×" trần trụi.** Với `blast_radius 1 action/3600s` và pod OOM mỗi
> ~2 phút, vòng tự dập cứu được **1 trong ~30 lần** → MTTR trung bình thực tế ≈ **302s**, tức
> cải thiện **2.7%**. Và với **một OOM đơn lẻ** thì kubelet (~10s) **nhanh hơn 6.7 lần** vòng
> tự dập (67.2s).
>
> **Điều vòng tự dập thật sự làm được:** phá `CrashLoopBackOff` — thứ kubelet không tự thoát ra.

Chi tiết: `report/mandate22-mttr/report.md`

### 3.2 Ba ngưỡng an toàn (TF1-107)

| Ngưỡng | Giá trị ship | Đo được | Kết luận |
|---|---|---|---|
| `verify.duration_seconds` | 120s, poll 20s | thoát nhánh "OOM mới" ở **43.0s** (3/3 lần); nhánh "hết giờ" ở **124.2s** | Giữ. Nhưng **không phải tham số chi phối** |
| `circuit_breaker` | 3 fail / 86400s | mở **đúng** sau 3 fail liên tiếp, rồi từ chối + escalate | Logic đúng, **không với tới được** |
| `blast_radius` | 1 / 3600s / namespace | chặn đúng thiết kế | **Cần đổi** |

Chi tiết: `report/mandate22-thresholds/report.md`

### 3.3 Lỗ hổng phát hiện trong lúc đo (TF1-102 / TF1-106 / TF1-107)

| # | Lỗ hổng | Nguồn | Ticket |
|---|---|---|---|
| 1 | `is_service_ready()` tra pod bằng `label_selector=opentelemetry.io/name=unknown` → luôn `False` → verify luôn FAIL trên **16/57 pod (28%)** | TF1-107 | **TF1-116** |
| 2 | `BlastRadiusGuard._history` **không sống qua restart** pod | TF1-106 | *chưa có ticket* |
| 3 | `check_error_budget_ok()` **thất bại mở** (fail-open) | TF1-106 | *chưa có ticket* |
| 4 | `verify_oom_recovery()` quét OOM **toàn namespace** → pod khác OOM làm verify của service đang xét FAIL oan | TF1-107 | *chưa có ticket* |
| 5 | `kafka-consumer-lag-high` query `kafka_consumer_group_lag` — **tên metric không tồn tại** | TF1-102 | *chưa có ticket* |

## 4. Bằng chứng an toàn — điều mandate đòi và điều đo được

Mandate đòi *"kiểm tra an toàn: dry-run / blast-radius"*. Đo thật thì **hai trong ba cổng
không làm đúng việc**:

| Cổng | Trạng thái |
|---|---|
| `dry_run` | ✅ hoạt động đúng — mặc định `true`, phải set `REMEDIATION_DRY_RUN=false` **rõ ràng** mới hành động thật |
| `blast_radius` | ⚠️ chặn đúng, nhưng state trong RAM nên **không sống qua restart** (lỗ hổng #2) |
| `error_budget_check` | ❌ **thất bại mở** — Prometheus lỗi thì nó cho đi tiếp thay vì chặn (lỗ hổng #3) |

**Mọi lần bật dry-run đều đi qua PR và đều được trả lại:** #459 bật → #460 trả. Thí nghiệm
TF1-107 **không** bật dry-run của bản production mà chạy Deployment riêng, để không hạ tư
thế an toàn của cả namespace.

## 5. ADR

| ADR | Nội dung | Chữ ký |
|---|---|---|
| **ADR-013** | Closed-loop auto-remediation: dry-run → blast-radius → verify → rollback → CB | **ký cá nhân** (TF1-108, 28/07) |
| ADR-012 | Baseline & anomaly detection cho detector | ký cá nhân (TF1-102, 27/07) |
| ADR-017 | Detection đáng tin — masking-resistance, MTTD trên EKS | ký cá nhân (TF1-108, 28/07) |

Chữ ký cá nhân không phải hình thức: một vòng tự động **xoá pod trên cụm thật** phải quy
được về một người. "Soạn thảo" chỉ ghi ai gõ chữ, không ghi ai chịu trách nhiệm.

## 6. Tái tạo

```bash
# MTTR before/after
python3 report/mandate22-mttr/measure_mttr.py
python3 report/mandate22-mttr/measure_after.py

# Validate ngưỡng bằng chaos OOM thật (nhớ dọn sau khi chạy — xem mục 8 của report)
kubectl apply -f report/mandate22-thresholds/canary-oom.yaml
kubectl create configmap tf1107-policy -n techx-tf1 \
  --from-file=policy.yaml=report/mandate22-thresholds/policy-test.yaml
kubectl apply -f report/mandate22-thresholds/runner.yaml
kubectl logs -n techx-tf1 -l app=tf1107-runner -f

# Backtest phát hiện hụt
python3 report/mandate22-detection-gaps/backtest_collapse.py
```

| Báo cáo | Đường dẫn |
|---|---|
| MTTR before/after | `report/mandate22-mttr/report.md` |
| Validate ngưỡng | `report/mandate22-thresholds/report.md` |
| Phát hiện hụt | `report/mandate22-detection-gaps/verify.md` |

## 7. Điều chưa làm được, nói rõ

- **Chưa sửa `blast_radius`** dù hai nguồn bằng chứng độc lập (TF1-106 và TF1-107) cùng chỉ
  vào nó. Sửa tham số an toàn nên đi PR riêng có backtest, không lẫn vào PR bằng chứng.
- **Ca verify PASS chưa đo được** — bị chặn bởi chính lỗ hổng #1.
- **Ba trong năm lỗ hổng chưa có ticket** (#2, #3, #4, #5 ở mục 3.3).
- **Phần lớn phép đo dùng pod mồi**, không phải service production. Chúng chứng minh được
  **cơ chế**, không chứng minh được hành vi của một service đang phục vụ khách.
- **`action` duy nhất là `k8s_restart_pod`.** Vòng khép kín chưa có hành động nào khác
  (scale, rollback helm, failover) — đây là phạm vi MVP đã chốt ở ADR-013, không phải thiếu sót
  mới.
