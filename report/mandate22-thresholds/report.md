# TF1-107 — validate ngưỡng remediation bằng OOM chaos thật trên EKS

**Ngày đo:** 28/07/2026 · **Người đo:** Thanh Pham Huu Tien
**Môi trường:** cluster `ecommerce-dev-eks` (us-east-1), namespace `techx-tf1`
**Code chạy:** image `1.1-aiops-remediation-ebb7b7b` — **đúng image và đúng code** của
`aiops-remediation` đang deploy, chỉ khác file config và `REMEDIATION_DRY_RUN=false`

Ticket đòi validate 3 con số trong `aiops/remediation/remediation_policy.yaml` mà
`aiops/remediation/README.md` tự khai là *"GIẢ ĐỊNH ban đầu, chưa validate bằng chaos test
thật trên EKS"*:

| Số | Giá trị đang ship | Nguồn |
|---|---|---|
| Verify timeout | 120s, poll mỗi 20s | `anomaly_remediation.md` §4.4 |
| Circuit breaker | mở sau 3 fail liên tiếp, đóng lại sau 24h | §4.5 |
| Blast radius | 1 pod / namespace / 1 giờ | §4.3 |

---

## 1. Phương pháp ghi trong ticket không chạy được — và lý do đã đổi

Ticket ghi: *"Ép OOM qua flagd `emailMemoryLeak` trên EKS"*. Không thực hiện được:

| Rào cản | Kiểm chứng 28/07 |
|---|---|
| flagd trên EKS sync **read-only** từ nguồn trung tâm của BTC | Chính `values-flagd-sync.yaml` ghi: *"TF không tự đổi được flag vì nguồn trung tâm sync đè lên"*. Query OFREP: flag `emailMemoryLeak` **có tồn tại, giá trị 0**, nhưng TF không bật được |

**Một ghi chép cũ đã lỗi thời, sửa luôn ở đây:** ADR-013 addendum 17/07 ghi lý do không dùng
`emailMemoryLeak` là *"email bị loại khỏi CI build vì 2 CVE HIGH, chưa từng build thành công
nên không có pod để test"*. Kiểm 28/07: `platform/build-exclusions.yaml` **rỗng** và
`email` đang chạy **2/2, 13 ngày tuổi**. Rào cản đó **không còn**; rào cản thật hiện nay
chỉ là flagd read-only.

### Cách đã dùng thay thế

| Ca cần đo | Nguồn OOM | Vì sao |
|---|---|---|
| verify FAIL (nhánh "OOM mới") | pod mồi `tf1107-canary` | OOM lại sau ~25s → luôn có OOM mới trong cửa sổ verify |
| verify FAIL (nhánh "hết giờ") | pod mồi `tf1107-unready` | readinessProbe luôn fail + `sleep 300` trước khi cấp phát → không Ready mà cũng không OOM trong 120s |
| verify PASS | **`jaeger` — OOM THẬT, không dàn dựng** | đang OOMKilled lặp lại (~39 phút/lần), sau restart sống lâu hơn hẳn cửa sổ verify |

**Ca verify PASS KHÔNG đo được — và lý do chính là kết quả lớn nhất của ticket này.** Xem mục 5.

Pod mồi kế thừa nguyên mẫu `mttr-canary.yaml` của TF1-106: **không phục vụ traffic nào nên
blast radius bằng không**, nhưng mang đúng nhãn `opentelemetry.io/name` mà `find_oom_pods()`
đọc, nên đường đi qua remediation là y hệt pod thật.

### Không hạ tư thế an toàn của hệ trong lúc đo

`aiops-remediation` đang deploy **giữ nguyên `REMEDIATION_DRY_RUN=true` suốt thí nghiệm**.
Thí nghiệm chạy trên một Deployment riêng (`tf1107-runner`) dùng cùng image, cùng
ServiceAccount, config riêng qua ConfigMap. Lý do không bật dry-run của bản đang deploy:

- ArgoCD selfHeal sẽ revert `kubectl patch`; đi đường PR thì mỗi lần đổi tham số tốn một
  vòng deploy ~25 phút (TF1-106 đã phải làm vậy).
- Quan trọng hơn: bật dry-run của bản production nghĩa là **hạ tư thế an toàn của cả
  namespace** trong suốt thời gian đo.

