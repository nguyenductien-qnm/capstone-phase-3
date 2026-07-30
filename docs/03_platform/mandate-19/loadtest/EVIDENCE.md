# Mandate-19 — Evidence (ảnh + số + công thức, map mục "Phải nộp")

> Mỗi mục: **ảnh đính kèm** (`img/`), **số đối chiếu** từ `README.md`, và **công thức tính** để
> mentor kiểm chứng lại được. Ảnh Grafana chụp bằng headless browser trên cửa sổ thời gian
> chính xác của từng run (time range hiện trên góc phải mỗi ảnh, giờ VN = UTC+7).

Cụm: develop `ecommerce-develop-dev-eks` (458), ns `techx-develop`. Node cố định **3 app + 1 ops**.

**⚠️ Đọc số cho đúng:** số trong bảng README là **client-side** (locust, theo từng bậc user);
số trên dashboard Grafana là **server-side** (span-based, gộp mọi route trong cửa sổ). Hai nguồn
độc lập nên lệch nhẹ là bình thường (vd p95 @40u: locust 33ms vs dashboard 48ms) — cùng bậc,
cùng kết luận; không so 1:1 từng con số.

---

## Phương pháp load test và ranh giới các phase

Bài test được chia thành ba phase riêng để tách việc **tìm capacity**, **xử lý bottleneck** và
**xác nhận hành vi toàn hệ thống**. Trạng thái replica/HPA của từng run phải được đối chiếu với
job YAML, `loadtest-runs-inventory.yaml` và ảnh Grafana; không suy ngược cấu hình chỉ từ kết quả.

### Phase 1 — Tìm capacity của flow cô lập

- Môi trường: develop.
- Với flow được chọn, các service cần cô lập được cố định ở `replicas = 1` và tắt HPA. Chỉ run có
  artifact chứng minh điều kiện này mới được dùng để ước lượng capacity một Pod.
- Tăng tải theo từng bậc cho tới khi flow vi phạm SLO.
- Dùng phase này để tìm service bão hòa đầu tiên và xác định safe planning capacity cho một Pod.

### Phase 2 — Xử lý bottleneck và xác nhận scaling

- Tune bottleneck đã tìm thấy, sau đó khôi phục HPA cho critical checkout path.
- Giữ nguyên số EKS node.
- Chạy lại cùng flow và cùng cách tăng tải để so sánh throughput, latency và requests/node.

### Phase 3 — Mixed traffic và overload

- Chạy representative mixed traffic theo đúng tỷ trọng workload trong test scenario.
- Bật load shedding cho browse; `/api/cart` và `/api/checkout` không dùng browse rate limit.
- Đếm riêng 429 chủ động, 5xx và lỗi kết nối để không đánh đồng “không bị shed” với “đạt SLO”.

Service-level test chỉ dùng để chẩn đoán bottleneck phát hiện từ end-to-end flow, không được dùng
làm kết quả capacity cuối cùng của toàn hệ thống.

| Flow | Cách test | Kết luận được phép rút ra | Evidence chính |
|---|---|---|---|
| Catalog/browse cô lập | Ghim bottleneck 1 Pod, tăng tải theo bậc tới khi vi phạm SLO | Capacity một Pod và bottleneck đầu tiên | Phase 3 job, README, ảnh per-pod |
| Checkout before/after | Giữ workload tương đương, so trước/sau tuning và HPA | Capacity đã chứng minh, improvement factor, requests/node | Checkout job, ảnh before/after |
| Mixed traffic | Giữ đúng tỷ trọng scenario, HPA hoạt động | Hành vi end-to-end sau tuning; không thay cho single-flow capacity | Phase 4 job, README, ảnh mixed |
| Overload/load shedding | Bơm vượt token bucket, tách browse và cart/checkout | Shed rate của route eligible và failure mode khi overload | Shed job, CSV/log, ảnh YC4 |

---

## E1+E2 — RPS đỉnh giữ SLO trước–sau (catalog flow, nút thắt frontend)

