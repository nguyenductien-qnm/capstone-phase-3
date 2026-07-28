# MANDATE-15 / TF1-111 — bắt đúng, không bị che, không kêu oan khi bận

**Ngày đo:** 28/07/2026 · **Người đo:** Thanh Pham Huu Tien
**Môi trường:** cluster `ecommerce-dev-eks` (us-east-1), namespace `techx-tf1` — **cụm thật, không phải docker-compose**
**Detector:** pod `aiops-detector-7dc4d5648-4ptdm`, image `1.3-aiops-detector-9ed48e5`, 17 rule, poll 30s, `provider=discord`

MANDATE-15 hỏi ba câu, không phải một:

1. **Bắt được không?** — đã trả lời ở `report/mandate15-eks/report.md` (26/07): precision 0.077 / recall 0.500 / lead-time 380.0s.
2. **Có bị che không?** — một spike đi trước có làm bỏ sót một sự cố NHỎ HƠN ngay sau đó không.
3. **Bận có bị nhầm là hỏng không?** — tải hợp lệ tăng mạnh mà không có lỗi nào, detector có kêu oan không.

Bản này trả lời câu 2 và câu 3, và đo lại câu 1 trên detector đã sửa.

---

## 1. Kết quả — số mức BỘ

| Chỉ số | Công thức | **EKS 28/07** | EKS 26/07 |
|---|---|---|---|
| K | số sự cố phải bắt | 2 | 2 |
| **recall** | bắt được / K | **0.500** | 0.500 |
| **precision** | lần kêu đúng / tổng lần kêu | **1/4 = 0.250** | 1/13 = 0.077 |
| **lead-time** | từ lúc sự cố bắt đầu tới lúc kêu | **51.6s** | 380.0s |

Số máy sinh: `set-level-score-28jul.txt`. Dữ liệu thô: `alerter_history-28jul-*.jsonl`.

**Lead-time cải thiện 7.4 lần** (380.0s → 51.6s). Nguyên nhân đã biết từ 26/07: rule đổi
từ `grpc-error-rate-high` (mẫu số bị RPC health-check pha loãng) sang `service-error-rate-high`
trên spanmetrics. Đây là thước đo của cả loạt TF1-102, nay có số xác nhận.

**precision 0.250 là con số bi quan có chủ ý.** Trong ca `cart`, ngoài alert đúng trên
`checkout` còn 2 alert nữa trên `frontend-proxy` và `frontend` (cách 32s). Hai cái đó
**không sai** — cart chết thì frontend gọi qua nó cũng lỗi thật — nhưng cách chấm hiện tại
tính chúng là "lần kêu không đúng" vì `service` của kịch bản là `checkout`. Giữ nguyên cách
chấm để so được với 26/07, và ghi rõ ở đây thay vì nới định nghĩa cho số đẹp hơn.

### 1.1 Từng ca

| Ca | Loại | Bơm | Kỳ vọng | Kết quả |
|---|---|---|---|---|
| `case_cart_outage_eks` | real | `cart` → 0 replica | phải kêu | **PASS** — `service-error-rate-high`/checkout tại **+51.6s** |
| `case_payment_outage_eks` | real | `payment` → 0 replica | phải kêu | **FAIL** — rule kỳ vọng im lặng (mục 4) |
| `case_quiet_window_eks` | healthy_load | *không bơm gì*, 300s | **không** được kêu | **PASS** — 0 báo động giả (26/07: FAIL, 10 báo động giả) |
| `case_healthy_load` | healthy_load | 22 → 112 user qua REST API locust | **không** được kêu | **PASS** — 0 báo động giả ở tải 5.21× (mục 3) |

---

## 4. Ca `payment` FAIL — và một đính chính so với cách diễn đạt cũ

**Verdict FAIL đứng vững:** rule kỳ vọng (`service-error-rate-high` trên `checkout`) không
kêu. Kiểm chứng bằng số, không suy đoán — truy vấn Prometheus đúng cửa sổ bơm:

```
sum by (service_name) (rate(traces_span_metrics_calls_total{service_name="checkout",
  status_code="STATUS_CODE_ERROR"}[5m])) / clamp_min(sum by (service_name) (...), 0.001)
→ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0   (13/13 mẫu)
```

