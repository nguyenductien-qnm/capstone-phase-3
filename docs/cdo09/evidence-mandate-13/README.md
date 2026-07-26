# Mandate 13 — Cost Efficiency, Elastic Compute — EVIDENCE PACK

> **TF:** CDO-09 · **Directive:** [`mandates/MANDATE-13-cost-efficiency-elastic.md`](../../../mandates/MANDATE-13-cost-efficiency-elastic.md)
> **Cluster test:** `ecommerce-develop-dev-eks` (account 458580846647) · namespace `techx-develop`
> **Branch:** `feat/mandate-13-cost-efficiency-elastic` — code đã viết xong, **chưa chạy `terraform apply` / ArgoCD sync** (xem `mandate-13/ADR-mandate13-cost-efficiency-elastic.md` §Approval gates).
> **ADR (quyết định + lý do):** [`mandate-13/ADR-mandate13-cost-efficiency-elastic.md`](mandate-13/ADR-mandate13-cost-efficiency-elastic.md)
> **Execution guide (thao tác apply + test thật trên multi-account):** [`mandate-13/EXECUTION-GUIDE.md`](mandate-13/EXECUTION-GUIDE.md)
> **Submission guide (hướng dẫn chi tiết nộp bài cho mentor):** [`mandate-13/SUBMISSION-GUIDE.md`](mandate-13/SUBMISSION-GUIDE.md)

---

## 0. Tóm tắt cho mentor

**Trạng thái hiện tại: code đã viết đầy đủ trên branch, CHƯA chạy trên cluster thật.**
Không có lệnh `terraform plan`/`apply` hay ArgoCD sync nào được thực hiện — bảng dưới đây phản ánh đúng thực tế đó, không tô hồng thành "Pass" khi chưa có bằng chứng thật từ console/Grafana.

| Yêu cầu | Trạng thái | Bằng chứng cần | Code Review |
|---|---|---|---|
| **#1** Chạy trên capacity rẻ (spot > 50%) | 🟡 **Code sẵn sàng, chưa đo được** | NodePool `capacity-type: ["spot","on-demand"]` — [`nodepool-default.yaml`](../../../platform/gitops/environments/develop/karpenter/nodepool-default.yaml). Root app đã bỏ exclude Karpenter — [`root-app.yaml`](../../../platform/gitops/environments/develop/bootstrap/root-app.yaml). Cần EC2 console + Cost Explorer sau khi apply. | ✅ Code đầy đủ |
| **#2** Trả tiền theo demand (co xuống thật) | 🟡 **Code sẵn sàng, chưa đo được** | `consolidationPolicy: WhenEmptyOrUnderutilized` + `consolidateAfter: 5m` + `disruption.budgets: nodes=1` trên NodePool. MNG `primary` giữ `min=2,max=3,desired=2` on-demand làm sàn HA, phần co-giãn thật đến từ node do Karpenter tạo. [`develop-capacity.tfvars`](../../../terraform/environments/develop/develop-capacity.tfvars) đã gỡ override cũ. Cần Grafana panel "Node Count and Scaling" quay live. | ✅ Code đầy đủ |
| **#3** Sống sót spot interruption (phần nặng nhất) | 🟡 **Code sẵn sàng, chưa test live-kill** | SQS interruption queue + 1 EventBridge rule (gộp 3 loại event) gated bởi `enable_karpenter_interruption_queue` trong [`karpenter.tf`](../../../terraform/modules/eks/karpenter.tf) + chỉ bật `true` ở [`main.tf develop`](../../../terraform/environments/develop/main.tf). Graceful-drain (`terminationGracePeriodSeconds: 30` + `preStop: sleep 5`) được thêm cho `payment` trong [`values.yaml`](../../../platform/charts/application/values.yaml). Karpenter Helm đã nối `interruptionQueue` trong [`karpenter.yaml`](../../../platform/gitops/environments/develop/applications/karpenter.yaml). Cần live `aws ec2 terminate-instances` trên 1 spot node. | ✅ Code đầy đủ |
| **#4** Đủ tín hiệu cho scheduler (request vừa đủ) | ✅ **Đã đạt từ trước** | Right-sizing đã làm ở Mandate-19 (`docs/mandate-19/loadtest/README.md` §"Sizing SAU-SHED") — không có thay đổi mới trong Mandate-13. | ✅ Không cần thay đổi |
| **#5** Đo được: node-hours ↓≥30%, spot≥50%, **Graviton**, co xuống thật, SLO giữ | ❌ **Graviton bị hoãn (deferred) có chủ ý** | Xem ADR Decision 4: CI hiện chỉ build `linux/amd64`, thêm multi-arch là scope quá lớn. Phần còn lại (node-hours, spot%, co xuống, SLO) cần đo sau apply. Load curve [`locust-loadcurve-mandate13-job.yaml`](../../../docs/mandate-19/loadtest/locust-loadcurve-mandate13-job.yaml) đã sẵn sàng. | ⚠️ Graviton N/A, phần khác OK |