| Ảnh | Cửa sổ (VN) | Nội dung |
|---|---|---|
| ![before](img/m19-phase2-before-catalog-latency-baseline.png) | 21/07 09:35–09:51 | BEFORE (frontend limit 200m): p95 94.1ms, p99 486ms cuối bậc 40u |
| ![after](img/m19-phase2-after-catalog-latency-baseline.png) | 21/07 10:20–10:37 | AFTER (limit 500m): p95 48ms, p99 126ms — tail sập rõ |

**Số đối chiếu (locust @40u):** throttle frontend **9.3% → 2.1%** (↓4.4×), p99 **341 → 122ms**
(↓2.8×), p100 810 → 260ms, rps 19.8 → 19.9 (đã tuyến tính — cải thiện nằm ở tail, không phải rps).

**Công thức:** `cải thiện p99 = 341/122 = 2.8×` · `throttle = throttled_periods/periods` (PromQL
hiện trong ảnh E4).

## E3 — requests-per-node tăng, NODE KHÔNG ĐỔI (ràng buộc cốt lõi #19)

| Ảnh | Nội dung |
|---|---|
| ![nodes](img/nodes-identity-20260721-1515.png) | `kubectl get nodes -L eks.amazonaws.com/nodegroup` chụp 21/07 15:15 — GIỮA chuỗi run: 3 node primary (AGE 2d22h, và 12-102 tạo 23h đêm 20/07 — đều TRƯỚC mọi run) + 1 node ops. Bằng chứng identity: không node nào sinh thêm trong ngày đo. |
| ![k8s](img/m19-checkout-after-limits-k8s-scaling.png) | Dashboard K8s trong lúc test trần checkout AFTER: **Nodes 4/4 phẳng**, HPA scale pod (cart→6, checkout→4) — pod nở, node không nở. |

**Công thức density (checkout flow, SLO<1s, 3 node app):**

```
requests-per-node BEFORE = 27 rps / 3 node ≈ 9 rps/node
requests-per-node AFTER  = 76.3 rps / 3 node ≈ 25.4 rps/node   (×2.8, node không đổi)
```

Ghi chú ảnh k8s: 2 ô đỏ là ngưỡng màu mặc định của dashboard — "HPAs at Max = 3" là hành vi
ĐÚNG khi ép hệ tới trần; "Restarts = 5" đã truy Prometheus: là product-reviews (~5) + jaeger (~2),
KHÔNG service nào thuộc chain checkout đang đo (xem mục lỗi có sẵn bên dưới).

## E4 — Nút thắt thông lượng: tìm thấy + nới (deliverable "1 bottleneck")

| Ảnh | Nội dung |
|---|---|
| ![throttle-before](img/m19-checkout-before-throttle-explore.png) | Explore + PromQL hiện nguyên văn: throttle **email leo ~95%** @60u (payment 34%, currency 29% cùng khung) — nút thắt chain checkout |
| ![throttle-after](img/m19-checkout-after-limits-throttle-explore.png) | Cùng query, sau khi nới limit (16:40 rollout): throttle **sập về <10%** toàn chain |
| ![perpod](img/m19-phase3-perpod-latency-baseline.png) | Phase 3 (frontend ghim 1 pod): trần per-pod — @120u p95 622ms server-side, vẫn <1s |

**Số đối chiếu:** email **95.7% → 6.7%** (limit 100m→400m), payment 34.2→4.6%, currency 29.1→8.6%,
cart 13→3.1%, checkout 12.9→1.6%. Phase 3 chứng minh frontend xử lý **ít nhất 56.2 rps/pod**
với p95 vẫn dưới SLO 1s; **20 rps/pod là safe planning capacity** theo ngưỡng cảnh báo 200ms,
không phải trần tuyệt đối. Nút thắt frontend = concurrency SSR, không phải CPU (83m/500m,
throttle 5.2% tại bậc gãy cảnh báo 200ms).

**PromQL (in trên ảnh):**
```
100 * rate(container_cpu_cfs_throttled_periods_total{namespace="techx-develop",container=~"email|payment|currency|cart|checkout"}[2m])
    / rate(container_cpu_cfs_periods_total{namespace="techx-develop",container=~"email|payment|currency|cart|checkout"}[2m])
```

## E5 — Capacity checkout đã chứng minh TRƯỚC–SAU (before/after thứ hai — luồng ra tiền)