Tỉ lệ lỗi của `checkout` đứng nguyên **0.0000** suốt cả cửa sổ. Ngưỡng 0.10 hay 0.01 đều
vô nghĩa khi tử số bằng 0. Nguyên nhân đã truy tận gốc ở `report/mandate15-eks/report.md`
mục 4 (bốn điểm mù xếp chồng, gốc là `checkout` đã chuyển sang gọi `payment` qua Kafka nên
giết `payment` không sinh lỗi ở đâu) — **chưa sửa gì kể từ đó, nên lỗ hổng tái hiện y nguyên.**

**Đính chính:** báo cáo 26/07 viết *"detector im lặng tuyệt đối"*. Lần chạy này **không**
im lặng tuyệt đối:

| | |
|---|---|
| Bơm bắt đầu | 05:03:38Z |
| Bơm kết thúc | 05:15:55Z (kéo dài 738s) |
| `service-traffic-collapse` / `payment` kêu | **05:16:50Z** |
| → sau khi sự cố bắt đầu | **+792s** |
| → sau khi sự cố đã được khắc phục | **+55s** |

Tức có một rule **đúng service** đã bắt được — nhưng kêu khi sự cố đã kết thúc rồi. Về mặt
vận hành thì vô dụng, và vì nó không nằm trong `expected_rule_ids` nên harness chấm là một
lần kêu sai, kéo precision xuống.

Không sửa `expected_rule_ids` để biến FAIL này thành PASS. Thêm `service-traffic-collapse`
vào danh sách kỳ vọng sau khi đã thấy nó kêu chính là chỉnh bài test cho khớp kết quả. Nếu
muốn đưa nó vào thì phải là một quyết định có lý lẽ đứng độc lập — và lý lẽ đó hiện **không
có**, vì +792s cho một sự cố kéo dài 738s nghĩa là phát hiện đến sau khi mọi chuyện đã xong.

### 0. Một biến nhiễu đã biết — ghi TRƯỚC khi chạy

Pod `jaeger-7bc68fd759-ltrcd` (limit 1Gi) đang OOMKilled lặp lại. Đo được trong lúc chuẩn bị:

| Lần OOM (finishedAt) | Detector kêu lúc | MTTD | restartCount |
|---|---|---|---|
| 03:05:05Z | 03:05:34Z | **29s** | 5 |
| 03:44:07Z | 03:44:30Z | **23s** | 6 |

Nhịp ~39 phút. `oom-detected` nằm trong `monitored_rule_ids` của ca healthy-load, mà ca
đó chấm PASS/FAIL bằng "không rule nào được kêu". Nên **nếu jaeger OOM đúng vào cửa sổ
đo, ca sẽ FAIL vì một dương tính THẬT, không phải vì tải cao bị nhầm là hỏng.**

Ghi trước để chỗ này không thành lời biện minh sau khi thấy kết quả. Cách xử lý đã định sẵn:

- Cửa sổ đo bố trí vào ~03:56–04:06Z, cách lần OOM gần nhất (03:44) và cách lần dự kiến
  kế tiếp (~04:23) — cũng qua hẳn `lookback_seconds: 300` của lần 03:44.
- Nếu `oom-detected` vẫn kêu, đối chiếu `finishedAt` của container để xác định là OOM
  thật hay không, rồi báo cáo verdict thô KÈM phân loại — không sửa verdict.
- **Không** gỡ `oom-detected` khỏi danh sách theo dõi để lấy PASS.

---

## 3. Ca healthy-load — PASS, nhưng phải đọc kèm điều kiện

**`VERDICT (healthy_load): PASS — no false alarm under load`**
Cửa sổ chấm 03:57:09 → 04:07:15Z. Log: `run-28jul-healthy-load.log`.
Kết quả máy sinh: `case_healthy_load-28jul.result.json`. Dữ liệu thô: `alerter_history-28jul-healthyload.jsonl`.

### 3.1 Tải đã tăng bao nhiêu — đo, không phải ước

Lấy mẫu 10s/lần bằng trường `current_rps` (xem mục 6.2 về việc vì sao không dùng `total_rps`):

| | Nền (n=51, 11 phút) | Tải cao (n=31, 7 phút) |
|---|---|---|
| user | 22 | 112 |
| `current_rps` mean | **4.52** | **23.55** |
| `current_rps` median | 4.30 | 23.10 |
| `current_rps` max | 7.50 | 32.70 |
| avg latency | 66.9 ms | **64.1 ms** |
| `fail_ratio` max | 0.00015 | 0.00014 |