**Nguyên tắc:** Không có dòng nào trong bảng trên được đánh "✅ Pass" chỉ vì code đã viết xong — "Pass" chỉ được gắn sau khi có log/screenshot thật lưu trong thư mục `logs/` và `screenshots/` (hiện đang trống, xem `EVIDENCE-INDEX.md`).

## 1. Những gì đã thay đổi trong code (branch này)

Chi tiết đầy đủ + lý do cho từng quyết định nằm ở ADR. Bảng dưới đây chỉ tóm tắt.

| File | Thay đổi |
|---|---|
| `platform/gitops/environments/develop/bootstrap/root-app.yaml` | Bỏ exclude 3 file Karpenter — kích hoạt Karpenter làm autoscaler chính trên develop (trước đó bị khóa từ 2026-07-19). |
| `terraform/modules/eks/karpenter.tf` + `outputs.tf` + `variables.tf` | Thêm SQS interruption queue + 1 EventBridge rule (gộp cả 3 loại event bằng list `detail-type`) + IAM statement cho controller đọc queue. **Được rào lại (gate) bởi biến mới `enable_karpenter_interruption_queue` (mặc định `false`)**, vì đây là shared module dùng chung bởi cả develop lẫn sandbox (xem §2 dưới). |
| `terraform/environments/develop/main.tf` | Bật `enable_karpenter_interruption_queue = true` — chỉ định riêng cho develop. |
| `terraform/environments/develop/develop-capacity.tfvars` | Bỏ override `eks_node_scaling` tồn đọng từ Mandate-19 Phase 2-3 (`desired_size=3`) — override này trước đây đã đè lên giá trị mặc định trong `variables.tf` khi apply (xem §3). |
| `platform/gitops/environments/develop/applications/karpenter.yaml` | Nối `settings.interruptionQueue`. |
| `platform/gitops/environments/develop/karpenter/nodepool-default.yaml` | `capacity-type: [spot, on-demand]`, `consolidationPolicy: WhenEmptyOrUnderutilized`, `consolidateAfter: 5m`, `disruption.budgets: nodes=1`, nâng `limits.cpu` lên `32` (theo công thức capacity planning, xem ADR Decision 3). |
| `platform/charts/application/values.yaml` | Thêm `terminationGracePeriodSeconds: 30` + `preStop: sleep 5` cho `payment` (service duy nhất trên luồng browse→cart→checkout còn thiếu — `ad`/`currency`/`ml-guard`/`recommendation` có cùng thiếu sót nhưng cố ý để ngoài phạm vi vì không nằm trên luồng này, xem ADR). Đây là shared chart, xem §2. |
| `docs/mandate-19/loadtest/locust-loadcurve-mandate13-job.yaml` | Đường cong tải mới thấp→cao→thấp (10u→40u→80u→40u→10u), luồng mixed browse+cart+checkout. Pha cuối kéo dài 10 phút (thay vì 5) để đủ thời gian cho Karpenter chạy consolidate (gom node). |

