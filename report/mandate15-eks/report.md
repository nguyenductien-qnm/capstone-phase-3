# MANDATE-15 / TF1-98 — đo lại precision/recall/lead-time trên EKS thật

**Ngày đo:** 26/07/2026 · **Người đo:** Thanh Pham Huu Tien
**Môi trường:** cluster `ecommerce-dev-eks` (us-east-1), namespace `techx-tf1` — **cụm thật, không phải docker-compose**
**Detector:** pod `aiops-detector-544bb4d5c6-bfr7p`, image `1.3-aiops-detector-43cfff8`, đứng sẵn trong cụm 10 ngày, `provider=discord`, 16 rule, poll 30s

Đây là bản đo lại của `#7b` (vốn chạy trên docker-compose) theo đúng yêu cầu TF1-98:
*"Re-measure P/R + lead-time + MTTD before/after trên EKS/prod us-east-1"*.

---

## 1. Kết quả — số mức BỘ, không phải từng ca

Mandate yêu cầu đo trên **một bộ sự cố có nhãn**, không phải chọn ca đẹp nhất.

| Chỉ số | Công thức | **EKS (26/07)** | compose `#7b` (25/07) |
|---|---|---|---|
| K | số sự cố phải bắt | **2** | 3 |
| **recall** | bắt được / K | **1/2 = 0.500** | 1/3 = 0.333 |
| **precision** | lần kêu đúng / tổng lần kêu | **1/13 = 0.077** | 1/6 = 0.167 |
| **lead-time** | từ lúc sự cố bắt đầu tới lúc kêu | **380.0s** | 88.9s |

Số máy sinh: `set_level_score.json`, `set-level-score.log`.
Dữ liệu thô để chấm lại độc lập: `alerter_history.jsonl` (14 alert), `alerter_history_quiet.jsonl`.

**Đọc cho đúng:** recall khá hơn compose nhưng precision và lead-time đều **tệ hơn rõ rệt**.
Lead-time xấu đi 4.3 lần có nguyên nhân đo được, xem mục 3.

### 1.1 Từng ca

| Ca | Loại | Bơm | Kỳ vọng | Kết quả |
|---|---|---|---|---|
| `case_cart_outage_eks` | real | `cart` → 0 replica, 367s | phải kêu | **PASS** — `grpc-error-rate-high`/checkout tại **+380s** |
| `case_payment_outage_eks` | real | `payment` → 0 replica, 367s | phải kêu | **FAIL** — detector im lặng hoàn toàn |
| `case_quiet_window_eks` | healthy_load | *không bơm gì*, 188 phút | **không** được kêu | **FAIL** — 10 báo động giả |

---

## 2. Cách bơm: `kubectl`, không phải flagd — và vì sao

flagd trên EKS **không bơm được**. ArgoCD Application `techx-corp` (namespace `techx-tf1`) nạp
`platform/gitops/environments/sandbox/values-flagd-sync.yaml`, file này trỏ flagd vào
`https://122.248.223.194.sslip.io/flags.json` của BTC. Patch ConfigMap `flagd-config` không có
tác dụng. Đây đúng như ADR-012 addendum 25/07 đã ghi, nay xác nhận lại từ chính manifest.

Harness đã có sẵn `inject: {"type": "command", ...}` (`incident_replay.py:83`) nên **không phải
sửa code đo trong lúc đang đo** — giữ đúng nguyên tắc đã theo ở `#7b`. Scenario dùng
`kubectl scale` để tạo sự cố thật và hoàn tác được.

An toàn: `aiops-remediation` trên cụm chạy `REMEDIATION_DRY_RUN=true` và chỉ có 1 policy cho
`oom-detected`, nên nó không can thiệp vào hai ca này. Cả hai deployment đều được khôi phục;
HPA (min 2) tiếp quản sau đó.

---

## 3. Vì sao lead-time xấu 4.3 lần so với compose

Không phải detector chậm đi. Là vì **mẫu số của rule bị RPC health-check pha loãng**.

`grpc-error-rate-high` tính tỉ lệ trên *toàn bộ* RPC của service. Đo trên cụm lúc 26/07:

| RPC của `checkout` | req/s |
|---|---|
| `grpc.health.v1.Health/Check` | 0.582 |
| `oteldemo.CheckoutService/PlaceOrder` | 0.071 |

Health-check chiếm **89%** mẫu số. Nên kể cả khi **100% đơn hàng thất bại**, tỉ lệ lỗi
chỉ bò lên ~0.109–0.18 so với ngưỡng 0.05 — thay vì vọt lên 0.9576 như trên compose
(nơi traffic do load-generator đẩy tập trung vào luồng checkout). Biên mỏng + cửa sổ
`rate(...[5m])` ⇒ mất 380s mới vượt ngưỡng.