**Bội số: 5.21× theo mean, 7.23× theo đỉnh.** Số thô: `rps-baseline-28jul.csv`, `rps-healthyload-28jul.csv`.

Đáng chú ý: độ trễ **không** tăng (66.9 → 64.1 ms) và tỉ lệ lỗi đứng yên ở mức ~0.00014.
Tức HPA hấp thụ trọn cú tăng 5×. Đây là lý do vật lý khiến không rule nào kêu — không phải
vì detector "khoan dung", mà vì hệ thật sự không hề suy giảm. Nói rõ để không nhận công quá.

### 3.2 Điều làm PASS này yếu hơn con số 17 nghe có vẻ

Trong chính cửa sổ đó, detector tự phát **8 alert `detector-silent-rule`** (`severity: info`) —
cơ chế rule tự tố cáo khi query không trả về series nào:

`error-budget-burn-fast-standard` · `error-budget-burn-fast-checkout` ·
`error-budget-burn-slow-standard` · `error-budget-burn-slow-checkout` ·
`error-budget-burn-fast` · `bedrock-cost-high` · `genai-latency-high` · `memory-saturation-high`

Cả 8 đều nằm trong `monitored_rule_ids`. Nghĩa là:

| | |
|---|---|
| Rule được theo dõi | 17 |
| Rule **mù** (không có dữ liệu, không thể kêu) | **8** |
| **Rule thực sự được kiểm** | **9** |

PASS là thật, nhưng nó nói "9 rule có dữ liệu đã không kêu oan dưới tải 5×", không phải
"17 rule đã không kêu oan". Tám rule kia im lặng vì mù, không phải vì đúng. Đây chính là
task #25 đang mở, nay có bằng chứng do chính detector sinh ra thay vì suy luận.

### 3.3 Biến nhiễu jaeger đã không xảy ra

`oom-detected` **không** kêu trong cửa sổ. Lần OOM gần nhất trước đó là 03:44:07, lần kế
tiếp rơi ngoài cửa sổ — đúng như bố trí ở mục 0. Không phải may: cửa sổ được đặt có chủ đích.

---

## 2. Ca masking — kết quả thật khác kỳ vọng, và đây là chỗ phải đọc kỹ

### 2.1 Chạy sống: PASS cả trước lẫn sau winsorize — nhưng KHÔNG phải một phép A/B

| Lần chạy | Ngày/giờ | Sự cố 1 (spike) | Sự cố 2 (nhỏ) | Kết quả |
|---|---|---|---|---|
| trước winsorize | 27/07 17:07 | `checkout`, 360s | `checkout`, **15s** | PASS — lead 150.8s / 91.9s |
| sau winsorize | 27/07 22:59 | `frontend`, 360s | `frontend`, **60s** | PASS — lead 119.9s / 93.3s |

**Hai lần chạy này dùng hai kịch bản KHÁC NHAU** (đổi service `checkout`→`frontend` và
thời lượng sự cố 2 từ 15s→60s ở commit `a8edb03`, 27/07 22:23 — tức giữa hai lần chạy).
Cho nên cặp số trên **không chứng minh được gì về winsorize**. Nó chỉ nói: cả hai thiết
kế kịch bản đều PASS trên cụm thật.

Ghi rõ điều này thay vì đặt hai chữ PASS cạnh nhau và để người đọc tự suy ra "winsorize
có tác dụng" — vì cặp số đó không cho phép suy ra như vậy.

### 2.2 Phép A/B thật nằm ở replay offline

Bằng chứng có giá trị cho winsorize là `report/mandate15/replay_masking.py`: lấy **chuỗi
thật 57 điểm** (step 30s) của `service-error-rate-high` / `frontend` đo trên cụm, rồi
chạy lại đúng thuật toán phát hiện **hai lần, chỉ khác mỗi winsorize**:

| | Sự cố 1 (noise-spike) | Sự cố 2 (subtle-incident) | Verdict |
|---|---|---|---|
| **KHÔNG** winsorize | bắt được, lead 120s | **BỊ CHE** | **FAIL** |
| **CÓ** winsorize | bắt được, lead 120s | bắt được, lead 119s | **PASS** |

Cùng dữ liệu, cùng ngưỡng tĩnh 0.1, cùng cổng SLO 0.5 — biến duy nhất là winsorize.
Đây mới là phép so sánh có kiểm soát. Số tái tạo được: `python3 report/mandate15/replay_masking.py`.