**Không đụng đến** (đã cân nhắc rồi loại bỏ để giữ quy tắc thay đổi tối thiểu — xem ADR §Rejected options): `terraform/environments/sandbox/primary-schedule.tf` (chỉ ảnh hưởng sandbox, không phải cluster mà mandate này nhắm tới), và panel Grafana Spot-vs-On-Demand mới (yêu cầu panel ③ của directive đã được thỏa mãn bởi panel "Node Count and Scaling" + SLO dashboard có sẵn).

## 2. Cô lập môi trường (Environment isolation) — tuân thủ `environment-isolation-execution-guide`

`terraform/modules/eks/` và `platform/charts/application/values.yaml` đều là các thành phần **dùng chung (shared)** (sử dụng bởi cả `develop` và `sandbox`). Có 2 điểm cần xử lý cẩn thận:

- **`terraform/modules/eks/karpenter.tf` (shared module) — tuân thủ Case T3.** Thêm SQS queue + EventBridge rule không điều kiện sẽ khiến lệnh `terraform plan`/`apply` tiếp theo của account **sandbox** (`804372444787`) tự động tạo các resource này dù mandate không nhắm tới sandbox — đúng anti-pattern mà guide mô tả. Đã sửa: biến `enable_karpenter_interruption_queue` (mặc định `false`) rào toàn bộ resource bằng `count`, chỉ bật `true` ở `terraform/environments/develop/main.tf` — theo đúng pattern có sẵn trong repo (`enable_network_policy`, CDO-219/Mandate-17-R3). Kết quả: sandbox plan sẽ không có bất kỳ diff nào từ các file mà Mandate-13 chạm vào.
- **`platform/charts/application/values.yaml` (shared chart) — Case G2.** Cấu hình graceful-drain cho `payment` an toàn ở cả 2 môi trường nên không cần feature flag, nhưng vẫn cần bằng chứng theo guide: render effective values cho cả develop và sandbox để xác nhận không có resource nào ở sandbox bị xóa/đổi tên ngoài dự kiến, và phải deploy develop trước (§3, chưa làm).

## 3. Việc còn lại trước khi có thể đánh dấu 'Pass'

**Thao tác chi tiết từng bước (pre-flight → PR → apply → ArgoCD sync → load test → live-kill → evidence) nằm ở [`mandate-13/EXECUTION-GUIDE.md`](mandate-13/EXECUTION-GUIDE.md)** — guide đó cũng chỉ rõ phần nào đã làm cục bộ (tfvars fix, `terraform fmt`/`validate`) và phần nào bị chặn vì phiên làm việc hiện tại không có AWS credentials cho account develop/sandbox lẫn CLI `gh`/`argocd`.

**Hướng dẫn nộp bài chi tiết cho mentor (deliverables, thứ tự, mẹo quay video, Q&A) nằm ở [`mandate-13/SUBMISSION-GUIDE.md`](mandate-13/SUBMISSION-GUIDE.md).**

1. Chạy `terraform plan` thật (qua `gh workflow run infra-develop.yaml`) cho cả develop và sandbox — xác nhận sandbox plan không đổi (bằng chứng Case T3 ở §2), sau đó `plan`/`apply` develop.
2. Review thủ công và chạy ArgoCD sync cho 3 Application `develop-karpenter*` lần đầu (ghi chú trong `karpenter-nodepool.yaml`: "Manual sync only. Review the EC2NodeClass role and discovery tags first").
3. Render effective Helm values cho cả develop và sandbox (Case G2).
4. Lấy baseline evidence (①②③ trước khi đổi) rồi chạy `locust-loadcurve-mandate13-job.yaml`, quay video Grafana live.
5. Thực hiện live-kill trên 1 spot node đang chịu tải — bằng chứng nặng đô nhất của yêu cầu #3.
6. Đo Cost Explorer Usage Quantity (trễ ~24h) cho bằng chứng về trend/node-hours.
7. Đổ dữ liệu vào `logs/` + `screenshots/` và cập nhật bảng ở §0 bên trên thành Pass/Fail thật sự.

Xem `EVIDENCE-INDEX.md` để biết cách map cụ thể file log/screenshot sau khi các bước trên hoàn tất.