Đo được trong lúc bơm: `status=13` tăng 5 → 10 → 18 → 26; tỉ lệ lỗi cửa sổ 2 phút đi
0.0708 → 0.1220 → 0.1818.

**Hệ quả:** ngưỡng 0.05 không có nghĩa như ta tưởng. Với service mà health-check áp đảo,
nó tương đương "hơn một nửa số request nghiệp vụ hỏng". Muốn lead-time thật thì rule phải
loại `grpc.health.v1.Health/Check` khỏi mẫu số, hoặc tách rule theo `rpc_method`.

---

## 4. Ca `payment` FAIL — bốn điểm mù xếp chồng

Bơm: `payment` → 0 replica, 367 giây. Sự cố **có thật**. Detector **im lặng tuyệt đối**.
Truy từng lớp, mỗi lớp kiểm chứng riêng:

**4.1 — Kiến trúc đã đổi sang bất đồng bộ, tài liệu chưa phản ánh.**
`checkout` **không còn gọi `payment` qua gRPC**. Chuỗi span `oteldemo.PaymentService/Charge`
đứng yên ở 19950 từ 25/07 ~21:30 rồi biến mất sau lần reset counter 26/07 08:45
(`raw/charge_span_7d.json`). Trong cửa sổ bơm, `checkout` chạy 42 `PlaceOrder` với đầy đủ call
sang cart/catalog/currency và **không một span nào sang payment**
(`raw/checkout_spans_during_injection.json`).

`payment` vẫn sống và vẫn xử lý đơn — qua Kafka: `KAFKA_TOPIC=domain.checkout.orders`,
`KAFKA_GROUP_ID=payment`, log `"Payment service published fulfillment event to topic
'domain.fulfillment.events'"`. Nên giết payment **không sinh lỗi ở bất kỳ đâu**; đơn hàng
vẫn được nhận, chỉ là chất đống trong Kafka không ai xử lý.

**4.2 — `payment` không xuất metric gRPC server-side.** Trên cả cụm chỉ **3/20 service** xuất
`rpc_server_duration_milliseconds`: `ad`, `checkout`, `product-catalog`. Báo cáo `#7b` mới ghi
nhận 2 service mù (`cart`, `image-provider`); thực tế rule này mù với gần như toàn hệ thống.

**4.3 — `payment` không xuất metric consumer lag.** Chỉ `fraud-detection` xuất
`kafka_consumer_records_lag`. Backlog mà payment tạo ra không có metric nào đo.

**4.4 — Rule đáng lẽ bắt được thì sai tên metric.**
`kafka-consumer-lag-high` (`rules.yaml:301`) query `kafka_consumer_group_lag`. Comment của
chính rule ghi *"PHAI verify ten metric tren Prometheus EKS ... truoc khi tin (TF1-71)"*.
**Nay verify xong** (`raw/kafka_metric_names.json`):

```json
{"assumed_by_rule": "kafka_consumer_group_lag", "exists": false,
 "actual_lag_metrics": ["kafka_consumer_records_lag",
                        "kafka_consumer_records_lag_avg",
                        "kafka_consumer_records_lag_max"]}
```

Tên giả định **không tồn tại**. Rule này vừa DRAFT vừa sai tên — nguy hiểm ở chỗ nếu ai đó
bật nó lên tưởng đã xong việc, nó sẽ **im lặng vĩnh viễn chứ không báo lỗi**, vì query trả
chuỗi rỗng chứ không ném exception.

> **Đây là lỗ hổng đáng lo nhất của cả đợt đo.** Một service nghiệp vụ lõi ngừng xử lý hoàn
> toàn, và không một tầng nào trong 16 rule nhận ra. Rule error-ratio mù về mặt cấu trúc với
> loại hỏng "im lặng" — chúng chỉ bắt được hỏng-có-lỗi, không bắt được hỏng-không-còn-tín-hiệu.

---

## 5. Ca cửa sổ yên tĩnh FAIL — báo động giả 3.2 lần/giờ

188 phút, không bơm gì, **10 alert**. Truy từng lần: tại thời điểm kêu, tỉ lệ lỗi `checkout`
lần lượt là `0.0219`, `0.0125`, `0.0063` — **không lần nào chạm ngưỡng tĩnh 0.05**
(`raw/checkout_error_ratio_injection.json` và query_range trong log).

Toàn bộ đến từ **tầng 3-sigma động**. Cơ chế: `detector.py:89-101` giữ cửa sổ trượt 30 mẫu,
poll 30s ⇒ baseline chỉ **15 phút**. Khi tỉ lệ lỗi nền dao động quanh 0.005 với phương sai
rất nhỏ, một nhịp lên 0.02 đã vượt `mean + 3σ`, dù về mặt vận hành hoàn toàn vô hại
(thấp hơn ngưỡng SLO 5% tới 2.5 lần).

