# Business Flows for Observability On-Call

> Vai trò của bạn: **Observability Engineer (On-Call Captain)**.
>
> Bạn không owner business logic của từng service. Bạn owner khả năng nhìn thấy sức khỏe hệ thống end-to-end: metrics, logs, traces, alerts, dashboards, runbooks và điều phối incident.
>
> Khi phải chọn ưu tiên, **bảo vệ checkout trước** vì đây là luồng revenue-critical.

---

## 1. Tổng Quan Ưu Tiên

| Priority | Luồng | Lý do |
|---|---|---|
| P0 | Checkout | Tạo doanh thu trực tiếp, lỗi là mất đơn hàng |
| P1 | Cart | Cart lỗi sẽ làm checkout không thể tiếp tục |
| P1 | Post-checkout async | Ảnh hưởng accounting, fraud check, xử lý sau đơn hàng |
| P2 | Browse | Ảnh hưởng trải nghiệm và conversion đầu phễu |
| P2 | Product detail + AI review | Ảnh hưởng quyết định mua hàng, nhưng LLM nên là best-effort |

---

## 2. Service Catalog: Mỗi Service Có Tác Dụng Gì?

| Service | Tác dụng chính | Nằm trong luồng nào | Mức độ critical | Observability cần nhìn |
|---|---|---|---|---|
| `frontend` | Giao diện người dùng, nhận thao tác browse, cart, checkout rồi gọi các backend service | Tất cả luồng | Critical | Request rate, 5xx, p95 latency, trace từ frontend sang backend |
| `product-catalog` | Cung cấp danh sách sản phẩm, chi tiết sản phẩm, giá, trạng thái sản phẩm/tồn kho | Browse, Checkout | Critical | Latency, 5xx, lỗi validate sản phẩm, ảnh hưởng checkout |
| `recommendation` | Trả về gợi ý sản phẩm cá nhân hóa hoặc sản phẩm liên quan | Browse | Non-critical | Latency, error rate, fallback rate |
| `ad` | Trả về quảng cáo/campaign để hiển thị trên trang browse | Browse | Non-critical | Latency, error rate, không được làm hỏng browse |
| `product-reviews` | Lấy review sản phẩm và gọi LLM để tạo tóm tắt/AI review | Product detail + AI review | Important | DB latency, LLM timeout, fallback rate |
| `postgresql` | Database lưu dữ liệu review hoặc dữ liệu quan hệ liên quan | Product detail + AI review | Important/Critical tùy dữ liệu | Connection pool, query latency, connection timeout, statement timeout |
| `llm` | Tạo tóm tắt review hoặc nội dung AI hỗ trợ user | Product detail + AI review | Best-effort | Timeout, latency, retry, fallback |
| `cart` | Quản lý giỏ hàng: thêm, xóa, sửa, lấy danh sách item trong cart | Cart, Checkout | Critical | Cart success rate, 5xx, latency, lỗi gọi Valkey |
| `valkey-cart` | In-memory store lưu trạng thái giỏ hàng/session cart | Cart, Checkout | Critical | Memory, eviction, connection error, latency |
| `checkout` | Điều phối quá trình đặt hàng: lấy cart, validate sản phẩm, tính tiền, shipping, payment, email, Kafka event | Checkout | P0 Critical | Checkout success rate, error rate, p95/p99 latency, dependency latency |
| `currency` | Xử lý tiền tệ, tỷ giá, format hoặc conversion giá | Checkout | Important | Latency, lỗi conversion, timeout |
| `shipping/quote` | Tính phí giao hàng, thời gian giao dự kiến hoặc lựa chọn shipping | Checkout | Important | Latency, quote failure, timeout |
| `payment` | Xử lý thanh toán, authorize/capture payment | Checkout | Critical | Payment error rate, latency, timeout, decline/error phân biệt rõ |
| `email` | Gửi email xác nhận đơn hàng hoặc thông báo sau checkout | Checkout | Best-effort/async candidate | Send failure, queue/retry, không nên làm fail checkout nếu order đã thành công |
| `Kafka` | Message broker nhận order event sau checkout để các service downstream xử lý async | Checkout, Post-checkout async | Important | Publish failure, broker health, consumer lag |
| `accounting` | Consumer đọc order event để ghi nhận doanh thu, hóa đơn, nghiệp vụ kế toán | Post-checkout async | Important | Consumer lag, processing error, pod health |
| `fraud-detection` | Consumer đọc order event để kiểm tra gian lận/rủi ro đơn hàng | Post-checkout async | Important | Consumer lag, processing error, decision latency |