| Ảnh | Cửa sổ (VN) | Nội dung |
|---|---|---|
| ![co-before](img/m19-checkout-before-latency-baseline.png) | 21/07 16:03–16:32 | BEFORE: p95 3.15s / p99 4.63s đỏ — gãy SLO ở 40–60u |
| ![co-after](img/m19-checkout-after-limits-latency-baseline.png) | 21/07 16:37–17:00 | AFTER: p95 **533ms** / p99 889ms — khớp locust 532/844ms @60u |

**Điểm tải cao nhất đã giữ SLO trong các run:**
```
BEFORE: 26.9 rps (@20u; 40u gãy p95 1118ms) ≈ 27 rps
AFTER:  76.3 rps (@60u p95 532ms, vẫn đạt SLO)
Measured passing-point ratio = 76.3/26.9 ≈ 2.8×
```

Run AFTER chứng minh **capacity ≥ 76.3 rps** trong cấu hình và SLO đã nêu; đây chưa phải trần
tuyệt đối vì run chưa có bậc tải kế tiếp làm checkout vi phạm SLO. Cải thiện đạt được khi không
thêm node, chỉ nới limit 5 service và bổ sung HPA cho checkout-path.

## E6 — Demo xuống mềm (YC4: shed browse; cart/checkout được loại khỏi 429)

| Ảnh | Cửa sổ (VN) | Nội dung |
|---|---|---|
| ![yc4](img/m19-yc4-shed-demo-latency-baseline.png) | 21/07 14:40–14:50 | Flood ~300+ req/s: E2E p95 513ms, frontend p95 571ms — **giữa flood vẫn <1s** |
| ![yc4-throttle](img/m19-yc4-shed-demo-throttle-explore.png) | nt | checkout throttle ≈ **0%** suốt flood (cart nhói 8% một nhịp) — checkout-path không bị bóp |
| ![yc4-k8s](img/m19-yc4-shed-demo-k8s-scaling.png) | nt | Node 4/4, 74 pod Running, Pending 1 thoáng qua — **hệ không sập, node không nở** (ảnh này minh họa vế "không sập" nhìn từ hạ tầng, không phải bằng chứng scaling) |

**Số shed (locust demo 631 rps, 120s — bảng README):**
```
% shed browse = 45378 / 64448 = 70.4%   (bucket rl_browse 80 rps/pod × 2 pod)
% shed cart   = 0 / 10803     = 0%      (route checkout-path không dùng browse rate limit)
```
Cơ chế: Envoy local_ratelimit per-pod, route `/api/cart|/api/checkout` đặt TRÊN catch-all nên
không dính limit. Chi tiết + nghịch lý ClusterIP: `shed-verification-clusterip-vs-podip.md`.
(Ảnh Grafana không thể hiện 429 vì Envoy admin tắt — không có metric shed trong Prometheus;
bằng chứng 429 là output locust bên dưới.)

### Re-run 22/07 13:20–13:23 UTC — số 429 tươi, artifact GỐC trong repo

Chạy `locust-shed-demo-job.yaml` (900u FastHttp, ClusterIP `frontend-proxy:80`, 180s — bơm
~1.0–1.4k rps, vượt xa bucket):

| Route | reqs | 429 (shed) | % shed | 5xx | p50 |
|---|---|---|---|---|---|
| browse `/api/products` | 178,435 | **134,818** | **75.6%** | 3,073 (1.7%) + 190 lỗi transport/parser | 230ms |
| cart `/api/cart` (đối chứng) | 4,900 | **0** | **0%** | 251 (5.1%) + 5 connection refused | 710ms |

```
% shed browse = 134818 / 178435 = 75.6%     (429 tức thì — offered ~1.4k rps)
% shed cart   = 0      / 4900   = 0%        (không có dòng 429 trong shed_failures.csv)
browse lọt qua ≈ (178435 − 138081) / 180s ≈ 224 rps — khớp bucket 80/s × pod proxy
```

