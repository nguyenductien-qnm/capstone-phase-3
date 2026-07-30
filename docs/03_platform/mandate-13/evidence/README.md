# Mandate 13 — Cost Efficiency, Elastic Compute — EVIDENCE PACK

> **TF:** CDO-09 · **Directive:** [`mandates/MANDATE-13-cost-efficiency-elastic.md`](../../../mandates/MANDATE-13-cost-efficiency-elastic.md)
> **Evidence pack này = cluster sandbox** (account `804372444787`, cluster `ecommerce-dev-eks`, namespace `techx-tf1`) — nơi duy nhất hiện có bằng chứng thật (2026-07-28). Track `develop` (account `458580846647`, cluster `ecommerce-develop-dev-eks` — target chính thức ban đầu của directive #13) có code đầy đủ nhưng **chưa apply/chưa có evidence thật**; chi tiết quyết định mở rộng sang sandbox nằm ở ADR §"Mở rộng sang sandbox — Phương án B" (27-07-2026).
> **ADR (quyết định + lý do, cả develop lẫn sandbox):** [`ADR-mandate13-cost-efficiency-elastic.md`](ADR-mandate13-cost-efficiency-elastic.md)
> **Evidence Index (bảng map bằng chứng → file, toàn bộ là sandbox):** [`EVIDENCE.md`](EVIDENCE.md)

---

## 0. Tóm tắt cho mentor

**Bằng chứng dưới đây đo trên cluster sandbox, KHÔNG phải cluster develop mà directive #13 nhắm tới ban đầu** — track develop có code đầy đủ nhưng chưa `terraform apply`/ArgoCD sync nên chưa đo được gì thật. Số liệu sandbox (2026-07-28) dùng để minh hoạ mô hình hoạt động đúng như thiết kế trong ADR; xem `EVIDENCE.md` cho chi tiết + raw log.

| Yêu cầu | Trạng thái (đo trên sandbox) | Bằng chứng | Evidence |
|---|---|---|---|
| **#1** Chạy trên capacity rẻ (spot > 50%) | ✅ **63.9%** trên compute Karpenter-managed (2300m/3600m CPU requests) | NodePool `spot` opt-in 10 service (accounting, ad, cart-consumer-worker, email, fraud-detection, image-provider, llm, ml-guard, product-reviews, recommendation) | `EVIDENCE.md` #1 |
| **#2** Trả tiền theo demand (co xuống thật) | 🟡 **Pod scale thật (HPA) ✅, node scale ❌** — `frontend` đã đạt tuyệt đối trần `maxReplicas` (20/20, 700 user, 30-07) nhưng pool `default` giữ nguyên 2 node suốt bài test. Pool `spot` có 1 chu kỳ launch→consolidate thật (~6 phút) | Load test thật (28-07 & 30-07) + giám sát `kubectl`/Karpenter events | `EVIDENCE.md` §2 |
| **#3** Sống sót spot interruption | ✅ Live spot-kill: node mới trong ~34s, pod Running trong ~118s, 0 pod Error/CrashLoop | `aws ec2 terminate-instances` + theo dõi pod | `EVIDENCE.md` #5, #6 |
| **#4** Đủ tín hiệu cho scheduler | ✅ Đã đạt từ Mandate-19 | Right-sizing (`docs/mandate-19/loadtest/README.md`) — không đổi ở Mandate-13 | — |
| **#5** node-hours ↓≥30%, spot≥50%, **Graviton**, co xuống thật, SLO giữ | ❌ **KHÔNG đạt node-hours** (0% chênh lệch trên pool `default`) — spot ratio 63.9% ✅ đạt, Graviton ❌ chưa bật (CI đã hỗ trợ multi-arch từ 28-07, blocker còn lại là NodePool config + runtime verify) | `EVIDENCE.md` §6 | `EVIDENCE.md` #3 |

**Kết luận node-hours:** Node-hours trên pool `default` (money-path) **không thay đổi (0%)** qua 2 lần load test thật — 28-07 (đỉnh 450 user) và 30-07 (đỉnh 700 user, sau khi nới `maxReplicas` cho 8 service qua PR #508). Ở lần test 30-07, `frontend` đạt tuyệt đối trần mới (20/20 replica, vẫn 74%/70% over-target) nhưng tổng CPU request pool `default` vẫn dưới capacity 2-node vì `checkout/payment/quote/shipping/currency/product-catalog` — trọng số task thấp trong locustfile — chưa vượt 70% utilization để tự sinh thêm replica; ước tính cần ~2500+ user đồng thời mới đủ. Pool `spot` có 1 chu kỳ launch→consolidate thật (Karpenter `Underutilized`, ~6 phút) nhưng quá ngắn để đại diện cho node-hours. Nguyên nhân là giới hạn kiến trúc thật (CPU-request sizing so với capacity node + task-weight distribution), không phải lỗi đo. Chi tiết đầy đủ: ADR §"Đo lường thực tế (30-07-2026)".

**Còn thiếu để evidence pack "đầy đủ":** PDB status output riêng, screenshot Grafana Node Count + SLO dashboard, screenshot EC2 Console.

## 1. Những gì đã thay đổi trong code — track develop (target chính thức của directive)

> Bảng này mô tả code nhắm vào `develop` — **khác với evidence sandbox ở §0** (sandbox có bộ thay đổi riêng, xem ADR §"Mở rộng sang sandbox — Phương án B"). Track develop chưa apply nên các thay đổi dưới đây chưa được đo trên cluster thật. Chi tiết đầy đủ + lý do cho từng quyết định nằm ở ADR. Bảng dưới đây chỉ tóm tắt.

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

## 3. Việc còn lại

**Ưu tiên ngay — lấp nốt evidence sandbox:** PDB status output riêng (`kubectl get pdb`), screenshot Grafana Node Count + SLO dashboard trong lúc load test, screenshot EC2 Console (Lifecycle/Instance type). `EVIDENCE.md` chỉ liệt kê evidence đã có — mục còn thiếu theo dõi ở đây.

**Việc riêng, chưa bắt buộc ngay — rollout track develop** (mục tiêu chính thức của directive, nhưng chưa có timeline): `terraform plan`/`apply` cho `karpenter.tf`+`variables.tf`, review ArgoCD thủ công cho 3 Application `develop-karpenter*`, và demo live spot-kill trên cluster develop thật — xem ADR §Approval gates (Develop). Nếu track develop được apply thật sau này, evidence của nó nên lưu vào `logs/`/`screenshots/` cùng cấp và thêm dòng riêng vào `EVIDENCE.md`, ghi rõ account/cluster để không lẫn với số liệu sandbox hiện có.