### Cách hiểu nhanh theo vai trò Observability

- Service nào nằm trên đường checkout thì phải observe kỹ hơn, vì ảnh hưởng trực tiếp doanh thu.
- Service nào là best-effort như `llm`, `recommendation`, `ad`, `email` thì lỗi của nó không nên kéo sập luồng chính.
- Với service critical, bạn cần dashboard + alert + trace/log query rõ ràng.
- Với service async như `accounting` và `fraud-detection`, dấu hiệu quan trọng nhất thường là **consumer lag**, **processing error**, và **consumer down**.

---

## 3. Browse Flow

### Luồng hoạt động

```text
User mở trang / browse sản phẩm
|
v
frontend
|
+-- gọi product-catalog để lấy danh sách sản phẩm
+-- gọi recommendation để lấy gợi ý sản phẩm
+-- gọi ad để lấy quảng cáo / campaign
|
v
frontend render trang browse cho user
```

### Các service trong luồng này làm gì?

- `frontend`: nhận request từ user và render trang browse.
- `product-catalog`: trả danh sách sản phẩm. Đây là dependency quan trọng nhất của browse.
- `recommendation`: trả gợi ý sản phẩm. Nếu lỗi, frontend vẫn nên hiển thị được danh sách sản phẩm.
- `ad`: trả quảng cáo/campaign. Nếu lỗi, không nên làm hỏng trang browse.

### Diễn giải

Browse là luồng người dùng dùng để xem danh sách sản phẩm. Luồng này thường có nhiều request, ảnh hưởng trực tiếp đến trải nghiệm đầu vào và khả năng user đi tiếp đến product detail/cart.

`recommendation` và `ad` nên được xem là non-critical hơn `product-catalog`. Nếu recommendation/ad chậm hoặc lỗi, frontend nên degrade gracefully thay vì làm hỏng cả trang browse.

### Observability cần theo dõi

| Tín hiệu | Cần xem |
|---|---|
| Latency | p95/p99 của frontend và product-catalog |
| Error rate | 5xx của frontend, product-catalog, recommendation, ad |
| Saturation | CPU/memory, pod restart, throttling |
| Dependency health | recommendation/ad có làm chậm browse không |

### Alert gợi ý

- `BrowseHighLatency`: p95 latency > 1s trong 5 phút.
- `ProductCatalogHighErrorRate`: product-catalog 5xx tăng cao.
- `RecommendationDegraded`: recommendation lỗi nhiều nhưng chỉ P2 nếu browse vẫn render được.

### Khi incident

1. Xem dashboard browse latency/error.
2. Trace từ `frontend` sang `product-catalog`, `recommendation`, `ad`.
3. Nếu chỉ `recommendation/ad` lỗi, đề xuất fallback/degrade.
4. Nếu `product-catalog` lỗi, escalate vì browse và checkout đều có thể bị ảnh hưởng.

---

## 4. Product Detail + AI Review Flow

### Luồng hoạt động

```text
User mở trang chi tiết sản phẩm
|
v
frontend
|
v
product-reviews
|
+-- gọi postgresql để lấy review gốc
+-- gọi llm để tạo tóm tắt / AI review
|
v
frontend hiển thị product detail + review
```

### Các service trong luồng này làm gì?

- `frontend`: hiển thị trang chi tiết sản phẩm và vùng review.
- `product-reviews`: gom dữ liệu review, gọi database, gọi LLM nếu cần.
- `postgresql`: lưu review gốc hoặc dữ liệu liên quan.
- `llm`: tạo tóm tắt/AI review để hỗ trợ user đọc nhanh.

### Diễn giải