**Tham số đã đổi so với bản ship — chỉ đúng MỘT thứ:** `blast_radius` từ `1 action/3600s`
lên `10 action/600s`. Lý do ở mục 4. `verify` và `circuit_breaker` **giữ nguyên** giá trị ship.

---

## 2. Verify — hai nhánh thoát, hai con số khác hẳn nhau

`verify_oom_recovery()` (`verifier.py`) có **hai** đường trả `False`, và ticket/README chỉ
nói tới một:

| Nhánh | Điều kiện | Đo được |
|---|---|---|
| **"OOM mới"** | thấy bất kỳ OOMKilled mới nào trong namespace | **43.0s** (3/3 lần, phương sai 0) |
| **"hết giờ"** | poll hết `duration_seconds` mà pod chưa Ready ổn định | **124.2s** |

### 2.1 Nhánh "OOM mới" — 43.0s, không hề chạm timeout

```
#1  action 07:28:47 -> verify FAIL 07:29:30  = 43.0s
#2  action 07:29:46 -> verify FAIL 07:30:29  = 43.0s
#3  action 07:30:46 -> verify FAIL 07:31:29  = 43.0s
```

**Kết luận đáng chú ý:** với sự cố OOM **lặp lại** — đúng loại sự cố mà rule `oom-detected`
sinh ra để xử lý — verify **không bao giờ** chạm ngưỡng 120s. Nó luôn thoát sớm ở 43s.
Nghĩa là con số 120s **không phải tham số chi phối** như tên gọi gợi ý; thứ chi phối là
`poll_interval_seconds: 20` (43.0s ≈ 2 nhịp poll + độ trễ API).

### 2.2 Nhánh "hết giờ" — 124.2s cho ngưỡng cấu hình 120s

```
action     07:39:14
verify FAIL 07:41:18   = 124.2s
```

Vượt 4.2s (~3.5%). Nguyên nhân đọc được trong code: vòng lặp gọi `sleep(poll_interval)` ở
**cuối** mỗi vòng rồi mới kiểm `deadline`, nên lần poll cuối luôn kéo dài thêm trọn một nhịp
20s trước khi thoát. Không phải lỗi, nhưng ai đặt timeout sát biên phải biết: ngưỡng thực tế
là `duration_seconds + tối đa một poll_interval`.

---

## 3. Circuit breaker — mở đúng sau 3 lần fail liên tiếp

```
07:31:45  circuit breaker DANG MO cho oom-detected:tf1107-canary
          - tu choi hanh dong, chi escalate
```

Hoạt động **đúng như spec**: đếm đủ 3 fail liên tiếp → mở → từ chối hành động → escalate
alert `severity=critical`. Sau khi mở, mọi chu kỳ tiếp theo đều bị chặn ở cổng đầu tiên.

---

## 4. Phát hiện chính: với tham số đang ship, circuit breaker gần như không mở được

Đây là kết quả quan trọng nhất của TF1-107, và nó là **hệ quả số học** của thứ tự các cổng
trong `process_oom_policy()`:

> circuit breaker → error budget → **blast radius** → dry-run → hành động → verify

`blast_guard.record(scope_key)` chạy **trước** hành động. Nên:

| | |
|---|---|
| Mỗi lần verify fail | tốn **1 action** |
| Breaker cần | **3 fail liên tiếp** |
| Blast radius đang ship | **1 action / 3600s / namespace** |
| → Thời gian tối thiểu để breaker mở | **≥ 2 giờ** |

Và điều kiện đó còn phải thoả thêm: `CircuitBreaker._fail_count` là **dict trong RAM của
tiến trình**. Mọi lần pod `aiops-remediation` restart — deploy mới, node scale, OOM, ArgoCD
sync — đều reset đếm về 0. Một tiến trình phải sống sót nguyên 2 giờ liên tục thất bại thì
breaker mới mở.

**Đó là lý do tôi phải nới `blast_radius` lên `10/600s` mới quan sát được breaker.** Ghi rõ
ở đây chứ không giấu: con số 3 fail/24h **không sai về logic** — code chạy đúng — nhưng
**không với tới được** khi ghép cùng blast radius hiện tại.