**Vì sao chạy sống không tách được còn replay lại tách được:** cơ chế che cần sự cố 2
rơi đúng vào lúc baseline còn đang bị nhiễm độc bởi spike (cửa sổ 30 mẫu = 15 phút).
Trên cụm thật, thời điểm sự cố 2 nổi lên phụ thuộc vào HPA, retry, và độ trễ scrape —
lệch vài chục giây là ra khỏi vùng bị che. Replay ghim đúng chuỗi số nên tái tạo được
điều kiện đó một cách xác định.

### 2.3 Giới hạn của chính winsorize — đã ghi trong code, không giấu

`detector.py` kẹp giá trị về `dynamic_threshold` trước khi nạp vào history. Trên chuỗi
**phương sai bằng không** (`mean=0, std=0` → `dynamic_threshold=0`) thì `min(value, 0) = 0`
với mọi giá trị, nên baseline bị ghim ở 0 vĩnh viễn chứ không "dần dần kéo theo".
Chuỗi tỉ lệ lỗi của `checkout` đúng là như vậy khi hệ khoẻ (đo được: 0.0000 suốt 121/121
mẫu trong 1 giờ). Với rule này đó lại là điều **mong muốn** — nó giữ ranh phát hiện sát
đáy nên sự cố nhỏ vẫn nổi lên — nhưng không được áp dụng mù cho rule khác mà không đo lại.

---

## 5. Một báo động giả đã truy tới tận gốc và đã sửa: `llm-rate-limit-429`

Ca healthy-load lần chạy 27/07 **FAIL**. Truy ra không phải detector chậm hay ngưỡng sai,
mà là một cụm từ khớp sai trong `rules.yaml`.

Dòng log làm nó kêu:

```
[frontend-proxy] ... "GET /api/product-reviews/6E92ZMYYFZ HTTP/1.1" 200 - via_upstream - "-" 0 534 429 429 "10.0.91.23" "python-requests/2.34.2"
```

Status là **200**. Số `429` là trường `%DURATION%` — request mất 429 **mili-giây**. Và
`python-requests/2.34.2` chính là load generator của bài đo.

Nguyên nhân: `body` là field `text` đã analyze, nên `match_phrase` với cụm `"429"` trần
khớp **token** `429` ở bất kỳ đâu trong dòng log, không riêng gì ô trạng thái HTTP.

Đếm trên toàn bộ index (7 ngày, 7.941.641 dòng):

| Loại dòng khớp `"429"` | Số dòng | Là 429 thật? |
|---|---|---|
| Access log Envoy, status 200, `429` = `%DURATION%` | 24 | không |
| `topic=domain.checkout.orders, partition=0, offset=429` | 25 | không |
| **Tổng** | **49** | **0** |

**Precision = 0.00** trên toàn bộ dữ liệu rule này từng thấy — với `severity: critical`.

Chuỗi nhân quả đáng chú ý: tải cao → độ trễ tăng → một request mất đúng 429ms → CRITICAL.
Tức cụm từ này biến "hệ thống BẬN" thành "hệ thống HỎNG" — đúng cái lỗi MANDATE-15 đi tìm.

