# MANDATE-18 evidence pack

Evidence pack cho [MANDATE-18: Hoá đơn ẩn - cắt tiền ngoài node compute](../../../mandates/MANDATE-18-cost-beyond-compute.md).

## Phạm vi đã xác minh

- AWS profile: `phase3-cdo` (SSO assumed role; không lưu account ID vào repository).
- Region: `us-east-1`.
- EKS cluster: `ecommerce-dev-eks`.
- Cluster tag environment: `dev`.
- Application/observability namespace: `techx-tf1`.

> The baseline above is historical data collected from sandbox. Per leader
> review on 2026-07-23, the Mandate 18 deployment target is now Terraform and
> GitOps `develop` (`ecommerce-develop-dev-eks`, `techx-develop`). Do not use
> the sandbox baseline as develop after evidence.
- Git baseline: `develop` tại `2376042`.

## Trạng thái mentor-facing hiện tại

- Evidence pack: **AUDITED, NOT SUBMISSION-READY**.
- Directive compliance nghiêm ngặt: `0/5` requirement đạt PASS hoàn toàn.
- Weighted directive completion (`PARTIAL=0.5`): `1.5/5 = 30%`.
- Screenshot thật: `0`; toàn bộ tên ảnh trong pack hiện là capture checklist.
- Terraform full plan: `BLOCKED` do SSO role không đọc được remote state object
  (`S3 HeadObject 403`); không thể khẳng định zero destroy/replace.
- Runtime change/after evidence: chưa có apply/Argo rollout cho S3 endpoint và
  telemetry controls.
- SLO final verification: success SLI đạt, nhưng storefront p95 `15s` FAIL.

## Cấu trúc

- `EVIDENCE-INDEX.md`: ánh xạ acceptance criterion tới evidence thật.
- `RUN-RESULTS.md`: kết quả runtime gần nhất và các blocker.
- `mandate-18.md`: báo cáo mentor-facing.
- `mandate-18/`: plan, ADR, runbook và kịch bản demo.
- `logs/`: raw CLI/API output đã redact.
- `screenshots/`: ảnh AWS Console/Grafana do operator chụp.

## Entry points cho mentor

1. [`mandate-18.md`](mandate-18.md): kết luận và before/after delta.
2. [`EVIDENCE-INDEX.md`](EVIDENCE-INDEX.md): requirement → raw log → screenshot.
3. [`RUN-RESULTS.md`](RUN-RESULTS.md): kết quả từng prompt và cách tính tỷ lệ.
4. [`mandate-18/implementation-plan.md`](mandate-18/implementation-plan.md):
   kế hoạch đóng gap trước PR.
5. [`screenshots/README.md`](screenshots/README.md): tên ảnh, caption, số cần đọc,
   timestamp/window và trạng thái capture.
6. [`logs/14-pr-readiness-audit.txt`](logs/14-pr-readiness-audit.txt): plan,
   redaction, screenshot và PR readiness audit gần nhất.

## Quy tắc evidence

1. Không ghi `PASS` chỉ vì control tồn tại trong code.
2. Raw evidence phải là output thật; không tạo sample output trong `logs/`.
3. Before/after phải dùng cùng region, filter, đơn vị, cửa sổ và workload.
4. Không cộng các đơn vị khác loại như NAT-hours, GB transfer và GB-month.
5. Redact account ID/ARN/email nhưng giữ resource name, timestamp, query và kết quả.
6. Không xóa resource nếu chưa xác minh owner, dependency và rollback.

## Quy ước trạng thái

- `PASS`: raw runtime evidence chứng minh đúng acceptance.
- `PARTIAL`: có bằng chứng hợp lệ cho một phần nhưng còn runtime/delta/gate.
- `BLOCKED`: thiếu quyền, owner confirmation hoặc dữ liệu bắt buộc.
- `PENDING`: bước chưa chạy nhưng không có blocker kỹ thuật được xác minh.

Đường dẫn evidence dự kiến không đồng nghĩa file/ảnh đã tồn tại. Cột
`Capture status` trong index và screenshot guide là nguồn sự thật.
