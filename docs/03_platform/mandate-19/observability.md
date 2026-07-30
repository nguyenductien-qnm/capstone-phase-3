# Observability — Mandate-19 và hiện trạng cụm develop

Tài liệu này gom về một chỗ: hệ quan sát đang có gì, các ngưỡng và con số chuẩn đã đo được của
Mandate-19 để đối chiếu, câu lệnh PromQL dùng hằng ngày, và những lỗ hổng quan sát còn tồn tại.
Cập nhật 22/07/2026, sau khi PR #274 (sizing + HPA + shed) merge vào develop.

---

## 1. Hệ quan sát đang chạy

| Thành phần | Vị trí / cách truy cập | Ghi chú |
|---|---|---|
| Prometheus | ns `techx-develop`, port-forward `svc/prometheus` | retention **1 tuần** — số đo cũ hơn là mất, muốn giữ phải chụp/export |
| Grafana | port-forward `localhost:3000` | dashboard "Kubernetes Scaling - Pods & Nodes" là ảnh một-khung-hình cho loadtest |
| Jaeger | port-forward | trace lỗi từng service (mẫu dùng tốt: PR #276 Mandate-16) |
| otel-collector | mỗi service trỏ OTLP về đây | span metrics **không có label HTTP status** — không đếm được 429/500 qua Prometheus |
| Node ops | 1× t3.large, taint `dedicated=observability:NO_SCHEDULE` | toàn bộ stack observability + locust in-cluster nằm đây, tách khỏi 3 node app |

## 2. Ngưỡng chuẩn để đánh giá

| Ngưỡng | Giá trị | Dùng làm gì |
|---|---|---|
| SLO chính thức storefront | **p95 < 1s** | tính trần, cam kết khách hàng (`onboarding/SLO.md`) |
| Cảnh báo nội bộ | p95 < 200ms | lộ nút thắt sớm, KHÔNG phải cam kết |
| Success SLO | browse/cart non-5xx ≥ 99.5%, checkout ≥ 99% | 429 do shed là chủ động, không tính lỗi hệ |
| CPU throttle | > 5% ở tải đỉnh = limit đang bóp; < 2% = đủ | căn cứ quyết định nới limit |
| Requests sizing | pod chạy ~55–65% requests ở steady-state | dưới nhiều = over-request, trên 100% = under-request nguy hiểm |
| HPA target | CPU 70% | mọi HPA trong chart |

## 3. Con số chuẩn Mandate-19 (để đối chiếu khi nhìn dashboard)

Số liệu đầy đủ ở `loadtest/README.md` và `loadtest/EVIDENCE.md` (E1–E8).

| Con số | Giá trị | Nguồn |
|---|---|---|
| Trần user-facing (mixed, qua NLB) | **98 rps @ 200u**, gãy 280u | PHASE 6.5, đo từ EC2 ngoài cụm |
| Trần per-pod frontend (SLO <1s) | ~56 rps/pod; theo cảnh báo 200ms ~20 rps/pod | Phase 3 |
| Trần checkout sau tuning | ~76 rps (trước tuning ~27) | Checkout before/after |
| Baseline mạng qua NLB (1u, warm) | 16ms | PHASE 6.5 |
| Shed | browse bucket 80 rps/pod, homepage 100 rps/pod; checkout/cart không shed | envoy.tmpl.yaml |
| Node | 4× t3.large (3 app + 1 ops), không đổi trong mọi bài đo | ràng buộc #19 |
| HPA hiện hành | frontend 2/10; email, quote, shipping, payment 2/4; cart 2/6; checkout 2/5 | values develop |

## 4. PromQL dùng hằng ngày

Thay `$SVC` bằng tên service, ns cố định `techx-develop`.

CPU thực dùng mỗi pod (căn requests):

```promql
avg(sum by(pod)(rate(container_cpu_usage_seconds_total{namespace="techx-develop",pod=~"$SVC-.*",container!=""}[2m])))
```

Tỷ lệ CPU throttle (căn limits — trên 5% ở tải đỉnh là limit đang bóp):

```promql
sum(rate(container_cpu_cfs_throttled_periods_total{namespace="techx-develop",pod=~"$SVC-.*"}[2m]))
/ sum(rate(container_cpu_cfs_periods_total{namespace="techx-develop",pod=~"$SVC-.*"}[2m]))
```

RAM working set so với limit (đầu vào right-size RAM — mục 6.3 master plan, chưa làm):

```promql
max by(pod)(container_memory_working_set_bytes{namespace="techx-develop",pod=~"$SVC-.*",container!=""})
```

Pod nằm node nào (verify isolation — generator phải ở node ops):

```promql
kube_pod_info{namespace="techx-develop",pod=~"locust.*|load-generator.*"}
```

Replica thật khi loadtest — đọc từ deploy chứ đừng tin `kubectl get hpa` (status cache stale):

```bash
kubectl get deploy $SVC -n techx-develop -o jsonpath='{.spec.replicas}'
```

## 5. Snapshot cụm thực tế — 22/07/2026 08:50 UTC (idle, không loadtest)

Chụp bằng `kubectl top` đối chiếu spec deployment. Lưu ý đây là trạng thái **nhàn rỗi**
(locust-loadtest đã scale về 0, load-generator tắt) nên cột CPU chỉ nói lên mức nền; CPU dưới tải
lấy ở bảng chuẩn `loadtest/README.md`. Cột đáng đọc nhất ở đây là **RAM% limit** — RAM không giảm
theo tải như CPU, số idle đã phản ánh gần đúng working set thật.

| Service | Rep | CPU req/lim | CPU idle | RAM req/lim | RAM dùng | **RAM % limit** |
|---|---|---|---|---|---|---|
| **prometheus** | 1 | 250m/1 | 61m | 768Mi/1536Mi | **1399Mi** | 🔴 **91%** |
| opensearch (sts) | 1 | — | 6m | —/1100Mi | **943Mi** | 🔴 **86%** |
| **fraud-detection** | 1 | 50m/150m | 7m | 128Mi/300Mi | **246Mi** | 🔴 **82%** |
| **ad** | 1 | 50m/200m | 2m | 128Mi/300Mi | **235Mi** | 🟡 **78%** |
| accounting | 1 | 100m/200m | 5m | 128Mi/256Mi | 173Mi | 🟡 68% |
| payment | 2 | 80m/300m | 9m | 96Mi/256Mi | ~163Mi | 64% |
| shopping-copilot | 1 | 10m/100m | 4m | 32Mi/100Mi | 60Mi | 60% |
| email | 2 | 100m/400m | 1m | 64Mi/100Mi | ~53Mi | 54% |
| frontend | 2 | 100m/500m | 9–38m | 128Mi/250Mi | ~123Mi | 50% |
| flagd | 1 | 10m/100m | 2m | 32Mi/75Mi | 33Mi | 44% |
| cart | 2 | 60m/350m | 7m | 64Mi/160Mi | ~65Mi | 41% |
| frontend-proxy | 2 | 100m/200m | 4–9m | 48Mi/65Mi | ~25Mi | 38% |
| grafana (main) | 1 | 10m/50m | 7m | 96Mi/768Mi | 176Mi | 23% |
| product-reviews | 2 | 100m/500m | 10m | 128Mi/512Mi | ~104Mi | 21% |
| currency | 1 | 50m/250m | 1m | 16Mi/20Mi | 4Mi | 20% |
| checkout | 2 | 60m/350m | 2m | 64Mi/128Mi | ~21Mi | 16% |
| jaeger | 1 | 100m/500m | 3m | 640Mi/1Gi | 167Mi | 16% |
| quote | 2 | 50m/100m | 1m | 32Mi/128Mi | ~20Mi | 15% |
| llm | 1 | 50m/500m | 24m | 128Mi/512Mi | 71Mi | 14% |
| recommendation | 1 | 100m/200m | 6m | 128Mi/500Mi | 62Mi | 12% |
| product-catalog | 2 | 40m/200m | 2m | 32Mi/128Mi | ~14Mi | 11% |
| shipping | 2 | 50m/100m | 1m | 32Mi/96Mi | 3–11Mi | 11% |
| image-provider | 1 | 50m/100m | 1m | 32Mi/50Mi | 5Mi | 10% |

Node cùng thời điểm (allocatable mỗi node 1930m CPU / ~7080Mi RAM):

| Node | Vai trò | CPU | RAM |
|---|---|---|---|
| ip-10-60-11-81 | app | 618m (32%) | 3607Mi (50%) |
| ip-10-60-12-102 | app | 217m (11%) | 3226Mi (45%) |
| ip-10-60-12-251 | app | 121m (6%) | 3241Mi (45%) |
| ip-10-60-12-28 | ops (observability) | 149m (7%) | 4463Mi (63%) |

HPA cùng thời điểm: frontend 2/10; email, quote, shipping, payment, product-reviews 2/4;
cart, frontend-proxy, product-catalog 2/6; checkout 2/5; currency, recommendation 1/4.

**Đọc ra từ snapshot này:**

- **prometheus 91% limit (1399Mi/1536Mi)** — tệ hơn con số 83% đo trước đó, working set đang
  phình theo cardinality. **Không còn là rủi ro lý thuyết: đã OOM thật** — metadata run
  m16-after (PR #276) ghi nhận Prometheus `OOMKilled` exit 137 lúc **22/07 05:48:18Z** giữa
  stage 300 user, tạo lỗ hổng dữ liệu quan sát ngay trong cửa sổ evidence của họ. Right-size
  RAM prometheus là việc BẮT BUỘC trước vòng đo tới.
- **opensearch 86% (943Mi/1100Mi)** và **fraud-detection 82%**, **ad 78%** — cùng nhóm rủi ro.
  Cả bốn đều nằm ngoài hai luồng đã đo của Mandate-19 nên chưa từng được xét.
- Chiều ngược lại, jaeger xin 640Mi dùng 167Mi, recommendation limit 500Mi dùng 62Mi, llm limit
  512Mi dùng 71Mi, product-reviews limit 512Mi dùng ~104Mi — thừa 3–8 lần, là nguồn co lại để bù
  cho nhóm thiếu mà không tăng tổng RAM cụm.
- Việc treo: right-size RAM theo công thức mục 6.3 master plan (max
  `container_memory_working_set_bytes` qua chu kỳ tải + headroom ~30%) cho ít nhất 4 service
  rủi ro trên.
- **product-reviews CrashLoopBackOff** (protobuf gencode lệch runtime) làm browse SLI dashboard
  đỏ (~96.8%) — lỗi build có sẵn, ngoài phạm vi #19, đừng nhầm là hệ quả loadtest.

## 6. Kiểm kê các run load test trong retention (19–22/07) — phục vụ sizing Prometheus

Chi tiết máy-đọc-được (đủ metadata, infrastructure, evidence, missing_fields từng run) nằm ở
[`loadtest/loadtest-runs-inventory.yaml`](loadtest/loadtest-runs-inventory.yaml). Dưới đây là bản
tóm tắt để ghép cửa sổ thời gian với metrics Prometheus.

Điểm thuận lợi nhất: **Prometheus giữ nguyên một cấu hình suốt cửa sổ** (Deployment revision 1 từ
khi dựng ~19/07 03:30Z — image v3.11.3, 250m/1cpu, 768Mi/1536Mi, retention 7d, scrape 1m, PVC
20Gi) nên mọi run đều so được với nhau về phía Prometheus. Và vì cụm mới dựng 19/07, không run
nào rơi ngoài retention — nhưng **cửa sổ 21/07 bắt đầu mất từ 28/07**, cần correlate trong tuần này.

| Run | Start–End UTC | Users | Duration | Kết quả | Evidence |
|---|---|---|---|---|---|
| phase2-before-catalog | 21/07 02:35–02:51 | 40 | 960s | ✅ 0 fail | README + job yaml |
| phase2-after-catalog | 21/07 03:20–03:37 | 40 | 960s | ✅ 0 fail | README |
| phase3-perpod | 21/07 03:47–04:08 | 120 | 1240s | ✅ | README + job yaml |
| yc4-shed-demo | 21/07 07:44–~07:46 | 100 | 120s | ✅ | README |
| phase4-mixed-60u | 21/07 08:24–~08:34 | 60 | 600s | ✅ (fail 7.2% = reviews CrashLoop) | README + job yaml |
| checkout-before | 21/07 09:07–~09:28 | 60 | 1240s | ✅ 0 fail | README + job yaml |
| checkout-after-limits | 21/07 09:39–~10:00 | 60 | 1240s | ✅ | README |
| sizing-sau-shed | 21/07 10:11–? | ? | ? | ✅ | README |
| **flashsale-200u-max10** | 21/07 11:57:42–12:12:41 | 200 | 900s | ✅ (45 fail, 0.04%) | **log giây-chính-xác trong repo** |
| flood-tuned-yc4 | 21/07, sau 13:00Z | 100 | ? | ✅ | flood-test-tuned-system.md |
| shed-verification-probes | 22/07 sáng | probe | — | ✅ | shed-verification-clusterip-vs-podip.md |
| m16-before-100u (PR #276) | 22/07 03:09:47–03:25:07 | 100 | 15m20s | ❌ fail 71.9% | PR #276 metadata + CSV |
| m16-before-150u/300u | 22/07 03:25–05:31 (khoảng) | 150/300 | ? | ? | PR #276 (chưa đọc metadata) |
| m16-after-stepped | 22/07 05:31:38–05:56:38 | ? | ~25m | ✅ | PR #276, tên file screenshot |
| actor-locust-loadtest | 19–21/07 lặp nhiều đợt | 100 | 15m/đợt | uncontrolled | README lịch sử (git 4204549) |

**Đọc bảng này khi correlate:**

- Run có timestamp chính xác để ghép thẳng: phase2 before/after, phase3, phase4, checkout
  before/after, yc4-shed-demo, flashsale (tốt nhất), m16-before-100u, m16-after-stepped.
- Run thiếu giờ nhưng dựng lại được bằng chính Prometheus: actor-locust-loadtest và
  flood-tuned-yc4 — query `kube_pod_info{pod=~"locust-loadtest.*|load-generator.*"}` và rate span
  `GET /` để khoanh cửa sổ.
- Phía app có 4 thế hệ cấu hình, đừng so chéo: (1) trước 21/07 03:05Z — frontend 200m; (2)
  03:05Z→~09:30Z — frontend 500m, chain cũ; (3) ~09:30Z 21/07→22/07 05:08Z — hệ patch-tay (limit
  chain, HPA checkout-path, max10, shed CM), không có trong git lúc đo; (4) sau 05:08Z 22/07 —
  PR #274 merge, cấu hình chính thức. Lưu ý cặp m16 before/after vắt qua mốc (4) — after của họ
  chạy trên hệ đã có sizing M19.
- Nguồn nhiễu: actor locust-loadtest (đẩy mọi HPA lên max khi hoạt động, hiện đã scale 0) và
  product-reviews CrashLoop (fail 100% flow reviews, không liên quan tải).

## 7. Lỗ hổng quan sát còn tồn tại

1. **Shed không có metric.** Envoy admin (9901) tắt, stats không scrape vào Prometheus → không
   thấy counter `rl_browse.rate_limited` / `rl_home.rate_limited`, không vẽ được tỷ lệ 429 trên
   Grafana. Hiện chỉ verify được bằng probe HTTP trực tiếp (bắn thẳng pod IP — xem
   `loadtest/shed-verification-clusterip-vs-podip.md`). Muốn vá: bật admin hoặc thêm envoy
   stats sink vào otel-collector.
2. **Span metric không có HTTP status** → không phân biệt 429 (shed chủ động) với 5xx (lỗi thật)
   qua Prometheus. Đếm lỗi phải dựa CSV locust hoặc log.
3. **Retention Prometheus 1 tuần** → bằng chứng before/after phải chụp/export ngay sau khi đo,
   không để dành được (bài học E1: BEFORE của frontend hết tái tạo vì limit đã đổi).
4. **Warm-up làm méo run đầu** — HPA scale trễ cộng SSR JIT khiến run đầu chậm giả tạo (p95 từng
   lệch 1300ms so với 430ms cùng kịch bản). Quy tắc: bỏ run đầu, lấy số từ run thứ hai.
5. **Bucket shed là per-pod** → tổng ngưỡng hiệu dụng = bucket × số pod proxy, thay đổi theo HPA.
   Nhìn số 429 phải nhớ nhân số pod; và probe qua ClusterIP sẽ không thấy shed nếu rps tức thời
   mỗi pod chưa vượt bucket.