Các số trong bảng trên lấy cùng snapshot CSV (`shed_stats.csv` + `shed_failures.csv`).
`locust-final-output.log` được chụp muộn hơn vài request nên có tổng khác nhẹ; không trộn hai
snapshot trong cùng một phép chia. **Cart 0% shed chỉ chứng minh cart không nhận 429**; run này vẫn
có 251 response 5xx và 5 lỗi kết nối, vì vậy không dùng `0% 429` để khẳng định cart đạt SLO.

Điểm kỹ thuật đáng nói với mentor: bucket là per-pod nên khi HPA scale frontend-proxy 2→6 dưới
flood, tổng ngưỡng lọt nở theo (160→480 rps) — shed và HPA phối hợp: từ chối phần dư tức thì
bằng 429, đồng thời nở công suất có kiểm soát; frontend scale 2→10 hấp thụ phần lọt, node giữ 4.

**Artifact gốc:** `runs/yc4-shed-rerun-20260722/` — `shed_failures.csv` (dòng
`LocustBadStatusCode(code=429) × 134818` cho browse, cart không có dòng 429),
`shed_stats.csv`, `locust-final-output.log` (bảng stats + error report nguyên văn).

## E8 — Tham chiếu thêm

- **flashsale 200u (frontend max10):** ![flash](img/m19-flashsale-200u-max10-latency-baseline.png)
  ![flash-k8s](img/m19-flashsale-200u-max10-k8s-scaling.png) — CSV locust GỐC kèm theo:
  `runs/flashsale-200u-max10/locust_stats.csv` (+percentiles).
- **Phase 4 mixed 60u:** ![p4](img/m19-phase4-mixed-60u-latency-baseline.png) — p95 50.2ms/p99
  125ms, không service nào căng; chỉ frontend scale (5) → khớp kết luận nút thắt.
  (Đốm error frontend 0.617 req/s ở mép trái 15:20 là TRƯỚC khi run bắt đầu 15:24 — không thuộc run.)
- **Trần user-facing qua NLB (EC2 ngoài cụm):** 98 rps @200u giữ SLO — EC2 đã terminate, bằng chứng
  là số liệu README PHASE 6.5.

## ⚠️ Lỗi hạ tầng CÓ SẴN phát hiện khi test (không do tải)

- **product-reviews CrashLoopBackOff** (protobuf gencode 7.35.0 vs runtime 5.29.6) — restart cả khi
  không test (5 lần trong cửa sổ checkout-after). Cần fix build image riêng. Đã loại khỏi số Phase 4.
- jaeger restart ~2 lần dưới tải nặng (all-in-one, không HA) — quan sát, ngoài scope #19.

## E7 — ADR ký tên

`docs/mandate-19/ADR-mandate19-throughput-ceiling.md` — capacity trước/sau, nút thắt, cách nâng,
cơ chế shed; owner `lken1514`, contributor/reviewer ký `Nguyenthanhdat`. ✅

---

## Phụ lục: cách tái tạo ảnh & số

- Ảnh Grafana: headless Chromium (Playwright) qua `kubectl port-forward svc/grafana 3000:80`,
  URL kèm `from/to` epoch đúng cửa sổ run — ai cũng mở lại được bằng time range trong ảnh.
- Restarts truy vết: `sum by (namespace,pod)(increase(kube_pod_container_status_restarts_total[25m]))`
  tại `time=2026-07-21T10:00:00Z`.
- Job shed demo tái chạy: `locust-shed-demo-job.yaml` (900u FastHttp qua ClusterIP — bơm vượt
  bucket per-pod; lưu ý KHÔNG dùng constant_throughput vì latency request 200 sẽ ghìm offered load
  dưới ngưỡng bucket → không shed, xem lần thử 22/07 10:42Z chỉ đạt 107 rps → 503 thay vì 429).

```bash
export AWS_PROFILE=sso-develop
kubectl get nodes -L eks.amazonaws.com/nodegroup          # node không đổi
kubectl -n techx-develop get hpa                           # frontend 2/10, chain 2/4
kubectl -n techx-develop get deploy frontend -o jsonpath='{.spec.template.spec.containers[0].resources}'
```

---

## Phụ lục: công thức sizing — nguồn kiểm chứng + áp số đo thực của mandate-19