Ghi chú: `blast_radius` cũng đã bị TF1-106 đo và kiến nghị xem lại vì lý do độc lập (nó khiến
vòng tự dập chỉ cứu 1/30 lần OOM, cải thiện MTTR trung bình 2.7% chứ không phải 4.6×). Hai
kết quả độc lập cùng chỉ vào một tham số.

---

## 5. Lỗi nghiêm trọng: vòng khép kín tự cắn chính nó trên 28% số pod

Định đo ca **verify PASS** bằng OOM thật của `jaeger`. Kết quả không như dự kiến, và nó lộ
ra một lỗi thật:

```
07:52:48  restart_pod: xoa pod techx-tf1/jaeger-7bc68fd759-ltrcd
07:54:52  verify: het 120s ma pod van chua Ready on dinh, FAIL
```

Nhưng pod thay thế **đã Ready sau đúng 2 giây**:

```
pod jaeger-7bc68fd759-9ncq8
  startTime  2026-07-28T07:52:48Z
  Ready True 2026-07-28T07:52:50Z     <- 2 giay
```

Remediation làm **đúng** (xoá pod, pod mới lên khoẻ trong 2s) nhưng lại **tự chấm mình là
thất bại** và chờ vô ích 124 giây.

### Nguyên nhân — chuỗi bốn bước

1. `find_oom_pods()` quét pod OOM **không lọc theo nhãn**, và khi pod thiếu nhãn thì gán
   `service_label = "unknown"` (giá trị mặc định của `.get()`):
   ```python
   service_label = (pod.metadata.labels or {}).get(service_label_key, "unknown")
   ```
2. Remediation **vẫn hành động thật** trên pod đó — không có gì chặn.
3. `is_service_ready()` lại đi tìm pod bằng **label selector**:
   ```python
   label_selector=f"{service_label_key}={service_label}"   # -> opentelemetry.io/name=unknown
   ```
   Không pod nào mang nhãn `opentelemetry.io/name=unknown`, nên hàm này **luôn trả False**.
4. → verify luôn hết giờ → luôn FAIL → `breaker.record_failure()` cộng dồn.

### Hậu quả vận hành

Sau **3 lần** như vậy, circuit breaker mở cho khoá `oom-detected:unknown` và **từ chối
remediate**, kèm alert `critical` báo *"đã fail liên tiếp quá 3 lần"* — trong khi thực tế cả
3 lần đều **thành công trong 2 giây**.

Nặng hơn: mọi pod thiếu nhãn đều dùng **chung một khoá** `oom-detected:unknown`. Nên 3 sự cố
ở **ba service khác nhau** cũng đủ mở một breaker chặn **tất cả** chúng.

Đo trên cụm 28/07:

| | |
|---|---|
| Tổng pod trong `techx-tf1` | 57 |
| Pod **thiếu** nhãn `opentelemetry.io/name` | **16 (28%)** |
| Gồm | `prometheus`, `grafana`, `jaeger`, `opensearch`, `otel-collector`, `kube-state-metrics`, và chính `aiops-detector` + `aiops-remediation` |

Tức vòng tự dập hỏng đúng trên **toàn bộ tầng observability** và trên chính nó.

Đây cũng là lời giải cho `service: "unknown"` trong alert `oom-detected` quan sát được sáng
28/07 — cùng một gốc: nhãn `opentelemetry.io/name` không phổ quát như code giả định.

### Hướng sửa (không làm trong ticket này)

`is_service_ready()` không nên tra bằng label selector. Nó nên nhận **ownerReference** của
pod cũ (ReplicaSet → Deployment) và hỏi đúng workload đó, hoặc tối thiểu là bỏ qua readiness
gate khi `service_label == "unknown"` thay vì chờ vô ích rồi báo fail.

---

## 6. Một khiếm khuyết nữa phát hiện khi đọc code, chưa dựng phép đo riêng

`verify_oom_recovery()` gọi `find_oom_pods(namespace, ...)` **trên toàn namespace**, rồi chỉ
loại pod cũ theo **tên**:

```python
new_oom = find_oom_pods(core_v1, namespace, service_label_key, since_seconds=...)
new_oom = [p for p in new_oom if p["pod_name"] != old_pod_name]
if new_oom:
    return False
```