Luồng này giúp user đọc chi tiết sản phẩm và review. `postgresql` là dependency quan trọng vì chứa dữ liệu review. `llm` là best-effort: nếu LLM chậm hoặc lỗi, không nên làm hỏng toàn bộ trang.

### Observability cần theo dõi

| Tín hiệu | Cần xem |
|---|---|
| DB latency | query duration, connection pool usage |
| DB errors | connection timeout, statement timeout |
| LLM latency | timeout, p95/p99, retry count |
| Fallback rate | tỷ lệ hiển thị "tóm tắt chưa có" |

### Alert gợi ý

- `ProductReviewsDbErrorRateHigh`: lỗi DB tăng cao.
- `ProductReviewsDbLatencyHigh`: query latency cao.
- `LlmTimeoutHigh`: LLM timeout tăng, severity cần thấp hơn checkout.

### Khi incident

1. Xác định lỗi nằm ở `postgresql` hay `llm`.
2. Nếu `llm` lỗi, ưu tiên fallback, không để ảnh hưởng checkout.
3. Nếu DB lỗi, thông báo Reliability Eng #3 vì liên quan DB resilience.
4. Dùng trace để chứng minh dependency nào gây chậm.

---

## 5. Cart Flow

### Luồng hoạt động

```text
User thêm sản phẩm vào giỏ hàng / xem giỏ hàng
|
v
frontend
|
v
cart service
|
v
valkey-cart
|
v
frontend hiển thị giỏ hàng
```

### Các service trong luồng này làm gì?

- `frontend`: nhận thao tác thêm/xóa/sửa cart từ user.
- `cart`: xử lý nghiệp vụ giỏ hàng và gọi storage.
- `valkey-cart`: lưu trạng thái giỏ hàng nhanh trong memory.

### Diễn giải

Cart là luồng gần với checkout. Nếu cart lỗi, user không thể checkout được. `valkey-cart` là dependency quan trọng vì lưu trạng thái giỏ hàng.

### Observability cần theo dõi

| Tín hiệu | Cần xem |
|---|---|
| Cart success rate | add/update/remove/get cart thành công |
| Valkey health | connection errors, latency, memory, eviction |
| Pod health | cart pod restart, readiness fail |
| Checkout impact | checkout gọi cart có bị lỗi không |

### Alert gợi ý

- `CartHighErrorRate`: cart 5xx tăng cao.
- `ValkeyCartUnavailable`: cart không kết nối được Valkey.
- `CartLatencyHigh`: cart p95 latency vượt ngưỡng.

### Khi incident

1. Kiểm tra cart service error rate.
2. Kiểm tra `valkey-cart` latency/error/memory.
3. Trace từ `frontend -> cart -> valkey-cart`.
4. Nếu ảnh hưởng checkout, nâng severity lên P0/P1.

---

## 6. Checkout Flow

### Luồng hoạt động

```text
User bấm checkout
|
v
frontend
|
v
checkout service
|
+-- gọi cart để lấy giỏ hàng
+-- gọi product-catalog để kiểm tra sản phẩm/giá/tồn kho
+-- gọi currency để xử lý tiền tệ
+-- gọi shipping/quote để tính phí giao hàng
+-- gọi payment để thanh toán
+-- gọi email để gửi xác nhận
+-- publish order event vào Kafka
|
v
Trả kết quả đơn hàng cho user
```

### Các service trong luồng này làm gì?

- `frontend`: gửi yêu cầu checkout khi user bấm đặt hàng/thanh toán.
- `checkout`: service điều phối trung tâm của luồng checkout.
- `cart`: trả dữ liệu giỏ hàng hiện tại.
- `product-catalog`: kiểm tra sản phẩm còn hợp lệ không, giá/tồn kho có đúng không.
- `currency`: xử lý tiền tệ hoặc quy đổi giá.
- `shipping/quote`: tính phí giao hàng.
- `payment`: xử lý thanh toán.
- `email`: gửi email xác nhận đơn hàng.
- `Kafka`: nhận order event để các service downstream xử lý sau checkout.

### Tóm tắt 1 dòng

