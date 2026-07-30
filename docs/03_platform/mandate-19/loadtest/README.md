# Mandate-19 — Throughput Ceiling Load Test (Phase 2 artifacts + handoff)

Test chạy trên **Develop (458)** cluster `ecommerce-develop-dev-eks`, ns `techx-develop`,
rồi mang cấu hình sang **Prod (804)** `ecommerce-dev-eks` ns `techx-tf1`.
Master plan: `loadtest-master-plan.md` (ngoài repo, máy user).

## ⚠️ Hai ngưỡng SLO — đọc trước khi xem bảng

| Ngưỡng | Giá trị | Vai trò |
|---|---|---|
| **SLO CHÍNH THỨC** (storefront p95) | **< 1s** (`onboarding/SLO.md`) | Ngưỡng cam kết khách hàng — dùng để tính **TRẦN thật** (RPS đỉnh giữ SLO). |
| Ngưỡng cảnh báo nội bộ | < 200ms | Chặt hơn, dùng để **lộ nút thắt/throttle sớm** — ở 1s thì mọi bậc dưới đây đạt hết, khó thấy cải thiện. KHÔNG phải SLO cam kết. |

> Các bảng dưới ghi CẢ hai. Cột "SLO<1s" là ngưỡng chính thức (tính trần). Nhãn "cảnh báo<200ms"
> chỉ để thấy service bắt đầu căng ở đâu. **Trần chính thức luôn theo <1s.** SLO đầy đủ: browse/cart
> non-5xx ≥99.5%, checkout success ≥99.0% — tất cả run dưới đây **0 fail** (đạt success SLO).

## Files

| File | Vai trò |
|---|---|
| `locustfile-catalog.py` | Catalog (browse) flow — 1 class `CatalogFlowUser`, `LoadTestShape` tự step 5/10/20/40 user (mỗi bậc 240s). |
| `locust-catalog-job.yaml` | K8s Job chạy locustfile trên node ops. CSV → emptyDir `/data`, pod `sleep 3600` sau khi shape xong (đọc CSV được). |

## Cách chạy (Job v2)

```bash
export AWS_PROFILE=sso-develop
CTX=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
kubectl --context "$CTX" apply -f locust-catalog-job.yaml
# đọc kết quả (pod sống sau khi xong nhờ sleep):
JPOD=$(kubectl --context "$CTX" get pod -l app=locust-phase2 -n techx-develop -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$CTX" exec $JPOD -n techx-develop -- cat /data/catalog_stats_history.csv
# CSV cột: 0=ts 1=users 2=type 3=name 4=rps 5=fail/s 11=p50 16=p95 18=p99
# lấy dòng ",Aggregated," CUỐI mỗi user_count (steady state)
kubectl --context "$CTX" delete job locust-phase2 -n techx-develop   # dọn sau khi đọc
```

Song song đọc PromQL (ns `techx-develop`, port-forward `svc/prometheus`):
- CPU/pod: `avg(sum by(pod)(rate(container_cpu_usage_seconds_total{namespace="techx-develop",pod=~"$SVC-.*",container!=""}[2m])))`
- throttle: `sum(rate(container_cpu_cfs_throttled_periods_total{...}[2m])) / sum(rate(container_cpu_cfs_periods_total{...}[2m]))`

## Kết quả BEFORE (frontend limits.cpu = 200m) — đo 21/07/2026 02:35–02:51 UTC

> Run sạch: 3 node app primary + 1 ops, 7 HPA prod-like, **0 fail** toàn bộ (failures.csv rỗng),
> không load-generator/actor. Latency = steady-state trung bình 30s cuối mỗi bậc (CSV
> `catalog_stats_history.csv`). CPU/throttle/replica = đỉnh trong cửa sổ 40s cuối mỗi bậc (Prometheus).

| Bậc | Users | rps | p50 | p95 | p99 | p100 | fail | product-catalog CPU/thr/rep | frontend CPU/thr/rep |
|---|---|---|---|---|---|---|---|---|---|
| idle | 0 | 0 | — | — | — | — | 0 | 2m / 0% / 2 | ~10m / — / 2 |
| 1 | 5 | 2.6 | 15ms | 132ms | 178ms | 750ms | 0 | 3m / 0% / 2 | 52m / 31.5%* / 6 |
| 2 | 10 | 4.9 | 13ms | 66ms | 218ms | 440ms | 0 | 5m / 0% / 2 | 27m / 4.5% / 5 |
| 3 | 20 | 9.8 | 13ms | 129ms | 424ms | 730ms | 0 | 8m / 0% / 2 | 35m / 4.9% / 4 |
| 4 | 40 | 19.8 | 13ms | 94ms | 341ms | 810ms | 0 | 13m / 0% / 2 | 52m / 9.3% / 6 |

