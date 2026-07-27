# Verify V1–V8 trên cụm EKS trước khi sửa rule

**Ngày đo:** 2026-07-27 · **Người đo:** Thanh Pham Huu Tien (phamthanh.forwork@gmail.com)
**Cụm:** `ecommerce-dev-eks` (us-east-1), namespace `techx-tf1`, Prometheus qua port-forward
**Cửa sổ backtest:** 12h, step 30s (đúng nhịp poll của detector), cooldown 600s

> **Vì sao có tài liệu này.** Rule `kafka-consumer-lag-high` nằm câm hàng tuần vì tên metric
> được **đoán** chứ không đo (`report/mandate15-eks/report.md` §4.4). PromQL sai tên trả
> chuỗi rỗng chứ không ném lỗi. Đợt này mọi query mới đều phải chạy thật trước khi viết vào
> `rules.yaml`. Không con số nào dưới đây là ước lượng.

---

## Tóm tắt cái đáng giá nhất

| # | Phát hiện | Hệ quả |
|---|---|---|
| V1 | `traces_span_metrics_*` phủ **17 service**, `rpc_server_duration_*` chỉ 3 | Vá được điểm mù coverage **không cần đụng app** |
| V2 | `payment` là `SPAN_KIND_CONSUMER`, **không phải** `SERVER` | Lọc `SERVER` đơn thuần sẽ **bỏ sót đúng `payment`** |
| V3 | spanmetrics **không hết hạn chuỗi** (53/84 pod đã chết vẫn còn series) | `absent()` **không bao giờ** kêu → bỏ khỏi thiết kế |
| V4 | Bỏ health-check thì `checkout` vượt 0.05 suốt **4.9%** thời gian bình thường | Ngưỡng phải nâng 0.05 → **0.10** |
| V6 | `kafka_consumer_group_lag` **không tồn tại**; bản thật không có nhãn `group`, và `namespace` cũng sai tên | Rule kafka có **3 lỗi chồng nhau**, sửa tên thôi vẫn rỗng |
| **V7** | **9/11 metric rule đang trả chuỗi rỗng.** Nhóm burn-rate — lõi neo vào SLO — **chưa từng có khả năng kêu** | Lớn hơn nhiều so với những gì MANDATE-15 ghi nhận |

---

## V1 — spanmetrics phủ bao nhiêu service

```promql
count(count by (service_name) (traces_span_metrics_calls_total))   # -> 17
```

| Nguồn metric | Số service |
|---|---|
| `rpc_server_duration_milliseconds` (rule đang dùng) | **3** — ad, checkout, product-catalog |
| `traces_span_metrics_calls_total` (spanmetrics) | **17** |

17 service: accounting, ad, cart, checkout, currency, fraud-detection, frontend, frontend-proxy,
image-provider, load-generator, payment, product-catalog, product-reviews, quote, recommendation,
shipping, shopping-copilot.

**`payment` có mặt với 39 chuỗi** — chính là service mà hôm 26/07 detector mù hoàn toàn.

spanmetrics là connector của collector (`values.yaml:2255`, `spanmetrics: {}`), sinh metric
**từ trace**, nên phủ mọi service có span mà không cần service tự xuất metric.

## V2 — nhãn thật

Nhãn có trên `traces_span_metrics_calls_total`: `service_name`, `span_name`, `span_kind`,
`status_code`, `service_namespace`, `k8s_pod_name`, `k8s_deployment_name`, `k8s_namespace_name`,
`k8s_node_name`, `service_instance_id`, `service_version`, `host_name`, `instance`, `job`.

**Phân bố `span_kind` — đây là chỗ suýt sai:**

| span_kind | Service |
|---|---|
| `SPAN_KIND_SERVER` | 13: ad, cart, checkout, currency, frontend, frontend-proxy, image-provider, product-catalog, product-reviews, quote, recommendation, shipping, shopping-copilot |
| `SPAN_KIND_CONSUMER` | 2: **accounting, payment** |
| `SPAN_KIND_PRODUCER` | 1: payment |