Đây chính xác là bài toán over-alerting mà MANDATE-15 sinh ra để giải quyết, và giờ có
**số đo trên cụm production** chứ không còn là giả thuyết.

---

## 6. MTTD before / after

| | Nguồn | Precision | Recall | Thời gian phát hiện |
|---|---|---|---|---|
| **Before** | `evaluate_detector.py` — dữ liệu **tổng hợp** sin+ramp+spike tự gán nhãn | 0.6875 | 0.9167 | 5 step (đơn vị bước, không phải giây) |
| **After (compose, `#7b`)** | bộ có nhãn, bơm flagd thật | 0.167 | 0.333 | 88.9s |
| **After (EKS, bản này)** | bộ có nhãn, bơm `kubectl` thật, detector đứng sẵn trong cụm | **0.077** | **0.500** | **380.0s** |

Con số tổng hợp cũ **lạc quan hơn thực tế khoảng 9 lần về precision**. Nguyên nhân: dữ liệu
tổng hợp có tỉ lệ tín hiệu/nhiễu cao và không hề chứa nhiễu nền của một cụm đang chạy thật.
Không nên dùng nó để báo cáo năng lực phát hiện nữa.

Ghi chú về `docs/ai/04_eval_report.md` (MTTD mean 19.6s / max 35.4s): đó là MTTD đo bằng
chaos flagd trên compose với sự cố đẩy tỉ lệ lỗi lên gần 1.0. Không mâu thuẫn với 380s ở
đây — khác môi trường và khác biên vượt ngưỡng (mục 3). Nhưng **con số dùng cho EKS phải là
380s**, không phải 35.4s.

---

## 7. Một bug của harness phát hiện trong lúc chấm — đã sửa

Khi chấm mức bộ, ca `payment` (detector im lặng) lại được báo là **caught, lead-time 1166.6s**.
Truy ra: `score_events` lọc alert theo `ts >= ev["t_start"]` mà **thiếu cận trên**. Với
scenario một sự kiện thì vô hại vì `observed` đã bị kẹp theo cửa sổ tổng; nhưng khi có nhiều
sự kiện, sự kiện sớm **nuốt luôn** alert của sự kiện muộn — ở đây ca payment cướp alert của
ca cart cách đó 19 phút.

Ảnh hưởng thật sự nằm ở MANDATE-15: `case_masking.json` **là scenario 2 sự kiện** theo thiết kế,
nên nó đang nằm đúng vào vùng lỗi này.

Đã sửa: kẹp thêm cận trên `ev["t_end"] + settle_seconds`. Kèm test hồi quy
`test_event_does_not_steal_an_alert_from_a_later_event`. Toàn bộ: **34/34 pass**
(13 `test_incident_replay.py` + 21 `test_detector.py`).

Số ở mục 1 là số **sau khi sửa**. Số sai trước khi sửa (`recall 1.000 / precision 0.154 /
lead-time 1166.6s`) ghi lại ở đây để ai đọc log cũ không nhầm.

---

## 8. Việc phải làm tiếp (không làm trong đợt này)

Xếp theo mức nghiêm trọng đo được:

1. **Sửa `kafka-consumer-lag-high`**: đổi `kafka_consumer_group_lag` → `kafka_consumer_records_lag`,
   rồi mới bỏ nhãn DRAFT. Chưa sửa thì đừng bật.
2. **Thêm rule bắt hỏng-im-lặng**: `absent()` hoặc "throughput tụt về 0" cho các service
   nghiệp vụ lõi. Không có nó thì cả lớp sự cố ở mục 4 mãi mãi vô hình.
3. **Bắt các service xuất metric server-side**, hoặc thêm rule đọc `traces_span_metrics_*`
   (collector đã sinh sẵn cho mọi service — chính nhờ nó tôi mới truy được mục 4.1).
4. **Loại health-check khỏi mẫu số** của `grpc-error-rate-high`, hoặc tách theo `rpc_method`.
5. **Xử lý báo động giả 3-sigma**: winsorize/EWMA — đúng phần việc đang nằm trong PR #343.
   Giờ đã có số nền để so trước/sau.

## 9. Điều chưa làm được, nói rõ

- **Không đo được ca masking và healthy-load-tải-cao** của MANDATE-15 trong đợt này. Bộ trên
  EKS mới có 3 ca. Hai ca đó nằm trong PR #343 chưa merge.
- **Cửa sổ yên tĩnh là quan sát thụ động**, không phải tải cao có kiểm soát — nó trả lời
  "detector có kêu nhảm khi bình thường không", chưa trả lời "bận có bị nhầm là hỏng không".
- **K=2 là nhỏ.** Đủ để kết luận về từng lỗ hổng đã truy tới tận gốc, chưa đủ để coi
  precision 0.077 là con số ổn định. Cần lặp lại nhiều phiên trước khi dùng nó làm baseline.