Đã sửa (PR #462, merge `9ed48e5`): bỏ `"429"` trần, thay bằng `'HTTP/1.1" 429'` — analyzer
tách thành `[http, 1.1, 429]` liên tiếp nên chỉ khớp khi status THẬT SỰ là 429. Kèm test
hồi quy `test_no_log_rule_matches_a_bare_number`. Chi tiết: `report/mandate15/false-positive-429.md`.

**Nói thẳng về phương pháp:** tôi sửa rule SAU khi thấy FAIL. Đó là tình huống dễ thành
"chỉnh bài test cho khớp kỳ vọng". Lý do sửa không dựa vào kết quả FAIL đó mà dựa vào
precision 0.00 trên 49 lần khớp suốt 7 ngày — một con số đã đúng từ trước khi có bài test.
Kết quả FAIL gốc không bị xoá, nó nằm ở mục 3.

---

## 6. Hai phát hiện ngoài dự kiến trong lúc đo

### 6.1 `oom-detected` bắt một OOM thật trong 29 giây

03:05:05Z pod `jaeger-7bc68fd759-ltrcd` bị OOMKilled (limit 1Gi, đã restart 5 lần).
Detector kêu lúc 03:05:34Z — **29 giây**, đúng một chu kỳ poll.

Đây là số MTTD **trên EKS, sự cố thật, không dàn dựng**, và nó ở một bậc hoàn toàn khác
380s của nhánh metric. Lý do: `oom-detected` là `type: k8s_status`, đọc thẳng trạng thái
container, không phải chờ một tỉ lệ tích trong cửa sổ `rate(...[5m])`. Hai con số đo hai
đường phát hiện khác nhau, không được trộn.

**Khuyết điểm kèm theo:** alert ghi `service: "unknown"`. Người trực nhận được "có cái gì
đó OOM" mà không biết là pod nào — phải tự đi tra. Chưa sửa trong đợt này, ghi vào mục 8.

### 6.2 Số throughput cũ đo nhầm trường

Ghi chú kịch bản healthy-load (và commit tạo ra nó) ghi *"22 → 106 user cho thông lượng
24.69 → 94.80 req/s, tức 3.84 lần"*. Con số đó đọc từ trường `total_rps` của locust, mà
`total_rps` là **trung bình cộng dồn từ lúc locust khởi động** — ở đây là nhiều ngày, và
bị nhiễm bởi mọi đợt tải của người khác.

Đo đối chứng 28/07 lúc 22 user: `total_rps` = **34.99** trong khi `current_rps` = **5.60**.
Chênh hơn 6 lần. Bội số 3.84x vì thế không đứng vững và đã bị loại; số ở mục 3 đo bằng
`current_rps`, lấy mẫu 10s một lần suốt cửa sổ.

---

## 7. Cách bơm và vì sao

**flagd không bơm được trên EKS.** ArgoCD nạp `values-flagd-sync.yaml` trỏ flagd vào
`https://122.248.223.194.sslip.io/flags.json` của BTC; patch ConfigMap không có tác dụng.
Đây là lý do mọi ca dùng `inject: {"type": "command"}` với `kubectl` thay vì flagd.

**Ca healthy-load dùng REST API của locust, không dùng `kubectl scale`.** Hai lý do đo được:

1. Nhân bản pod chỉ cho **1.47x** vì pod mới cần thời gian ramp user.
2. `kubectl scale` gây một nhịp traffic **tụt** lúc pod lên/xuống, mà nhịp tụt đó có thể
   tự nó làm `service-traffic-collapse` kêu — tức tạo đúng một báo động giả trên chính ca
   dùng để chứng minh không có báo động giả.

`POST /swarm` đổi số user ngay, không restart pod, không tạo nhịp tụt.

**Kiểm chứng nhịp tụt:** 03:34 tôi hạ tải 211 → 22 user (dọn tải do người khác để lại).
Không rule nào kêu trong và sau cú hạ đó. Nên với biên độ này, `service-traffic-collapse`
không phải nguồn nhiễu.

**An toàn:** `aiops-remediation` chạy `REMEDIATION_DRY_RUN=true` và chỉ có policy cho
`oom-detected`, nên nó không can thiệp vào các ca này. Mọi deployment đều được khôi phục
về `--replicas=2` (đúng `minReplicas` của HPA).

---

## 9. Điều chưa làm được, nói rõ

- **Cặp trước/sau winsorize chạy sống không phải A/B** (mục 2.1). Bằng chứng có kiểm soát
  chỉ có ở replay offline. Muốn có A/B sống thật thì phải deploy hai image khác nhau và
  chạy cùng kịch bản — không làm trong đợt này.
- **`monitored_rule_ids` của 3 ca EKS cũ vẫn là 11 rule**, không phải 17. Cố ý giữ nguyên
  để so được với mốc 26/07; nếu mở rộng thì phép so mất ý nghĩa. Hệ quả: precision của 3
  ca đó tính trên tập rule hẹp hơn ca healthy-load.
- **`oom-detected` không định danh được service** (mục 6.1).
- **`error-budget-burn-fast` và 3 rule burn-rate khác vẫn ở trạng thái DRAFT**, chưa verify
  PromQL trên Prometheus sống. Chúng nằm trong danh sách theo dõi nhưng nhiều khả năng mù.
- **K nhỏ.** Bộ có nhãn trên EKS mới có 5 ca. Đủ để kết luận về từng lỗ hổng đã truy tới
  gốc, chưa đủ để coi precision là con số ổn định.