Nghĩa là **nếu bất kỳ pod nào khác trong `techx-tf1` OOM trong cửa sổ verify, verify của
service đang xét sẽ FAIL** — dù hai service không liên quan gì nhau. Trên cụm này điều đó
không hiếm: `jaeger` OOM đều đặn ~39 phút/lần.

Hệ quả: một lần remediate **thành công** có thể bị chấm là thất bại chỉ vì hàng xóm OOM, và
ba lần như vậy sẽ mở circuit breaker oan.

Chưa dựng phép đo riêng cho khiếm khuyết này (cần dàn dựng hai pod OOM lệch pha nhau có kiểm
soát). Ghi lại để không rơi mất — đây là bug thật, không phải suy đoán.

---

## 7. Bảng kết luận cho 3 ngưỡng

| Ngưỡng | Đang ship | Đo được | Kiến nghị |
|---|---|---|---|
| `verify.duration_seconds` | 120s | thực tế **124.2s**; và với OOM lặp thì **không bao giờ chạm tới** (thoát ở 43.0s) | Giữ 120s. Nhưng ghi vào doc rằng ngưỡng thực = `duration + 1 poll`, và rằng nhánh chi phối là "OOM mới" chứ không phải timeout |
| `circuit_breaker` 3 fail / 24h | 3 / 86400s | logic **đúng**, nhưng **không với tới được** với blast radius hiện tại (≥2h) và reset khi pod restart | Sửa `blast_radius` trước (xem dưới). Cân nhắc đưa `_fail_count` ra ngoài RAM |
| `blast_radius` 1 / 3600s / namespace | 1 / 3600s | chặn đúng như thiết kế, nhưng khiến breaker bất khả thi **và** (TF1-106) khiến MTTR trung bình chỉ cải thiện 2.7% | **Đổi**: hạn mức theo *service* thay vì *namespace*, và nới `max_actions` cho cùng một sự cố kéo dài |

---

## 8. Tái tạo

```bash
kubectl apply -f report/mandate22-thresholds/canary-oom.yaml       # ca verify FAIL "OOM moi"
kubectl create configmap tf1107-policy -n techx-tf1 \
  --from-file=policy.yaml=report/mandate22-thresholds/policy-test.yaml
kubectl apply -f report/mandate22-thresholds/runner.yaml
kubectl logs -n techx-tf1 -l app=tf1107-runner -f

kubectl apply -f report/mandate22-thresholds/canary-unready.yaml   # ca verify FAIL "het gio"
```

Dọn dẹp — **bắt buộc chạy sau khi đo xong**:

```bash
kubectl -n techx-tf1 delete -f report/mandate22-thresholds/runner.yaml
kubectl -n techx-tf1 delete -f report/mandate22-thresholds/canary-oom.yaml
kubectl -n techx-tf1 delete -f report/mandate22-thresholds/canary-unready.yaml
kubectl -n techx-tf1 delete configmap tf1107-policy
```

Log thô: `runner.log`, `runner-timeout.log`, `runner-jaeger.log` · số đã tính:
`result-breaker.txt` · trạng thái trước khi đo: `pre-state.txt`

---

## 9. Điều chưa làm được, nói rõ

- **Chưa đo trên service production thật.** Hai trong ba ca dùng pod mồi. Chúng chứng minh
  được **cơ chế** (verify fail, breaker đếm, blast radius chặn) chứ không chứng minh được
  hành vi của một service đang phục vụ khách. Ca verify PASS dùng `jaeger` — OOM thật nhưng
  cũng là thành phần hạ tầng, không phải service nghiệp vụ.
- **Ca verify PASS chưa đo được** — bị chính lỗi ở mục 5 chặn. Muốn đo được phải sửa
  `is_service_ready()` trước, hoặc chọn một service CÓ nhãn `opentelemetry.io/name` mà OOM
  thật (hiện không có service nào như vậy đang OOM trên cụm).
- **Chưa dựng phép đo cho khiếm khuyết ở mục 6.**
- **Chưa sửa `blast_radius`.** Ticket này là *validate*, không phải *sửa*. Hai nguồn bằng
  chứng độc lập (TF1-106 và bản này) đều chỉ vào nó — việc sửa nên đi PR riêng có backtest.
- **`error_budget_check` không được kiểm ở đây.** TF1-106 đã ghi nó **thất bại mở**
  (fail-open); bản này không lặp lại phép đo đó.