> Công thức lấy từ draft `isolated-flow-load-testing.md`, đã đối chiếu nguồn chính thức và
> **validate bằng chính số đo trong README này**. Chỉ giữ phần áp dụng được cho #19; phần
> N−1/drain rehearsal thuộc bài PDB/drain (INC-2), ngoài scope.

### 1. Replica theo capacity mỗi pod — `Replica_required = ceil(RPS_design / Safe_RPS_per_pod)`

Capacity theo RPS/Pod là mô hình planning dựa trên load test, không phải công thức autoscaling mặc
định của Kubernetes. Phase 3 đo frontend ghim 1 Pod: 56.2 rps vẫn giữ p95<1s, nhưng team chọn
`Safe_RPS_per_pod = 20 rps/pod` theo ngưỡng cảnh báo 200ms để có headroom →

```
RPS_design 120 rps → Replica_required = ceil(120/20) = 6
```
**Khớp thực đo:** phase 2 catalog @đỉnh, frontend kịch đúng **6 replica** (HPA max 6 thời điểm đó).

### 2. Replica theo HPA CPU — `Replica_CPU = ceil(CPU_required / (CPU_request × HPA_target))`

Đúng theo thuật toán HPA chính thức `desiredReplicas = ceil(current × currentMetric/desiredMetric)`
với utilization tính **trên requests** (kubernetes.io → Horizontal Pod Autoscaling): điểm cân bằng
là CPU/pod = request × target → replica ổn định = tổng CPU / (request × target). Áp số frontend:

```
CPU_cost_per_request = (116m − 10m) / 56.2 rps ≈ 1.9m per rps      (Phase 3, 1 pod)
CPU_required @120rps = 10m + 120 × 1.9m ≈ 238m
Replica_CPU = ceil(238m / (100m × 0.70)) = ceil(3.4) = 4
```

**→ Phát hiện đắt nhất:** `Replica_CPU = 4` **<** `Replica_required = 6`. Công thức chứng minh
bằng số điều đã thấy bằng thực nghiệm: frontend SSR nghẽn **concurrency trước khi nghẽn CPU**,
nên HPA CPU-target một mình sẽ under-scale — phải lấy `max(4, 6) = 6`. Đây chính là lý do
"nút thắt = concurrency Next.js, không phải CPU" ở mục E4.

### 3. Node capacity — `Allocatable = Capacity − kube-reserved − system-reserved − eviction-hard`

Nguồn: kubernetes.io → Reserve Compute Resources; scheduler chỉ nhìn **requests** (Manage
Resources for Containers). Áp số: t3.large (2 vCPU) → allocatable thực đo **1930m**;
`Nodes_base = max(ceil(ΣrequestCPU/1930m), ceil(ΣrequestMem/…), pods-per-node)` — với tổng
requests hiện tại (sau right-size) 3 node app là đủ kèm headroom, khớp thực tế node giữ 4 (3+1 ops)
suốt mọi phép đo.

### 4. Memory — `request ≈ P95(working_set) × SF`, `limit ≈ max_observed × SF`

Cùng nguyên tắc VPA recommender (percentile của working set, KHÔNG tuyến tính theo RPS).
Đã áp đúng kiểu này ở mục "Sizing SAU-SHED" (đo CPU/mem steady-state sau shed rồi đặt request
cho pod chạy ~55–65%).

### 5. Giới hạn của mô hình tuyến tính CPU

`CPU_cost_per_request` chỉ đúng ở vùng tải ổn định — chính data #19 minh họa: gần bão hòa
latency nổ trước khi CPU hết (frontend 83m/500m @bậc gãy cảnh báo), nên mô hình dùng để
**sizing khởi điểm**, còn trần thật phải đo (đúng ghi chú "draft, cần validate" trong tài liệu gốc).

**Safety factor 1.2–1.3:** quy ước headroom phổ biến (SRE workbook khuyến nghị dự phòng
N+1/N+2 theo mức độ quan trọng) — không phải hằng số chuẩn, cần review theo burst pattern
và tốc độ phản ứng HPA, như draft tự ghi chú.

---

## References — nguồn chính thống theo công thức

### 1. Throughput / RPS / concurrency

```text
RPS = Total requests / Test duration (seconds)
```