`checkout` gọi `cart`, `product-catalog`, `currency`, `shipping/quote`, `payment`, `email`, rồi publish sự kiện đơn hàng lên `Kafka`.

### Diễn giải

Checkout là luồng revenue-critical. Đây là luồng cần được bảo vệ đầu tiên khi có sự cố, vì lỗi checkout có nghĩa là user không tạo được đơn hàng.

Trong checkout, không phải dependency nào cũng có cùng mức độ critical:

| Dependency | Mức độ | Ghi chú |
|---|---|---|
| cart | Critical | Không có giỏ hàng thì không checkout được |
| product-catalog | Critical | Cần validate sản phẩm/giá/tồn kho |
| payment | Critical | Thanh toán là core của checkout |
| currency | Important | Cần đúng tiền tệ/giá |
| shipping/quote | Important | Cần phí vận chuyển |
| email | Best-effort/async candidate | Lỗi email không nên làm mất đơn hàng nếu order/payment đã thành công |
| Kafka publish | Important | Cần event cho accounting/fraud, cần theo dõi retry/failure |

### Observability cần theo dõi

| Tín hiệu | Cần xem |
|---|---|
| Checkout success rate | SLO >= 99% |
| Checkout error rate | 5xx, business failure, payment failure |
| Checkout latency | p95/p99 end-to-end |
| Dependency latency | cart, catalog, currency, shipping, payment, email |
| Kafka publish status | publish success/failure/retry |
| Saturation | checkout pod CPU/memory, restart, throttling |

### Alert gợi ý

- `CheckoutHighErrorRate`: checkout error rate > 1% trong 2 phút.
- `CheckoutHighLatency`: checkout p95/p99 latency vượt ngưỡng.
- `PaymentDependencyErrorHigh`: lỗi payment tăng cao.
- `CheckoutKafkaPublishFailure`: publish order event vào Kafka thất bại.
- `CheckoutPodsNotReady`: checkout không đủ replica sẵn sàng.

### Khi incident

1. Xác nhận user impact: checkout có đang fail không, success rate còn bao nhiêu.
2. Mở trace mẫu: `frontend -> checkout -> dependencies`.
3. Tìm dependency nào làm chậm/lỗi nhiều nhất.
4. Nếu checkout lỗi do dependency best-effort như email, đề xuất fallback/async.
5. Nếu lỗi ở payment/cart/product-catalog, escalate ngay cho owner liên quan.
6. Nếu incident > 15 phút chưa resolve, escalate Tech Lead.
7. Sau incident, cập nhật runbook và alert threshold nếu cần.

---

## 7. Post-Checkout Async Flow

### Luồng hoạt động

```text
checkout publish order event
|
v
Kafka
|
+-- accounting consumer đọc event để ghi nhận doanh thu / hóa đơn
+-- fraud-detection consumer đọc event để kiểm tra gian lận
|
v
Xử lý hậu checkout
```

### Các service trong luồng này làm gì?

- `Kafka`: giữ order event sau checkout và phân phối cho consumer.
- `accounting`: đọc event để ghi nhận doanh thu, hóa đơn, nghiệp vụ kế toán.
- `fraud-detection`: đọc event để kiểm tra gian lận hoặc đánh dấu đơn hàng rủi ro.

### Diễn giải

Đây là luồng bất đồng bộ sau checkout. User có thể đã nhận kết quả checkout, nhưng hệ thống vẫn cần accounting và fraud-detection xử lý order event.

Owner chính về Kafka resilience trong team là **Reliability Engineer #3**. Vai trò của Observability Engineer là bảo đảm nhìn thấy consumer lag, consumer down, processing error và khả năng recover sau restart.

### Observability cần theo dõi

| Tín hiệu | Cần xem |
|---|---|
| Kafka consumer lag | Lag theo consumer group accounting/fraud-detection |
| Consumer health | pod ready, restart, crashloop |
| Processing rate | events/sec đọc và xử lý |
| Processing errors | lỗi parse event, lỗi ghi DB, lỗi fraud check |
| Retry/DLQ | retry tăng, dead-letter queue nếu có |

