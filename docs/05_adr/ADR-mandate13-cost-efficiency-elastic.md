# ADR — Mandate 13 cost efficiency, elastic compute

- **Status:** Proposed. Code xong trên `feat/mandate-13-spot-opt-in-async-consumers` (kế thừa `feat/mandate-13-cost-efficiency-elastic`). Track `develop`: chưa `terraform apply`/ArgoCD sync. Track `sandbox` (mở rộng tự nguyện): code xong + **evidence thật đã có** (28-07-2026, xem `EVIDENCE.md`).
- **Ngày:** 25-07-2026 (gốc) · 27-07-2026 (mở rộng sandbox) · 28-07-2026 (đo lường thực tế).
- **Owner:** CDO-09 (cost + reliability).
- **Rollout target:** Terraform/GitOps `develop` (cluster `ecommerce-develop-dev-eks`, ns `techx-develop`) — target chính thức của directive #13. Mở rộng tự nguyện (27-07-2026): GitOps `sandbox` (cluster `ecommerce-dev-eks`, ns `techx-tf1`) — ngoài phạm vi chấm điểm gốc.
- **Scope principle:** chỉ đổi tối thiểu để đáp ứng directive #13, không suy đoán làm thêm ngoài lề.

## Bối cảnh

Directive #13 yêu cầu >50% compute trên spot + node-hours giảm ≥30% cho cùng tải, không rớt request trên luồng browse→cart→checkout khi spot node bị thu hồi. Account chạy credit ($≈0) nên đo bằng node-hours + %spot + SLO, không dùng cột $.

Baseline trước khi đổi: MNG `primary` 100% on-demand, kích thước tĩnh. IAM/Pod Identity của Karpenter đã có sẵn nhưng GitOps Application của nó bị exclude khỏi root ArgoCD app (dormant từ 2026-07-19). NodePool cũ chỉ on-demand, `consolidationPolicy: WhenEmpty` (không bao giờ scale-down thật), và không có cơ chế xử lý spot-interruption nào (không SQS, không EventBridge) — PDB workload vô dụng trước một đợt thu hồi spot thật.

## Quyết định (Develop)

1. **Karpenter = autoscaler chính; MNG `primary` co lại thành floor cố định `min=2,max=3,desired=2` on-demand.** Bật lại Application `develop-karpenter*` đang dormant thay vì lật MNG sang spot trực tiếp (MNG/ASG không scale-down theo pod pending — sẽ cần thêm Cluster Autoscaler, một tool thứ 2). Giữ `min=2` (không phải `1`) để HA cho floor: CoreDNS/Karpenter controller cần ≥2 node trải AZ, tránh SPOF khi 1 node gặp sự cố.
2. **Spot interruption: EventBridge → SQS → Karpenter `interruptionQueue`, gate bằng biến mới `enable_karpenter_interruption_queue` (default `false`, chỉ `true` ở `terraform/environments/develop/main.tf`).** `terraform/modules/eks/` là shared module (dùng bởi cả develop và sandbox) — không gate sẽ leak resource sang sandbox plan (Case T3, giống pattern `enable_network_policy` có sẵn trong repo). Rule EventBridge gộp cả 3 loại event (Spot Interruption Warning, Rebalance Recommendation, State-change). Bác bỏ chạy song song AWS Node Termination Handler (double-drain race) và bác bỏ dựa vào NotReady mặc định của kubelet (chậm hơn nhiều so với cảnh báo 2 phút của AWS).
3. **`consolidationPolicy: WhenEmptyOrUnderutilized` + `consolidateAfter: 5m` + `limits.cpu: 32` + `disruption.budgets: nodes=1`** trên NodePool develop. `WhenEmptyOrUnderutilized` (thay `WhenEmpty`) để chứng minh scale-down thật. `5m` là chuẩn production (tránh node churn) — pha "tải thấp" cuối load test được kéo dài lên 10 phút để đủ thời gian demo. `limits.cpu:32` tính theo công thức capacity planning (`maxReplicas × CPU request × 1.15 × 1.3 ≈ 30 vCPU`). `disruption.budgets: nodes=1` chặn evict hàng loạt, bảo vệ SLO khi consolidate/interrupt.
4. **Graviton/arm64 bị loại khỏi phạm vi có chủ ý.** CI hiện chỉ build `linux/amd64`; multi-arch cần build matrix mới + test tương thích arm64 cho service dùng native/JNI (Java OTel agent, C++ OTel SDK) — quá lệch pha so với scope mandate này. Ghi nhận **FAIL/deferred** cho tiêu chí Graviton của yêu cầu #5, không lấp liếm.
5. **Graceful-drain (`terminationGracePeriodSeconds: 30` + `preStop: sleep 5`) chỉ thêm cho `payment`** trong `platform/charts/application/values.yaml` (shared chart, Case G2 — an toàn cho mọi môi trường nên không cần gate, nhưng cần render effective values cả 2 môi trường để xác nhận không lệch). `payment` là lỗ hổng thật duy nhất trên luồng browse→cart→checkout (đã có PDB/topologySpread nhưng thiếu preStop). `ad`/`currency`/`ml-guard`/`recommendation` thiếu tương tự nhưng ngoài luồng này nên không mở rộng.
6. **Load curve mới** (`docs/mandate-19/loadtest/locust-loadcurve-mandate13-job.yaml`) — tái dùng task mix Mandate-19 Phase 4 + `LoadTestShape` mới low→high→low (10u→40u→80u→40u→10u). Bắt buộc vì directive cần đo cả scale-up lẫn scale-down; repo trước đó chỉ có shape step-up.
7. **Không tạo Grafana panel mới** — panel "Node Count and Scaling" + SLO dashboard có sẵn đã đáp ứng đủ yêu cầu panel ③; spot% chứng minh qua EC2 console/Cost Explorer.
8. **Không đụng `terraform/environments/sandbox/primary-schedule.tf`** — chỉ ảnh hưởng sandbox, ngoài phạm vi develop của ADR gốc.