Google Cloud mô tả request throughput theo số request được phục vụ mỗi giây và khuyến nghị load
test để xác định capacity cũng như hành vi khi overload ([Google Cloud — backend load testing][ref-gcp-load]).

### 2. p95 và p99

```text
p95: 95% request hoàn thành trong thời gian này
p99: 99% request hoàn thành trong thời gian này
```

Locust tính percentile từ phân phối response time của các request đã ghi nhận
([Locust — response-time statistics][ref-locust-stats]).

### 3. Success rate / error rate

```text
Success rate = Successful requests / Total requests × 100%
Error rate   = Failed requests / Total requests × 100%
```

Google Cloud định nghĩa request-based availability theo tỷ lệ good requests trên total requests
([Google Cloud Observability — request-based SLI][ref-gcp-sli]).

### 4. CPU throttling ratio

```promql
sum(rate(container_cpu_cfs_throttled_periods_total[5m]))
/
sum(rate(container_cpu_cfs_periods_total[5m]))
```

cAdvisor định nghĩa hai CFS counter dùng trong tỷ lệ này ([cAdvisor Prometheus metrics][ref-cadvisor]);
Prometheus quy định `rate()` dùng cho counter và điều chỉnh counter reset
([Prometheus `rate()`][ref-prom-rate]).

### 5. Công thức HPA chính thức

```text
desiredReplicas =
ceil(currentReplicas × currentMetricValue / desiredMetricValue)
```

Đây là thuật toán được Kubernetes công bố cho Horizontal Pod Autoscaler
([Kubernetes HPA][ref-k8s-hpa]).

### 6. Capacity theo RPS mỗi Pod

```text
RPS_per_pod     = Service RPS / Ready Pods
Replica_capacity = ceil(Design RPS / Safe RPS per Pod)
```

GKE dùng maximum average RPS per Pod cho capacity-based load balancing và traffic autoscaling
([GKE traffic management][ref-gke-traffic]). `Safe RPS per Pod` của team phải lấy từ load test thực
tế; đó không phải con số mặc định của Kubernetes.

### 7. Tìm throughput ceiling

Google SRE khuyến nghị kiểm thử đến giới hạn capacity và quan sát failure mode khi overload vì khó
dự đoán trước tài nguyên nào sẽ cạn đầu tiên ([Google SRE — cascading failures][ref-google-sre]).
Nếu run mới chỉ chứng minh một bậc vẫn đạt SLO, tài liệu ghi `capacity ≥ observed RPS`, không gọi đó
là absolute ceiling.

### 8. Load shedding và HTTP 429

```text
Shed rate = Requests trả 429 / Total eligible requests × 100%
```

Envoy Local Rate Limit mặc định trả 429 khi token bucket hết token
([Envoy Local Rate Limit][ref-envoy]). AWS Builders' Library giải thích load shedding giữ goodput
ổn định khi offered load tiếp tục tăng ([AWS Builders' Library][ref-aws-shed]).

### Các phép tính thực nghiệm của team

```text
Improvement factor = AFTER / BEFORE
RPS per node       = Total RPS / Healthy app nodes
CPU cost per RPS   = ΔCPU / ΔRPS
```

> These are empirical calculations derived from the team's load-test measurements, not official
> Kubernetes formulas.

Các phép này phải kèm run, cửa sổ thời gian và input đo; không mô tả chúng là công thức tiêu chuẩn.

[ref-gcp-load]: https://docs.cloud.google.com/load-balancing/docs/backend-service-load-testing
[ref-locust-stats]: https://docs.locust.io/en/stable/_modules/locust/stats.html
[ref-gcp-sli]: https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring/sli-metrics/req-resp-metrics
[ref-cadvisor]: https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md
[ref-prom-rate]: https://prometheus.io/docs/prometheus/latest/querying/functions/#rate
[ref-k8s-hpa]: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
[ref-gke-traffic]: https://docs.cloud.google.com/kubernetes-engine/docs/concepts/traffic-management
[ref-google-sre]: https://sre.google/sre-book/addressing-cascading-failures/
[ref-envoy]: https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/local_rate_limit_filter
[ref-aws-shed]: https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/