`payment` làm việc qua Kafka (`process domain.checkout.orders`), **không có span SERVER nào**.
Kế hoạch ban đầu lọc `span_kind="SPAN_KIND_SERVER"` sẽ bỏ sót đúng service mà cả đợt này nhắm
vào. Bộ lọc đúng là **`SPAN_KIND_SERVER|SPAN_KIND_CONSUMER`** = 15 service ("việc mà service
được yêu cầu làm", cả đồng bộ lẫn bất đồng bộ). `CLIENT`/`PRODUCER` là lời gọi đi ra, cố ý loại.

Còn mù: `fraud-detection` và `load-generator` (chỉ có span CLIENT).

## V3 — spanmetrics có dọn chuỗi của service chết không? **KHÔNG**

Cấu hình trên cụm là `spanmetrics: {}` — mặc định, không đặt `metrics_expiration`.
Kiểm chứng bằng thực nghiệm chứ không tin tài liệu:

| | |
|---|---|
| Pod xuất hiện trong metric | 84 |
| Pod đang sống | 51 |
| **Pod đã chết mà chuỗi vẫn còn** | **53** |

**Hệ quả đảo ngược thiết kế:** service chết thì chuỗi bị **đóng băng** ở giá trị cũ chứ không
biến mất. Nên:

- `absent(...)` **không bao giờ** kêu → **bỏ 2 rule `absent()` khỏi kế hoạch**
- `rate()` trên counter đóng băng = 0 → **rule tỉ lệ là tuyến duy nhất**

## V4 — tỉ lệ lỗi khi bỏ health-check

Phân bố 12h, `status_code="STATUS_CODE_ERROR"`, loại `grpc.health.v1.Health/Check`:

| service | p50 | p95 | p99 | max | % thời gian > 0.05 |
|---|---|---|---|---|---|
| **checkout** | 0.0153 | **0.0500** | 0.5714 | 1.0000 | **4.9%** |
| frontend-proxy | 0.0030 | 0.0074 | 0.1365 | 0.3092 | 1.2% |
| frontend | 0.0029 | 0.0071 | 0.0996 | 0.2312 | 1.2% |
| product-catalog | 0.0000 | 0.0025 | 0.0044 | 0.0051 | 0.0% |
| cart | 0.0000 | 0.0006 | 0.0018 | 0.0024 | 0.0% |
| shipping | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0% |

Ngưỡng 0.05 hiện tại nằm **đúng p95 của checkout** — vùng sinh nhiễu. Backtest số báo động/12h:

| ngưỡng | 0.05 | **0.10** | 0.15 | 0.20 | 0.30 | 0.50 |
|---|---|---|---|---|---|---|
| tổng alert / 12h | 14 | **3** | 3 | 3 | 2 | 1 |

**Chọn 0.10.** Điểm gãy rõ (14 → 3); lên 0.15/0.20 không giảm thêm. Vẫn cách xa sự cố thật:
bỏ health-check ra thì mẫu số nhỏ đi ~9 lần nên một sự cố thật đẩy tỉ lệ lên gần 1.0, chứ không
bò lên 0.109–0.18 như số đo 26/07.

## V5 — sàn thông lượng từng service (rate[1h] thấp nhất trong 12h, req/s)

| service | sàn | | service | sàn |
|---|---|---|---|---|
| **payment** | **0.06484** | | shopping-copilot | 0.29971 |
| quote | 0.06614 | | checkout | 0.66942 |
| shipping | 0.06659 | | product-reviews | 0.68540 |
| ad | 0.09548 | | cart | 0.93719 |
| recommendation | 0.09802 | | product-catalog | 1.10480 |
| image-provider | 0.10000 | | frontend-proxy | 1.36878 |
| accounting | 0.13390 | | frontend | 3.81883 |
| currency | 0.18728 | | | |

Cổng hoạt động 0.05 như kế hoạch chỉ cho `payment` biên 1.3× — quá mỏng. **Chọn 0.02**
(biên 3.2×). Hiện không service nào nằm dưới 0.05 nên cổng chưa loại ai; nó là lưới đỡ cho
đêm vắng khách.

## V6 — rule kafka có **ba** lỗi chồng nhau, không phải một

| | Đo được |
|---|---|
| `kafka_consumer_group_lag` (rule đang dùng) | **RỖNG — không tồn tại** |
| `kafka_consumer_records_lag` | 1 chuỗi, `service_name=fraud-detection` |
| Nhãn thật | `client_id`, `partition`, `topic`, `service_name`, `k8s_namespace_name`, … |

1. Tên metric sai
2. `max by (group)` — **không hề có nhãn `group`** (đó là nhãn của kafkametrics receiver, mà
   receiver đó trỏ vào `kafka:9092` không tồn tại vì chart đặt `kafka.enabled=false`)
3. Bộ lọc `{namespace="techx-tf1"}` — nhãn thật là `k8s_namespace_name`

**Sửa mỗi tên metric vẫn ra chuỗi rỗng.** Và ngay cả khi sửa cả ba thì chỉ phủ được
`fraud-detection`: MSK tắt `open_monitoring` (`terraform/modules/msk/main.tf:98-106`) nên
`payment`/`email`/`shipping` không quan sát được lag → cần ticket hạ tầng cho CDO.

## V7 — rule nào đang câm (chạy `detector.py --once --dry-run` trên Prometheus thật)

**9 trong 11 metric rule trả về 0 chuỗi.** Chỉ `latency-p95-high` và `grpc-error-rate-high`
có dữ liệu.

| Rule | Rỗng vì | Nguyên nhân gốc đo được |
|---|---|---|
| `error-budget-burn-fast-standard` | **MÙ** | `http_server_..._count{service_namespace="techx-corp"}` chỉ có **`cart`**; và `http_response_status_code=~"5.."` **rỗng toàn cụm** → tử số không bao giờ có dữ liệu |
| `error-budget-burn-slow-standard` | **MÙ** | như trên |
| `error-budget-burn-fast-checkout` | **MÙ** | `{service_name="checkout"}` trên metric đó **rỗng** — checkout không xuất `http_server_request_duration_seconds` |
| `error-budget-burn-slow-checkout` | **MÙ** | như trên |
| `error-budget-burn-fast` (DRAFT) | **MÙ** | như trên |
| `bedrock-cost-high` | **MÙ** | `bedrock_cost_usd_total` **không tồn tại** |
| `genai-latency-high` | **MÙ** | lọc `service_name="product-reviews"`, nhưng chỉ `cart`/`jaeger`/`otelcol-contrib` xuất metric đó |
| `memory-saturation-high` (DRAFT) | **MÙ** | `container_memory_working_set_bytes{namespace=...}` có 156 chuỗi nhưng phép join với `kube_pod_container_resource_limits` không ra kết quả — cần điều tra riêng |
| `kafka-consumer-lag-high` (DRAFT) | **MÙ** | xem V6 |

> **Đây là phát hiện lớn nhất của đợt verify.** Bốn rule burn-rate là phần **neo vào SLO hợp
> đồng** — thứ được trình bày như lõi của hệ phát hiện. Đo ra thì chúng **chưa từng có khả
> năng kêu**, và không ai biết vì detector nuốt im lặng chuỗi rỗng. Chính cơ chế tự-tố-cáo
> vừa viết là thứ phát hiện ra điều này ngay lần chạy đầu tiên.

## V8 — chi phí query

| | |
|---|---|
| Cardinality `traces_span_metrics_calls_total` | 1007 chuỗi |
| Query `service-traffic-collapse` (4 sub-query, 2 cửa sổ `[1h]`) | 0.71 / 0.75 / 0.77 s |
| Query error-rate mới | 0.73 / 1.17 s |

11 metric rule × ~0.8s ≈ 9s mỗi chu kỳ, nằm gọn trong poll 30s. **Chưa cần recording rule.**

---

## Backtest rule `service-traffic-collapse`

Mô phỏng lại đúng `eval_metric_rule` (op=lt, tầng tĩnh, `dynamic_enabled: false`), cooldown
600s theo (rule, service). Hai cách định nghĩa "sụt thông lượng":

- **A — tự thân:** `rate_ngắn(svc) / rate1h(svc)`
- **B — so bạn:** chia thêm cho `rate_ngắn(tổng) / rate1h(tổng)`

| cửa sổ ngắn | ngưỡng | A tự thân | **B so bạn** |
|---|---|---|---|
| 5m | 0.20 | 25 | 9 |
| 5m | 0.10 | 7 | 7 |
| **15m** | **0.20** | 5 | **2** |
| 15m | 0.10 | 2 | 2 |
| 30m | 0.20 | 2 | 2 |

**Chọn: so bạn, cửa sổ `[15m]`, ngưỡng 0.20, cổng 0.02 → 2 báo động/12h** (từ 25, giảm 92%).
30m không cải thiện thêm nên 15m là điểm gãy.

**Vì sao phải "so bạn".** Cách tự thân báo động **đồng loạt 8 service cùng lúc** lúc 06:17,
đổ lỗi cho tất cả trong khi nguyên nhân là **một nguồn tải ở thượng nguồn thay đổi**: đo được
load-generator đi từ 43.9 → 6.9 span/s và tổng hệ từ 236.6 → 54.7 span/s. `sum(up)` giữ nguyên
**23 suốt 12h** nên đây không phải hố scrape — traffic thật sự tụt 6 lần. Cách so bạn triệt
tiêu đúng loại này: `frontend` 0.191→0.828, `frontend-proxy` 0.149→0.708,
`recommendation` 0.160→0.598, `ad` 0.130→0.483.

**2 báo động còn lại đều của `accounting`** — consumer Kafka theo lô, dao động 0.062–5.423 req/s
trong 12h (87 lần). Chấp nhận: 0.17 báo động/giờ, so với mốc đã đo **3.2/giờ** ngày 26/07.

**Giá phải trả, nói rõ:** cửa sổ `[15m]` nghĩa là service chết hẳn mất ~12–15 phút mới bị bắt.
Chậm hơn 380s của rule error-rate. Nhưng hiện tại loại sự cố này **không bao giờ** bị bắt, nên
15 phút vẫn là cải thiện tuyệt đối. Cách sửa đúng là trường `for:` (đòi điều kiện kéo dài) —
detector **không có** trường đó; đây là hạn chế đã biết, để ticket riêng.

## Câu truy vấn cuối cùng đã chạy thật

```promql
(
  sum by (service_name) (rate(traces_span_metrics_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[15m]))
  / clamp_min(sum by (service_name) (rate(traces_span_metrics_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[1h])), 0.001)
)
/ scalar(clamp_min(
    sum(rate(traces_span_metrics_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[15m]))
    / clamp_min(sum(rate(traces_span_metrics_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[1h])), 0.001), 0.001))
and (sum by (service_name) (rate(traces_span_metrics_calls_total{span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"}[1h])) > 0.02)
```

Trả về **15 chuỗi, chỉ mang nhãn `service_name`** — đúng điều kiện để `svc` lấy được tên
service thật (dedup key, cooldown, nhóm alert, chấm điểm `incident_replay` đều đúng). Giá trị
lúc đo: 0.90–0.92 cho các service vắng nhất, cách xa ngưỡng 0.20.

> Lưu ý `clamp_min` chỉ nhận instant vector, không nhận scalar — bản viết đầu bị
> `parse error: expected type instant vector in call to function "clamp_min", got scalar`.
> Đây đúng là loại lỗi `validate_rules.py` bắt được ở CI.

---

## Việc phát sinh, chưa làm trong đợt này

1. **4 rule burn-rate + `error-budget-burn-fast` đều mù** — cần viết lại trên nền spanmetrics
   hoặc bỏ. Lớn hơn phạm vi PR hiện tại, cần ticket riêng.
2. `bedrock-cost-high` và `genai-latency-high` mù — metric không tồn tại / lọc sai service.
3. `memory-saturation-high` mù — phép join với `kube_pod_container_resource_limits` cần điều tra.
4. MSK `open_monitoring` tắt → lag của payment/email/shipping không quan sát được (ticket CDO).
5. Detector thiếu trường `for:` (đòi điều kiện kéo dài N chu kỳ).
6. `fraud-detection` và `load-generator` chỉ có span CLIENT → nằm ngoài rule collapse.