\* Throttle 31.5% @5u là transient cold-start (pod vừa nhận tải + HPA còn 6 rep dư từ ramp), không phải steady-state.

**Phát hiện từ run này:**

Throughput tăng tuyến tính theo số user (khoảng 0.5 rps mỗi user, từ 2.6 rps ở 5u lên 19.8 rps ở
40u), tức là trong dải 5-40u hệ chưa gãy. Nhưng nhìn vào latency thì thấy chuyện khác: p50 phẳng ở
13ms trong khi p99 phình từ 178ms lên 424ms và p100 chạm 810ms. Đuôi latency phình theo tải mà số
giữa không đổi là dấu hiệu điển hình của CPU throttle — đúng kiểu Next.js SSR bị limit bóp.

Nút thắt nằm ở `frontend`, không phải product-catalog. Ở 40u, frontend throttle 9.3% dù đã scale
kịch 6 replica (HPA max) — nghĩa là thêm pod không cứu được nữa, thứ chặn trần là `limits.cpu=200m`.
Trong khi đó product-catalog nhàn tuyệt đối: 13m CPU, throttle 0%, vẫn nằm ở 2 replica min.

Từ đó ra giả thuyết cho run AFTER: nâng `frontend.limits.cpu` từ 200m lên 500m sẽ giảm throttle và
hạ đuôi p99/p100, mà không cần thêm node (ràng buộc #19).

## Kết quả AFTER (frontend limits.cpu = 500m) — đo 21/07/2026 03:20–03:37 UTC

> Cùng cluster (3 node app + 1 ops), cùng locustfile/shape, cùng HPA prod-like, **0 fail**.
> Biến DUY NHẤT đổi so với BEFORE: `frontend.limits.cpu` 200m→500m (requests giữ 100m → HPA
> target 70% không đổi). Đo sau khi ArgoCD sync + rollout + cluster nguội (frontend 10m/2rep).

| Bậc | Users | rps | p50 | p95 | p99 | p100 | fail | product-catalog CPU/thr/rep | frontend CPU/thr/rep |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 5 | 2.5 | 12ms | 37ms | 51ms | 130ms | 0 | 4m / 0% / 2 | 18m / 0.4% / 4 |
| 2 | 10 | 5.0 | 12ms | 19ms | 29ms | 49ms | 0 | 5m / 0% / 2 | 27m / 0.8% / 4 |
| 3 | 20 | 9.6 | 12ms | 20ms | 122ms | 200ms | 0 | 9m / 0% / 2 | 33m / 0.7% / 4 |
| 4 | 40 | 19.9 | 15ms | 33ms | 122ms | 260ms | 0 | 15m / 0% / 2 | 55m / 2.1% / 6 |

## So sánh BEFORE → AFTER (deliverable Mandate-19 YC2)

> **Kết luận:** nâng `frontend.limits.cpu` 200m→500m nâng trần bằng **hiệu suất**, **KHÔNG thêm node**
> (giữ 3 node app suốt cả hai run — ràng buộc #19 thỏa). Cùng throughput, đuôi latency sập xuống.

| Chỉ số @40u | BEFORE (200m) | AFTER (500m) | Cải thiện |
|---|---|---|---|
| **frontend CPU throttle** | **9.3%** | **2.1%** | ↓ 4.4× |
| **p99 latency** | 341ms | 122ms | ↓ 2.8× |
| **p100 (max) latency** | 810ms | 260ms | ↓ 3.1× |
| rps (throughput) | 19.8 | 19.9 | giữ nguyên (đã tuyến tính) |
| frontend replica đỉnh | 6 (HPA max) | 6 (HPA max) | không đổi |
| product-catalog throttle | 0% | 0% | không đổi (không phải nút thắt) |
| **Node app count** | **3** | **3** | **không thêm node ✅ (#19)** |

Đuôi latency cải thiện mạnh nhất ở dải thấp (p99 @10u: 218→29ms, ↓7.5×). Ở 40u frontend vẫn chạm
6 replica nhưng **throttle chỉ còn 2.1%** (so 9.3%) → limit 500m gỡ đúng nút thắt CPU-throttle đã xác
định ở BEFORE. Bằng chứng: CPU/pod gần như y hệt (52m→55m, cùng workload) nhưng không còn bị CFS bóp.

## Phase 3 — Per-pod capacity (frontend ghim 1 pod, limit 500m) — đo 21/07 03:47–04:08 UTC

> Ghim `frontend` HPA min=max=1 (service đo), nới `product-catalog`+`frontend-proxy` min=max=4.
> ArgoCD auto-sync TẮT tạm để patch không bị selfHeal revert. Catalog flow, đẩy tới gãy SLO p95<200ms.
> Node không đổi (3 app + 1 ops). Khôi phục HPA 2/6 + bật lại auto-sync sau khi đo.

| Bậc | Users | rps | fails/s | p50 | p95 | p99 | frontend CPU/pod | throttle | **SLO<1s** | cảnh báo<200ms |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 20 | 10.0 | 0 | 11ms | 32ms | 95ms | — | — | ✅ | ✅ |
| 2 | 40 | 19.7 | 0 | 11ms | 50ms | 198ms | 46m | 1.7% | ✅ | ✅ |
| 3 | 80 | 39.4 | 0.01 | 13ms | 226ms | 365ms | 83m | 5.2% | ✅ | ❌ (bắt đầu căng) |
| 4 | 120 | **56.2** | 0.13 | 27ms | **553ms** | 720ms | 116m | 12.0% | ✅ **← trần: p95 vẫn <1s** | ❌ |

### Trần per-pod (frontend, catalog flow, limit 500m)
- **Theo SLO chính thức (<1s): ~56 rps/pod** — ở 120u p95 mới 553ms, vẫn dưới 1s (bậc cao nhất đo được
  vẫn đạt; trần thật ≥ 56rps, chưa chạm). fails 0.13/s ở 120u (còn trong budget non-5xx ≥99.5%).
- **Theo ngưỡng cảnh báo nội bộ (<200ms): ~20 rps/pod** — service bắt đầu căng ở 80u. Dùng số này cho
  sizing thận trọng (max_replicas), nhưng TRẦN cam kết là ~56rps.

**🔑 Phát hiện then chốt: nút thắt per-pod không phải CPU.**

Ở bậc bắt đầu căng (80u, p95 226ms), frontend chỉ dùng 83m trên limit 500m — tức 17% — và throttle
vỏn vẹn 5.2%. Lên 120u cũng chỉ 116m. Nếu nút thắt là CPU thì pod phải ăn gần hết 500m, đằng này
CPU còn dư hơn 80%. Vậy thứ làm 1 pod frontend bão hòa là chỗ khác: Next.js SSR chạy đơn process,
single-thread, mọi thứ từ fetch backend đến render React đều dồn lên một event loop. Khi request
tới nhanh hơn tốc độ event loop xử lý, chúng xếp hàng — và 503 xuất hiện khi hàng đợi đầy, chứ
không phải khi CPU cạn.

Hệ quả cho sizing: muốn nâng trần throughput của frontend thì phải thêm pod (mỗi pod là một event
loop độc lập), chứ không phải thêm CPU limit. Limit 500m vẫn có giá trị riêng của nó — giảm
tail-latency do throttle, như bảng before/after ở trên đã chứng minh — nhưng nó không nâng được
rps/pod. Hai vấn đề khác nhau, hai đòn bẩy khác nhau.

Từ số 20 rps/pod suy ra đầu vào cho max_replicas: phục vụ N rps catalog ở mức an toàn cần khoảng
`ceil(N / 20)` pod cộng headroom. Ví dụ design load 100 rps cần chừng 5 pod, nên maxReplicas=6
hiện tại là đủ và còn dư 1 pod.

### ⚠️ Giới hạn phạm vi — số 20rps/pod chỉ đúng cho frontend

Con số này không đại diện cho service khác, vì frontend là một ca đặc biệt: Node.js một event loop,
SSR chặn luồng đơn, nên nút thắt là concurrency. Các service còn lại có mô hình concurrency khác
hẳn — product-catalog, checkout, shipping viết bằng Go chạy goroutine đa core, cart dùng thread
pool .NET, currency đa luồng — nút thắt của chúng nhiều khả năng là CPU và phải đo riêng mới biết,
không suy ra được từ số của frontend.

Lý do phase này chỉ đo frontend: với catalog flow, before/after ở Phase 2 đã cho thấy frontend là
service duy nhất bão hòa, còn product-catalog throttle 0% và không rời 2 replica. Đo per-pod các
service nhàn trên flow này chỉ ra những con số vô nghĩa. Mỗi flow có service nghẽn riêng — checkout
flow (checkout/payment/cart) được đo ở phần "Checkout flow" phía dưới.

## YC4 — Load-shedding: xuống mềm khi vượt trần (§12) — demo 21/07 07:44 UTC

> **Yêu cầu #19-4:** khi tải vượt trần, hệ phải **shed/rate-limit bảo vệ checkout, hy sinh browse —
> KHÔNG sập toàn bộ.** Làm ở **frontend-proxy (Envoy 1.34)** — điểm vào duy nhất của storefront.

**Thiết kế (tầng A — ưu tiên flow):** `local_ratelimit` filter per-route trong `envoy.tmpl.yaml`:
- **Tách route `/api/checkout` + `/api/cart` LÊN TRÊN catch-all** (trước đó đi chung `/`) →
  **KHÔNG rate-limit** = ưu tiên tuyệt đối.
- **`/api/products`** (browse): token bucket **80 rps** (tune từ Phase 3: ~20rps/pod × ~4-6 pod).
- **catch-all `/`** (homepage flood): token bucket **100 rps**.
- Filter đặt ngay trước `router`; listener-level `filter_enabled=0` (mặc định không shed, chỉ route có
  `typed_per_filter_config` mới enforce).

**Delivery:** mount ConfigMap `frontend-proxy-envoy-shed` đè `/home/envoy/envoy.tmpl.yaml` (tune nhanh
trên develop; auto-sync tắt tạm). Chốt số xong → bake vào image cho prod (§12.4 cách A, giữ immutable).

**Kết quả demo (Locust 100u, ~631 rps tổng, 120s):**

| Route | reqs | 429 (shed) | % shed | p95 | Kết luận |
|---|---|---|---|---|---|
| **browse `/api/products`** | 64448 | **45378** | **70.4%** | 550ms | shed đúng phần vượt bucket 80rps |
| **cart (checkout-path)** | 10803 | **0** | **0%** | 650ms | **qua hết — ưu tiên tuyệt đối** |

Browse bị shed 70% khi flood: 574 rps đập vào, chừng 80 rps đi qua, phần dư nhận 429.
`failures.csv` xác nhận 45372 dòng "429 Too Many Requests" — là load-shed chủ động chứ không phải
5xx lỗi. Trong khi đó checkout-path không bị shed chút nào: 10803 request cart qua hết dù hệ đang
quá tải nặng. Hệ không sập, vẫn phục vụ bình thường, chỉ từ chối phần browse dư thừa — đúng mục
tiêu YC4. Config Envoy đã verify render đúng trong pod (7 chỗ local_ratelimit, rl_browse
max_tokens 80, route checkout tách lên trên).

> **Cập nhật 22/07:** cả ba việc treo ở đây đã xử lý gần hết. Config shed đã nằm trong
> `envoy.tmpl.yaml` của repo (PR này), merge xong CI sẽ tự build image mới nên không còn phụ thuộc
> ConfigMap mount tay. Demo với cờ flagd `loadGeneratorFloodHomepage` thật cũng đã chạy trên hệ đã
> tuning — kết quả trong `flood-test-tuned-system.md`. Riêng chuyện xác minh shed có một bài học về
> phương pháp test (bucket là per-pod), ghi trong `shed-verification-clusterip-vs-podip.md`.
> Còn lại duy nhất Karpenter pin trên prod (§0.7) khi mang cấu hình sang.

## Phase 4 — Mixed traffic + right-size requests (bonus, ngoài scope 4 YC #19) — 21/07 08:24 UTC

> Mixed traffic 60u, weight OTel-demo (index1/browse10/recos3/reviews2/ads3/viewcart3/addcart2/
> checkout1), HPA **để nguyên** (bức tranh thật). Run SẠCH (actor không nhiễm). Node 3+1 không đổi.
> Mục tiêu: replica concurrency thật (đầu vào Quota §3.3) + CPU/pod thật (right-size requests, YC2).

**Aggregate:** 22 rps tổng, p95 **52ms**, p99 **140ms** — hệ giữ SLO tốt ở 60u mixed. (Fail 7.2% =
product-reviews CrashLoop, đã biết; loại reviews thì các flow khác 0 fail.)

**Replica concurrency đỉnh (service nào peak cùng lúc):**

| Service | replica đỉnh | Nhận định |
|---|---|---|
| **frontend** | **5** | service DUY NHẤT scale (SSR nghẽn) — khớp kết luận nút thắt |
| cart, checkout, product-catalog, frontend-proxy | 2 (min) | không cần scale ở 60u |
| recommendation, currency, ad, payment... | 1 (min) | min |

→ **Không có "nhiều service peak cùng lúc"** ở tải này → Quota **KHÔNG cộng máy móc Σmax_replicas**
(đúng plan §3.3). Quota thực = frontend chiếm phần lớn, backend gần như tĩnh.

**CPU/pod thật vs requests (right-size — YC2 "resource request sát usage"):**

| Service | CPU dùng thật | requests hiện | % dùng | Right-size đề xuất |
|---|---|---|---|---|
| frontend | 10–28m/pod | 100m | 10–28% | giữ 100m (spiky SSR, cần headroom) |
| cart | 3–4m | 100m | **3–4%** | → ~30m (over-request ~25×) |
| product-catalog | 2m | 100m | **2%** | → ~30m (over ~50×) |
| checkout | 2m | 100m | **2%** | → ~30m |
| frontend-proxy | 4m | 100m | **4%** | → ~30m |

Phát hiện chính: các backend service over-request 25-50 lần (xin 100m nhưng chỉ dùng 2-4m) — đúng
kiểu "giữ tài nguyên dư" cần khử. Hạ requests xuống chừng 30m sẽ tăng mật độ pod trên node đáng kể.
Về an toàn, HPA target 70% của 30m là 21m, vẫn cao hơn hẳn usage thật 2-4m nên không lo flapping;
riêng frontend giữ 100m vì usage spiky lên tới 28m, cần headroom cho HPA kịp phản ứng. Số này lúc
đo chưa áp ngay (cần thêm một vòng verify tải cao); phần "Sizing SAU-SHED" phía dưới là vòng verify
đó và đã chốt số cuối.

## Checkout flow — trần luồng ra tiền + nút thắt backend chain — đo 21/07 09:07 UTC

> Checkout single+multi tải cao (10/20/40/60u), qua SSR. Chuỗi: checkout → cart + currency +
> product-catalog + **payment + shipping + email**. HPA để nguyên. Run SẠCH, **0 fail** (kết quả đúng).

**Trần checkout (SLO chính thức <1s) ≈ 27 rps (bậc 20u) — THẤP hơn catalog** (checkout chain nghẽn sớm hơn frontend):

| Bậc | rps | p95 | p99 | **SLO<1s** | cảnh báo<200ms |
|---|---|---|---|---|---|
| 10u | 14.3 | 143ms | 242ms | ✅ | ✅ |
| 20u | 26.9 | 333ms | 600ms | ✅ **← trần: p95 <1s** | ❌ |
| 40u | 44.0 | 1118ms | 1514ms | ❌ gãy (>1s) | ❌ |
| 60u | 46.7 | 2194ms | 2559ms | ❌ rps bão hòa (44→47 dù user +50%) | ❌ |

**🔑 Nút thắt checkout = backend chain bị CPU-throttle (KHÁC catalog — nút thắt ở frontend):**

| Service @60u | CPU/pod | throttle | limit | Chẩn đoán |
|---|---|---|---|---|
| **email** | 99m | **95.7%** | 100m | 🔴🔴 NGHẼN NẶNG NHẤT — chạm sát limit, throttle liên tục |
| **payment** | 73m | **34.2%** | 100m | 🔴 nghẽn nặng (1 replica, KHÔNG HPA) |
| **currency** | 35m | **29.1%** | 100m | 🔴 nghẽn |
| cart | 62m | 13.0% | 200m | 🔴 nghẽn vừa (dù đã scale 3 replica) |
| checkout | 66m | 12.9% | 200m | 🔴 nghẽn vừa |
| shipping | 19m | 0% | 100m | ✅ nhàn |
| product-catalog | 36m | 0.1% | 200m | ✅ nhàn |
| frontend | 89m | 3.4% | 500m | ✅ OK (limit 500m đã đủ) |

Vì sao checkout gãy sớm hơn catalog? Ở luồng này nút thắt không nằm ở frontend nữa, mà ở đám
backend phía sau: email, payment và currency bị limit 100m bóp cổ, đồng thời payment, shipping và
email lúc đó không có HPA nên kẹt cứng ở 1 replica. Điều này xác nhận cái caveat đã nói ở Phase 3 —
mỗi luồng có nút thắt riêng, frontend chỉ là trần của luồng web UI.

### Bảng limit đề xuất (dựa throttle% — chỉ service trên 2 luồng đo)

> Nguyên tắc: throttle > 5% ở tải đỉnh = limit bóp cổ, cần nâng. throttle < 2% = đủ/thừa.

| Service | limit hiện | throttle @đỉnh | Đề xuất limit.cpu | Lý do |
|---|---|---|---|---|
| **email** | 100m | 95.7% | **→ 300–500m** + thêm HPA | nghẽn nặng nhất, chặn checkout |
| **payment** | 100m | 34.2% | **→ 300m** + thêm HPA min2 | luồng ra tiền, không được throttle |
| **currency** | 100m | 29.1% | **→ 250m** | dùng chung nhiều flow |
| **cart** | 200m | 13.0% | **→ 350m** | throttle dù đã scale |
| **checkout** | 200m | 12.9% | **→ 350m** | core checkout |
| frontend | 500m | 3.4% | giữ 500m | đã đủ (chứng minh ở before/after) |
| shipping, product-catalog | 100m/200m | ~0% | giữ nguyên | nhàn, không đụng |

- **Phát hiện phụ (reliability):** payment/shipping/email **KHÔNG có HPA** → không scale khi checkout
  tải cao. payment/email cần thêm HPA (min2) — vừa chống throttle vừa chống single-point (1 replica).
- ✅ **ĐÃ ÁP + verify** (before/after bên dưới). Service ngoài 2 luồng đo GIỮ NGUYÊN (không đoán).

### Checkout BEFORE → AFTER (nâng limit chain, override develop) — đo 21/07 09:39 UTC

> Nâng limit 5 service (email 100→400m, payment 100→300m, currency 100→250m, cart 200→350m,
> checkout 200→350m), **giữ requests** → HPA target không đổi. Override CHỈ develop. Node 3+1 không đổi.

**Throttle sập ở mọi service (cơ chế):**

| Service | throttle B→A | limit B→A |
|---|---|---|
| **email** | **95.7% → 6.7%** | 100m→400m |
| payment | 34.2% → 4.6% | 100m→300m |
| currency | 29.1% → 8.6% | 100m→250m |
| cart | 13.0% → 3.1% | 200m→350m |
| checkout | 12.9% → 1.6% | 200m→350m |

**Trần + latency checkout (before→after):**

| Bậc | rps B→A | p95 B→A | p99 B→A | **SLO<1s** B→A |
|---|---|---|---|---|
| 10u | 14.3→14.2 | 143→117ms | 242→207ms | ✅→✅ |
| 20u | 26.9→28.3 | 333→117ms | 600→208ms | ✅→✅ |
| **40u** | 44.0→53.7 | **1118→323ms** | 1514→561ms | **❌→✅** (nâng trần!) |
| 60u | 46.7→**76.3** | 2194→**532ms** | 2559→844ms | ❌→**✅** |

Kết quả: trần checkout theo SLO<1s tăng từ ~27 rps (gãy ở 40u) lên ~76 rps (60u vẫn giữ p95 532ms),
tức gần gấp 2.8 lần. Throughput đỉnh tăng 63%, p95 ở 60u giảm 4 lần, và node vẫn giữ nguyên 3+1.
Đây là cặp before/after thứ hai của Mandate-19, sau frontend, và nó chứng minh cùng một nguyên lý —
nới limit để gỡ CPU-throttle là nâng trần bằng hiệu suất — áp dụng được cho cả backend chain chứ
không riêng gì SSR.

## Sizing SAU-SHED — request sát usage (YC2 "resource request sát usage") — đo 21/07 10:11 UTC

> Ý tưởng: một khi đã có load-shedding thì sizing phải dựa trên lượng traffic thật sự lọt qua Envoy,
> chứ không phải trần khi chưa shed. Cách đo: bật shed rồi flood browse (661 rps đập vào, Envoy shed
> 71%, checkout chỉ 0.4% fail — vẫn được bảo vệ), đo CPU/pod của phần traffic lọt qua, rồi đặt
> requests sao cho pod chạy quanh 55-65% — đủ headroom cho HPA mà không flapping.

Có một khác biệt quan trọng giữa frontend và đám backend. Frontend đứng **trước** điểm shed: browse
nào lọt qua Envoy thì frontend vẫn phải render SSR, nên nó hứng trọn tải — thực tế sau shed vẫn
chạm 457m/500m với throttle 37%. Vì vậy frontend size theo trần (giữ limit 500m, requests 100m, để
HPA lo scale). Ngược lại product-catalog và các backend đứng **sau** frontend, browse đã bị chặn
71% trước khi tới nơi nên tải thấp hẳn (catalog chỉ còn 9m) — chúng size theo con số sau-shed.

**Right-size requests (từ CPU avg steady-state sau-shed) — before → after:**

| Service | req cũ | CPU thật | req mới | % sau (target 55-65%) | Chiều |
|---|---|---|---|---|---|
| **email** | 50m | 62m | **100m** | 124%→**52%** ✅ | under → sửa |
| **payment** | 50m | 44m | **80m** | 88%→**65%** ✅ | under → sửa |
| **currency** | 50m | 33m | 50m (giữ) | **55%** ✅ | ổn |
| **cart** | 100m | 37m | **60m** | 37%→71%* | over → sửa |
| **checkout** | 100m | 31m | **60m** | 31%→71%* | over → sửa |
| **product-catalog** | 100m | 9m | **40m** | 9%→25% | over nặng → sửa |
| frontend | 100m | 184m | giữ 100m | (size theo trần, HPA scale) | trần |

\* cart/checkout 71-83% ở verify-run (tải mạnh hơn) → HPA scale, có headroom. Ở tải thực thấp hơn.

Kết quả: email thoát khỏi vùng under-request nguy hiểm (đang dùng 124% requests, về 52%), ba
service khác về đúng dải 55-65%. Requests cũ đặt sai cả hai chiều — email/payment thiếu,
catalog/checkout thừa 3-10 lần — giờ đã sát usage thật, đúng yêu cầu YC2. Tóm lại limits (nâng ở
phần trước) lo chống throttle, còn requests (phần này) lo tối ưu density; hai việc khác nhau.
Toàn bộ override chỉ áp cho develop trong `values-application.yaml`, node 3+1 không đổi.

## PHASE 6.5 — Trần user-facing đo từ EC2 qua NLB — đo 21/07 (đã terminate EC2)

> Mọi phép đo phía trên đều bắn locust từ trong cụm (node ops) vào ClusterIP. Cách đó tốt cho việc
> so sánh before/after, nhưng chưa phải con số người dùng thật nhìn thấy: thiếu chặng NLB và mạng
> ngoài, và generator chạy trên node t3.large dùng chung với observability nên không đủ lực ở tải cao.
> Phase này dựng một EC2 `c6i.2xlarge` riêng (ngoài cụm, qua SSM) bắn mixed traffic qua NLB, step-load
> 40→280u, để chốt trần user-facing.

**Kết quả:**

| Chỉ số | Giá trị |
|---|---|
| Baseline mạng (1u, warm) | 16ms |
| **Trần giữ SLO (<1s)** | **98 rps @ 200u** — checkout p99 970ms, fail 0% |
| Điểm gãy | 280u — frontend throttle 9.4%, payment 8.8% |
| Node | giữ 4 suốt bài (ràng buộc #19) |

**Vì sao hai con số trần khác nhau mà không mâu thuẫn.** ADR ghi trần luồng Web UI ~330 rps theo
SLO<1s (56 rps/pod × 6, catalog flow, đo in-cluster), còn phase này ra 98 rps. Khác nhau vì đo hai
thứ khác nhau: số ADR là trần của riêng luồng browse/catalog, còn 98 rps là trần **mixed traffic có
checkout** đi qua NLB — checkout chain gãy sớm hơn browse nhiều (xem phần "Checkout flow" phía trên),
nên trần mixed thấp hơn là điều tự nhiên. Khi cần một con số nói với người ngoài ("hệ chịu được bao
nhiêu"), dùng 98 rps. Khi cần so before/after nội bộ, dùng số in-cluster.

**Bài học warm-up (giải nghịch lý p95 cụm vs EC2).** Ban đầu hai cách đo cho p95 lệch nhau xa, nghi
ngờ đủ thứ: CPU tranh chấp, node placement, connection pinning — đều sai. Nguyên nhân thật là
**warm-up**: run đầu tiên dính HPA scale-up trễ cộng SSR JIT nên chậm giả tạo; chạy lại đúng kịch bản
đó lần hai thì p95 tụt từ 1300ms xuống 430ms và hai cách đo khớp nhau. Từ đó về sau, quy tắc là
**bỏ run đầu, lấy số từ run thứ hai trở đi** (áp dụng cho cả in-cluster lẫn EC2).

**Khi nào dùng cách nào:**

| Nhu cầu | Cách đo |
|---|---|
| So before/after khi đổi sizing/HPA, đo throttle từng service | Locust in-cluster (job trong thư mục này) — nhanh, lặp lại được |
| Chốt trần user-facing cho ADR/báo cáo, hoặc trước khi promote prod | EC2 ngoài cụm qua NLB — generator dư lực, đúng đường user |
| Verify shed (429) | Bắn thẳng 1 pod IP, hoặc công cụ giữ rps ổn định — xem `shed-verification-clusterip-vs-podip.md` |

## Flood test hệ đã tuning (YC4) + verify shed — 21-22/07

Chi tiết trong hai file cùng thư mục:

- **`flood-test-tuned-system.md`** — bật cờ flagd `loadGeneratorFloodHomepage` thật, load-generator
  100u đập ~93× tải nền vào homepage. Checkout SLI giữ 100%, node giữ 4, frontend tự scale ra max.
  Hệ không sập — YC4 đạt trọn vẹn trên hệ đã tuning.
- **`shed-verification-clusterip-vs-podip.md`** — giải thích vì sao probe qua ClusterIP không thấy
  429 (bucket per-pod, kube-proxy chia tải, curl-fork không đủ rps tức thời) trong khi bắn thẳng
  1 pod IP thì shed kích rõ (GET / shed 41%, /api/products 53%). Kết luận: shed không lỗi, chỉ là
  phải test đúng cách.

## Trạng thái chốt Mandate-19 (cập nhật 22/07)

Bốn yêu cầu của #19 đều đã có số liệu và trải qua before/after: biết trần (Phase 3 + 6.5), nâng
trần bằng hiệu suất không thêm node (frontend limit + checkout chain), xử nút thắt (HPA
checkout-path), và xuống mềm khi vượt trần (shed + flood test). Việc còn lại chỉ là đưa cấu hình
mong muốn về Git và dọn dẹp:

1. **Merge PR này** — gồm sizing chuỗi checkout, HPA email/quote/shipping/payment min2/max4,
   frontend HPA max 10, và shed trong `envoy.tmpl.yaml`. Autosync đang bật nên merge là ArgoCD tự
   sync; riêng shed cần CI build xong image frontend-proxy mới có hiệu lực.
2. **Sau khi image mới chạy:** xóa ConfigMap tạm `frontend-proxy-shed` (đang mồ côi, không pod nào
   mount).
3. **Ngoài phạm vi #19 nhưng cần fix riêng:** product-reviews CrashLoop (protobuf gencode lệch
   runtime) — hiện làm app health Degraded và browse SLI dashboard đỏ.
4. Khi mang cấu hình sang prod: đo lại trần bằng EC2 qua NLB (Phase 6.5) trên môi trường prod trước
   khi công bố số, và pin Karpenter (§0.7).

## Bài học / bẫy (đừng lặp lại)

- **Điều khiển Locust qua web `/swarm` API mong manh** (405 nếu thiếu `Content-Type`; `user_classes` list bị urlencode sai → spawn 0 user; `--class-picker` treo không bind port). → Dùng **headless + LoadTestShape** như file này, KHÔNG web API.
- **CSV ở `/tmp` mất khi pod chết** → dùng emptyDir `/data` + `sleep` giữ pod (đã làm trong Job này).
- **Node ops chỉ đủ 1 Locust 500m.** Xóa generator cũ trước khi tạo mới, dùng Recreate/Job.
- **Giữa các lần đo phải đợi HPA co về min ≥5 phút** (scaleDown stabilization 300s), nếu không baseline gồm replica dư từ tải trước. `kubectl get hpa` hiển thị rep **stale** — đọc `deploy .spec.replicas` thật.
- **Admission policy dev** enforce `require-resources` + `deny-privilege-escalation` → pod phải có resources + securityContext đầy đủ.
- **frontend-proxy service port = 80** (sau PR #242, target 8080). Locust host = `http://frontend-proxy:80`.