### Rejected options (Develop)

- Lật MNG `primary` sang `SPOT` trực tiếp: MNG/ASG không scale-down theo pod pending.
- Karpenter + Cluster Autoscaler song song: 2 autoscaler tranh quyết định tạo node.
- AWS Node Termination Handler song song Karpenter: double-drain race, thừa thãi.
- Fargate profile cho `techx-develop`: không hỗ trợ DaemonSet, không có khái niệm "node" để demo scale.
- `consolidationPolicy: WhenEmpty` + `consolidateAfter: Never`: không chứng minh được scale-down.
- Graviton/arm64 ngay lần pass này: xem Decision 4.
- Mở rộng graceful-drain cho `ad`/`currency`/`ml-guard`/`recommendation`: ngoài luồng browse→cart→checkout.
- Grafana panel Spot-vs-On-Demand riêng: directive không đòi hỏi, giữ minimum-change.
- Tool load-test mới (k6/Artillery/Gatling): Locust + thêm shape class là đủ.

## Rà soát sau merge `origin/develop` (`c9f8b29`, 25-07-2026)

Merge kéo theo PR #382 (continuous loadgen), #386 (karpenter-phase1-sandbox), #385 (provenance trace), #384/#383 (fix grafana/email). Đã soát toàn bộ file đụng — 2 điểm cần xử lý:

- **`minValues: 2` trên zone requirement (đã fix).** PR #386 fix lỗi này cho NodePool sandbox (khiến Karpenter reject 100% node launch vì mỗi NodeClaim chỉ pin 1 AZ) nhưng bỏ sót NodePool develop. Đã xoá `minValues` khỏi NodePool develop, dựa vào `topologySpreadConstraints` ở pod level để trải AZ.
- **Continuous load-generator (PR #382) bật lại `enabled: true`** trong file values dùng chung — traffic nền có thể khiến node không đạt `Underutilized`, nhiễu phép đo scale-down. Không revert (thuộc sở hữu sáng kiến khác); cần tắt tạm bằng thao tác vận hành trước khi đo, bật lại sau.

Phần còn lại bị merge đụng (MSK/CDC, migration .NET 8 accounting, provenance trace) không giao nhau với phạm vi ADR này.

## Mở rộng sang sandbox — Phương án B (27-07-2026)

**Bối cảnh:** Mở rộng tự nguyện sau khi phần develop xong (không bắt buộc). Audit phát hiện sandbox đã có sáng kiến Karpenter/spot riêng (MANDATE-02, PR #386/#415) dùng 2 NodePool: `default` (on-demand) và `spot` (opt-in qua toleration, chỉ `ad`+`product-reviews`). Mô hình opt-in cũ chỉ đạt trần **~13.6%** compute trên spot (ước tính tối đa ~44% dù vét cạn ứng viên) — không đủ đạt mục tiêu >50% của directive.

### Quyết định (Sandbox)

1. **Phương án B — đổi NodePool `default` sang `["spot", "on-demand"]`** (opt-out) thay vì mở rộng dần opt-in (Phương án A, trần chỉ ~44%). Đánh đổi: mô hình "fail-open" — xử lý ở Decision 2.
2. **An toàn mặc định = on-demand tập trung tại `default.schedulingRules.nodeSelector`** (`values-application.yaml`) thay vì khai từng service — service mới thêm sau này tự động an toàn. Vòng 2: `accounting`/`fraud-detection` được nâng `replicas:2` + PDB `maxUnavailable:1` để đồng nhất chuẩn an toàn với các service spot khác (Kafka consumer group xử lý partition khác nhau — không có nguy cơ duplicate).
3. **Thêm `image-provider`, `llm`, `ml-guard`, `accounting`, `fraud-detection` vào NodePool `spot`** — nâng tổng 11 service opt-in (tất cả off money-path), đủ chuẩn `PDB + replicas≥2 + preStop/terminationGrace` trước khi thêm toleration. Đẩy spot ratio sandbox vượt **>50%**.
4. **Vá graceful-drain cho `ad`** (bug thật phát hiện lúc audit, không liên quan trực tiếp mở rộng) — thiếu hoàn toàn `terminationGracePeriodSeconds`/`preStop` dù đã ở NodePool spot từ trước.
5. **Nâng `limits.cpu` NodePool `spot`** từ `8` lên `32` vCPU — đỉnh lý thuyết sau khi thêm 3 service mới (~8.8 vCPU) đã sát trần cũ.
6. **Sửa comment sai của biến `enable_karpenter_interruption_queue`, không sửa hành vi** — biến này không thực sự gate gì trong `karpenter.tf` (resource tạo vô điều kiện); "sandbox plan No changes" ở Decision 2 gốc đúng tình cờ vì queue vốn tồn tại sẵn từ PR #415/#386. Cố tình không thêm `count` vì sẽ khiến apply tiếp theo DESTROY queue thật đang chạy.
7. **Thêm `sync-wave: "0"` cho app `techx-corp`** để giảm (không loại bỏ hoàn toàn) rủi ro cửa sổ thời gian pod mới sinh ra lộ ra spot trước khi Deployment kịp cập nhật nodeSelector.
8. **Xoá `terraform/environments/sandbox/primary-schedule.tf`** (lịch scale cứng 2→3→2 node/ngày) — mâu thuẫn tinh thần "trả tiền theo demand", nhường co giãn cho Karpenter.

### Rejected options (Sandbox)

- Mở rộng dần opt-in (Phương án A): trần thực tế chỉ ~44%, không đủ tin cậy đạt >50%.
- Đổi `default` sang mixed nhưng không thêm an toàn mặc định: rủi ro fail-open — xem Decision 2.
- Để `accounting`/`fraud-detection` rơi tự do vào pool mixed: thay bằng opt-in tường minh — xem Decision 3.
- Graviton/arm64 cho sandbox: kế thừa deferred từ Decision 4 gốc.
- Giữ lịch cố định `primary-schedule.tf`: mâu thuẫn "trả tiền theo demand" — đã xoá (Decision 8).

### Đo lường thực tế (28-07-2026)

- **Spot 63.9%** trên compute Karpenter-managed (2300m/3600m CPU requests) — **ĐẠT >50%**. Đo bằng CPU-requests vì MNG floor (CoreDNS/Karpenter controller, không thể lên spot) sẽ kéo tỷ lệ toàn-cluster xuống méo (48.8% nếu tính cả MNG, 29.6% nếu đếm instance-hours ngang nhau bất kể workload).
- **Node-hours ≥30% theo đường cong tải: KHÔNG ĐẠT (đã kiểm chứng bằng load test thật).** Log ban đầu (khung 09:30–10:30 ICT) hoá ra chỉ ghi lại hệ quả của bài live spot-kill test, không liên quan tải — số 30.3%/31.9% tính trên dữ liệu đó đã bị rút lại. Sau đó đã **chạy trực tiếp một bài load test mới trên cluster** (28-07-2026, 06:51–07:05 UTC, đỉnh 450 user, giám sát `kubectl` mỗi 15-30s xuyên suốt): xác nhận HPA scale pod thật theo tải (`frontend` 2→10, `cart` 2→4 replica) nhưng **Karpenter không thêm node nào — giữ nguyên 4 node suốt bài test**, kể cả lúc tải đỉnh. Kết luận: ở kích thước pod/cluster hiện tại, node-hours không thay đổi theo tải trong khoảng 10-450 user (chênh lệch 0%, không đạt ≥30%) — đây là kết quả thật, không phải lỗi đo.
- Chi tiết đầy đủ + log gốc: [`EVIDENCE.md`](EVIDENCE.md).

### Rủi ro còn tồn đọng

- **Thứ tự apply bắt buộc tách 2 PR riêng biệt**: (1) `values.yaml`+`values-application.yaml`+`application.yaml`+`nodepool-spot.yaml` trước, verify pod luồng tiền có nodeSelector on-demand + Healthy; (2) chỉ sau đó merge `nodepool-default.yaml` (đổi capacity-type). Sai thứ tự = cửa sổ thời gian pod luồng tiền lộ ra spot thật.
- Graviton vẫn FAIL/deferred, kế thừa từ develop.
- `image-provider`/`llm`/`ml-guard`/`ad`/`fraud-detection` nằm trong `values.yaml` **shared** — thay đổi sẽ tự động áp dụng cho `develop` ở lần sync tiếp theo. Cần render `helm template` cả 2 môi trường trước khi merge (chưa làm).

### Rollback (Sandbox)

- NodePool `default` về on-demand-only: lật `capacity-type` về `["on-demand"]`.
- Rút 3 service mới khỏi NodePool `spot`: xoá `schedulingRules` tương ứng trong `values-application.yaml`.
- Bỏ an toàn mặc định on-demand: xoá `default.schedulingRules.nodeSelector` — **không** rollback riêng lẻ mục này mà không rollback luôn Decision 1.
- `limits.cpu` NodePool `spot`: sửa giá trị trực tiếp, không ảnh hưởng node đang chạy.

### Approval gates (Sandbox)

Bắt buộc merge 2 đợt tách biệt như mô tả ở §Rủi ro còn tồn đọng, verify `kubectl` thủ công giữa 2 đợt trước khi mở PR thứ 2. Status vẫn Proposed cho tới khi cả 2 PR merge + deploy thật — dù vậy bằng chứng đo spot/node-hours/SLO **đã có** (xem `EVIDENCE.md`).

## Rollback (Develop)

- Tắt Karpenter: thêm lại `exclude: '{karpenter-crd.yaml,karpenter.yaml,karpenter-nodepool.yaml}'` vào root-app.yaml — MNG floor (`min=2,max=3,desired=2`) đã đủ chịu tải trong lúc rollback.
- NodePool: lật `nodepool-default.yaml` về `capacity-type:[on-demand]` / `consolidationPolicy: WhenEmpty`.
- Interruption queue: `enable_karpenter_interruption_queue = false` trong `terraform/environments/develop/main.tf` — gate bằng `count` nên tự destroy gọn gàng (không cần `-target`).
- Graceful-drain `payment`: xoá block trong `values.yaml` — không có gì phụ thuộc vào nó.

## Approval gates (Develop)

`terraform plan`/`apply` cho `karpenter.tf` + `variables.tf`, review ArgoCD thủ công cho 3 Application `develop-karpenter*` trước sync đầu tiên, và demo live spot-kill (0 request rớt checkout) — tất cả đang chờ thực hiện. Status vẫn Proposed cho tới khi các bước này chạy xong trên cluster develop thật.