### Alert gợi ý

- `KafkaConsumerLagHigh`: consumer lag > 1000 trong 10 phút.
- `AccountingConsumerDown`: accounting consumer không có pod ready.
- `FraudDetectionConsumerDown`: fraud-detection consumer không có pod ready.
- `KafkaProcessingErrorHigh`: processing error tăng cao.

### Khi incident

1. Xem lag theo từng consumer group.
2. Xác định consumer nào chậm: `accounting` hay `fraud-detection`.
3. Kiểm tra consumer pod restart/crashloop.
4. Kiểm tra log lỗi xử lý event.
5. Gọi Reliability Eng #3 nếu cần fix Kafka/consumer resilience.
6. Báo cáo PM nếu lag có nguy cơ ảnh hưởng accounting/fraud SLA.

---

## 8. Bản Đồ Ownership Theo Role

| Luồng | Owner implementation chính | Bạn với vai trò Observability |
|---|---|---|
| Browse | Reliability/Build tùy backlog | Dashboard latency/error, alert browse degradation |
| Product detail + AI review | Reliability Eng #1 + Build nếu circuit breaker/fallback | Trace DB/LLM, alert DB/LLM degradation |
| Cart | Reliability Eng #1/#2 tùy SPOF/probe/PDB | Alert cart error, Valkey health, checkout impact |
| Checkout | Nhiều role cùng bảo vệ, ưu tiên Reliability | Owner dashboard/alert/runbook checkout end-to-end |
| Kafka -> accounting/fraud-detection | Reliability Eng #3 | Alert consumer lag/down/error, điều phối incident |

---

## 9. Dashboard Nên Có

### Executive / Service Health Dashboard

- Checkout success rate.
- Checkout p95/p99 latency.
- Browse p95 latency.
- Cart success rate.
- Kafka consumer lag accounting/fraud-detection.
- Current incidents / firing alerts.

### Checkout Deep Dive Dashboard

- Request rate, error rate, duration của checkout.
- Dependency latency: cart, product-catalog, currency, shipping/quote, payment, email.
- Kafka publish success/failure.
- Pod readiness, restart, CPU/memory.

### Kafka Dashboard

- Consumer lag by group.
- Message in/out rate.
- Consumer processing rate.
- Consumer errors.
- Pod restart/crashloop.

### Dependency Dashboard

- PostgreSQL connection pool, query latency, timeout.
- Valkey latency, memory, connection errors.
- Payment error/latency.
- LLM timeout/latency/fallback rate.

---

## 10. On-Call Checklist Khi Alert Fire

```text
Alert fire
|
v
1. Acknowledge alert
|
v
2. Xác định severity
   |
   +-- Checkout bị ảnh hưởng? => P0
   +-- Cart/payment/catalog bị ảnh hưởng? => P1/P0 tùy impact
   +-- Kafka lag sau checkout? => P1 nếu backlog tăng nhanh
   +-- Recommendation/ad/llm lỗi riêng lẻ? => P2 nếu có fallback
|
v
3. Mở dashboard liên quan
|
v
4. Lấy trace/log mẫu để khoanh vùng dependency lỗi
|
v
5. Gọi đúng owner implementation
|
v
6. Theo dõi recovery và cập nhật incident channel
|
v
7. Sau incident: ghi MTTA/MTTD/MTTR và update runbook
```

---

## 11. Định Vị Vai Trò Của Bạn

Bạn nên hiểu tất cả các luồng, vì on-call cần nhìn được hệ thống end-to-end. Tuy nhiên, bạn không cần tự mình implement/fix tất cả service.

Trong pitch hoặc daily standup, có thể nói như sau:

> Tôi đảm nhận Observability Engineer / On-Call Captain. Tôi cover observability cho tất cả business flows, trong đó ưu tiên checkout end-to-end vì đây là luồng revenue-critical. Tôi phụ trách dashboard, alert, trace/log investigation, runbook và điều phối incident. Các owner service sẽ fix implementation, còn tôi đảm bảo team phát hiện sự cố sớm, khoanh vùng nhanh và có số liệu để báo cáo SLO/MTTR.

