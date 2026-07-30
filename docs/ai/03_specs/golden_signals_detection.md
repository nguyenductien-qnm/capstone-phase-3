# Spec: Golden Signals Anomaly Detection (Latency & Error Rate)

> **Phạm vi:** Tài liệu này đặc tả tầng **phát hiện** (detection) — TF1-49.
> Vòng xử lý khép kín (dry-run → blast-radius → verify → rollback) thuộc TF1-50,
> đặc tả tại [`anomaly_remediation.md`](anomaly_remediation.md). Không lặp lại ở đây.

> **⚠️ Cập nhật 2026-07-24 — phương pháp thật KHÔNG phải EWMA:** tài liệu này (bản
> spec gốc TF1-49) mô tả EWMA α=0.2 xuyên suốt bên dưới, nhưng code thật
> (`aiops/detector/detector.py`) triển khai **rolling-window 3-sigma** (mean/std trên
> 30 mẫu gần nhất theo `rule_id:service`), không phải EWMA. Đây là quyết định có chủ
> đích, đã ghi trong **ADR-012** (`05_adrs.md`, phần "Alternatives considered") — EWMA
> bị defer sang `#7b`/TF1-71 vì cần backtest ≥24h dữ liệu Prometheus thật trước khi
> chọn α có căn cứ. Pseudocode EWMA bên dưới giữ nguyên làm tài liệu tham khảo cho
> hướng nâng cấp tương lai, KHÔNG phản ánh hành vi hiện tại của detector — đọc
> `detector.py`/ADR-012 để biết phương pháp đang chạy thật.

## 1. Mục tiêu & Phạm vi

Soạn thảo đặc tả kỹ thuật giám sát hai tín hiệu vàng (Golden Signals) của hệ thống storefront:
- **Latency (p95):** SLO cam kết < 1s.
- **Error Rate (HTTP 5xx):** Tỷ lệ lỗi backend.

Sau B1, detector đang dùng **hybrid static threshold + rolling SMA 3σ**. Kế hoạch
EWMA ban đầu (alpha = 0.2, threshold = 3σ) vẫn được giữ lại làm phương án đối
chứng; chưa phải thuật toán đang chạy.

---

## 2. Golden Signals — Monitored Metrics

| Signal | Metric | SLO / Alert Threshold | Detection Method |
|---|---|---|---|
| **Latency** | `http_request_duration_seconds` (p95) | SLO: < 1s | Static SLO threshold OR rolling SMA 3σ |
| **Error Rate** | `http_requests_total{status=~"5.."}` / tổng requests | SLO threshold theo từng rule | Static SLO threshold OR rolling SMA 3σ |

---

## 3. Trạng thái triển khai sau B1 — rolling SMA 3σ

`aiops/detector/detector.py::eval_metric_rule` hiện triển khai hai lớp cho mỗi
metric rule:

1. **Static:** so sánh giá trị hiện tại với `threshold` trong `rules.yaml`.
2. **Dynamic:** so sánh giá trị hiện tại với trung bình cộng và độ lệch chuẩn
   của lịch sử gần nhất. Alert được phát khi **static OR dynamic** fire.

| Thuộc tính | Runtime hiện tại |
|---|---|
| Baseline | Trung bình cộng đơn giản (SMA) theo từng `rule_id × service` |
| Warm-up | Tối thiểu 5 mẫu lịch sử trước khi bật dynamic detection |
| Cửa sổ | Tối đa 30 mẫu; tăng dần khi warm-up, sau đó rolling FIFO |
| Ngưỡng | `mean + 3σ` với rule `gt`; `mean - 3σ` với rule `lt` |
| Độ lệch chuẩn | Population standard deviation trên cửa sổ lịch sử |
| Chống nhiễu rất nhỏ | Độ lệch tuyệt đối phải lớn hơn `0.001` |
| Thứ tự cập nhật | So sánh mẫu hiện tại trước, rồi mới thêm mẫu đó vào history |
| State | In-memory; baseline được học lại khi process restart |

Với poll interval 30 giây, cửa sổ đủ 30 mẫu tương đương khoảng 15 phút. Runtime
không có phép tính lũy thừa theo thời gian và không có tham số `alpha`, vì vậy
không được gọi là EWMA. `evaluate_detector.py` mô phỏng cùng họ thuật toán SMA
3σ và cửa sổ 30 mẫu, nhưng đang dùng guard `0.01` thay vì `0.001`; cần đồng bộ
guard trước khi dùng script để so sánh định lượng với runtime.

### 3.1 Quyết định tạm thời và tiêu chí chọn SMA hay EWMA

Hiện tại giữ **SMA 3σ** vì đây là thuật toán đã được triển khai, test và đủ đơn
giản cho baseline univariate hiện tại. **EWMA không bị loại bỏ**: alpha = 0.2
vẫn là ứng viên từ kế hoạch gốc ở Section 4.

Khi có tối thiểu 24–48 giờ metric Prometheus thật và các khoảng sự cố/chaos có
nhãn, replay cùng một dataset qua SMA và EWMA. So sánh precision, recall, false
positive rate, MTTD và độ ổn định khi traffic thay đổi; sau đó mới quyết định
thuật toán dynamic nào được dùng. Lớp static bám SLO vẫn được giữ trong cả hai
phương án.

---

## 4. Kế hoạch gốc — Detection Configuration (EWMA, giữ lại để đối chứng)

Phần này giữ nguyên thiết kế EWMA ban đầu và code mẫu để phục vụ backtest trong
tương lai. Đây là **candidate design**, không mô tả runtime hiện tại.

### 4.1 p95 Latency — EWMA Detection

Theo dõi `http_request_duration_seconds` (p95) qua thuật toán EWMA để phát hiện **gradual degradation**.

**Tham số EWMA:**

| Tham số | Giá trị | Lý do chọn |
|---|---|---|
| `alpha` | **0.2** | p95 latency storefront có variance cao trong giờ cao điểm — α thấp hơn mức mặc định 0.3 để baseline nhớ xa hơn, giảm false alarm. Phù hợp detect **gradual degradation** (ví dụ: connection pool cạn dần, memory leak), không phải sudden spike. |
| `threshold` | **3.0 σ** | ~0.3% false-positive rate với phân phối chuẩn công nghiệp. |
| Scrape interval | **15s** | Đủ granular để bắt degradation trong vòng 2–3 phút. |

**Giới hạn & Bù đắp:**
- α = 0.2 cần ~12–15 data points liên tục deviate mới trigger alert.
- Sudden spike (p95 vọt lên đột ngột trong 1–2 scrape) được bắt bởi Prometheus rule riêng (xem Section 4.3).

**Implementation:**

```python
import pandas as pd
import numpy as np


def detect_latency_anomaly(series: pd.Series, alpha: float = 0.2, threshold: float = 3.0) -> pd.Series:
    """
    Phát hiện latency anomaly bằng EWMA.
    
    Args:
        series: p95 latency values (pd.Series, indexed by timestamp).
        alpha: smoothing factor (0.2 cho storefront).
        threshold: std deviation threshold (mặc định 3σ).
    
    Returns:
        pd.Series[bool] — True tại các điểm anomaly.
    """
    ewma_mean = series.ewm(alpha=alpha, adjust=False).mean()
    ewma_std = series.ewm(alpha=alpha, adjust=False).std().replace(0, 1e-10)
    return (np.abs(series - ewma_mean) / ewma_std) > threshold
```

### 4.2 HTTP 5xx Error Rate — EWMA Detection

Theo dõi tỷ lệ lỗi HTTP 5xx qua EWMA để phát hiện **gradual increase** trong error rate.

**Tham số EWMA:**

| Tham số | Giá trị | Lý do chọn |
|---|---|---|
| `alpha` | **0.2** | Cùng lý do latency — giảm false alarm từ transient errors. |
| `threshold` | **3.0 σ** | ~0.3% false-positive rate. |
| Scrape interval | **15s** | Theo latency. |

**Lưu ý:**
- Error rate baseline phụ thuộc vào traffic volume — EWMA tự động normalize qua std deviation.
- Ví dụ: nếu baseline error rate = 0.05% ± 0.02% (1σ), thì alert trigger khi error rate > 0.11% (baseline + 3σ).

**Implementation:**

```python
def detect_error_rate_anomaly(series: pd.Series, alpha: float = 0.2, threshold: float = 3.0) -> pd.Series:
    """
    Phát hiện error rate anomaly bằng EWMA.
    
    Args:
        series: error rate values in [0, 1] (e.g., 0.01 = 1%), indexed by timestamp.
        alpha: smoothing factor.
        threshold: std deviation threshold.
    
    Returns:
        pd.Series[bool] — True tại các điểm anomaly.
    """
    ewma_mean = series.ewm(alpha=alpha, adjust=False).mean()
    ewma_std = series.ewm(alpha=alpha, adjust=False).std().replace(0, 1e-10)
    return (np.abs(series - ewma_mean) / ewma_std) > threshold
```

### 4.3 Complementary Prometheus Rules — Bắt Sudden Spikes

EWMA chậm (cần 12–15 data points) → cần rule Prometheus để bắt sudden spike:

```yaml
# prometheus-rules.yaml
groups:
  - name: storefront.golden_signals
    rules:
      # Rule 1: p95 latency SLO breach — sudden spike
      - alert: StorefrontLatencySLOBreach
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{service="storefront"}[5m])) by (le)
          ) > 1.0
        for: 2m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Storefront p95 latency vượt SLO 1s"
          description: "p95 = {{ $value | humanizeDuration }} (SLO: < 1s)"

      # Rule 2: HTTP 5xx error rate threshold breach
      - alert: StorefrontHighErrorRate
        expr: |
          (sum(rate(http_requests_total{service="storefront", status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total{service="storefront"}[5m])))
          > 0.01
        for: 5m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Storefront HTTP 5xx rate > 1%"
          description: "Error rate = {{ $value | humanizePercentage }}"
```

**Giải thích:**
- **Rule 1:** Latency > 1s (SLO) trong 2 phút → alert. Bắt sudden spike mà EWMA chưa kịp detect.
- **Rule 2:** Error rate > 1% trong 5 phút → alert. Ngưỡng 1% được chọn vì:
  - Thường xuyên error rate < 0.1% (healthy state).
  - 1% tương đương ~1 lỗi per 100 requests → đáng để alert.
  - Balance giữa bắt real issues vs. false alarm từ transient failures.

---

## 5. Safety Considerations for Detection

### 5.1 Preventing False Positives

Detection là tín hiệu đầu vào cho alert/remediation, nên false positive vẫn có
chi phí cao. Trạng thái và chiến lược hiện tại:

- **Hybrid hiện tại:** static SLO threshold OR rolling SMA 3σ. Detector phát
  alert khi một trong hai lớp fire; nó không yêu cầu hai lớp cùng đồng ý.
- **EWMA tương lai:** chỉ thay lớp dynamic SMA nếu backtest trên cùng dataset
  chứng minh trade-off tốt hơn; không thay lớp static bám SLO.
- **Threshold tuning:** 3σ và cửa sổ 30 mẫu là cấu hình hiện tại; alpha = 0.2
  chỉ thuộc candidate EWMA, chưa phải tham số runtime.
- **Verification buffer:** Remediation engine chỉ confirm recovery khi p95 < 800ms (buffer 200ms so với SLO 1s) — tránh flip-flopping ở edge.

### 5.2 Blast-radius Awareness

Detection spec phải biết rằng:
- Mỗi anomaly alert có thể trigger max 1 pod restart/namespace/giờ (an control layer constraint).
- 3 lần remediation thất bại liên tiếp → circuit breaker opens → page on-call (human takes over).
- Detection phải có độ specificity đủ cao để tránh cascading false restarts.

---

## 6. Tóm tắt Detection Strategy

| Trạng thái | Detection Method | Tham số | Vai trò |
|---|---|---|---|
| **Đang chạy** | Static threshold | Theo `rules.yaml` và SLO | Bắt vi phạm ngưỡng tuyệt đối |
| **Đang chạy** | Rolling SMA 3σ | warm-up=5, window=30, threshold=3σ | Bắt lệch baseline theo từng rule × service |
| **Ứng viên** | EWMA | α=0.2, threshold=3σ, interval=15s trong kế hoạch gốc | Đối chứng khả năng bắt gradual degradation |

**Quyết định hiện tại:** dùng static OR SMA 3σ. Khi đủ dữ liệu thật, so sánh SMA
với EWMA trên cùng tập dữ liệu và chọn một phương pháp cho lớp dynamic dựa trên
FP/recall/MTTD; không chọn trước theo claim trong tài liệu.


---

## Phụ lục kiểm chứng 12/07/2026 — MTTD đo thật + lỗ hổng burn-rate

**Số đo pipeline detection** (compose stack, chaos qua flagd, script `docs/ai/evals/measure_detection_pipeline.py`): ingest lag P50 2.1s/max 5.1s; sự cố → phrase thấy được trên OpenSearch P50 5.1s; **MTTD poll 30s: mean ~19.6s, max ~35.4s**; chi phí 1 query detector 5ms P50 → vùng poll hợp lệ theo error budget SLO: **[10s, 60s]**, 30s giữ nguyên là quyết định có số.

**Lỗ hổng theo nguyên tắc giáo trình AIOps course** (*"Never alert on raw error rate — use multi-window multi-burn-rate"*): rule error-rate hiện là single-window 5m raw threshold → (a) page vì blip khi budget 24h còn nguyên, (b) **ngủ quên trước slow burn** (0.4% cả ngày = đốt 80% budget, không alert). Đã thêm rule DRAFT `error-budget-burn-fast` (14.4× ở cả 5m và 1h) + `memory-saturation-high` (>85% limit — leading indicator cho lớp OOM/INC-2) vào `rules.yaml` — **phải verify PromQL trên Prometheus sống trước khi tin**.

**FP run 15 phút tải thật:** rule `latency-p95-high` bắn nhầm vào `flagd` (4.87s, không thuộc SLO nào) — query cần filter service thuộc SLO; rule 429 từng bắn với nhãn sai bản chất khi lỗi thật là thiếu creds → code đã chuyển sang marker `AI_SUMMARY_FALLBACK reason=<type>`, rule `genai-assistant-failure` match marker này. `min_count` db-pool/dns đổi 3→1, window 5→10m (giáo trình: "missing an incident is a zero — recall dominates").

## Phụ lục 2 (12/07 chiều) — semantics verify bằng chaos thật + lỗ hổng tầng gRPC

Thí nghiệm: bật `productCatalogFailure` trên compose, traffic locust chạy nền, đọc Prometheus sống.

**Phát hiện quan trọng: sự cố này KHÔNG sinh HTTP 5xx** — chỉ hiện ở tầng gRPC (`rpc_server_duration_milliseconds_count{rpc_grpc_status_code="13"}`, đo được error-ratio product-catalog = **6.6%**), trong khi `http_server_request_duration_seconds_count` chỉ có mã 200 chảy. Hệ quả: **mọi rule error-rate dựa HTTP (cả rule cũ lẫn burn-rate draft) mù với lớp sự cố gRPC-layer.** Đã thêm rule `grpc-error-rate-high` (threshold 5%) — **semantics verified trên data sống** (fire đúng dưới chaos, im lặng trước đó).

Trạng thái verify từng rule metric:
| Rule | Parse | Semantics |
|---|---|---|
| latency/error-rate/checkout/genai-latency | ✅ | ✅ hoạt động từ FP-run + latency đã fire thật |
| `grpc-error-rate-high` (mới) | ✅ | ✅ **verified chaos 12/07** |
| `error-budget-burn-fast` | ✅ | ⚠️ chưa fire được ở local vì chưa tạo được HTTP 5xx thật — verify tiếp trên EKS hoặc chaos khác sinh 5xx |
| `memory-saturation-high` | ✅ | ⏳ compose không có kube-state-metrics/cadvisor (0 series — đúng kỳ vọng, không FP); **EKS bắt buộc cài kube-state-metrics** để rule sống |

## Phụ lục 3 — bảng sensitivity poll↔MTTD (đo 12/07, migrate từ review)

| Poll | MTTD max (đo/suy từ delay đo được + U(0,P)) | Chi phí query (5ms/query đo được) | Verdict theo target ≤2 phút |
|---|---|---|---|
| 10s | 15.4s | ~0.25% duty | Pass — biên tối đa |
| **30s (hiện tại)** | **35.4s** | ~0.08% | **Pass biên 3.4× — giữ** |
| 60s | 65.4s | ~0.04% | Pass — dùng nếu cần giảm tải backend log |
| 120s | 125.4s | ~0.02% | Chạm biên — loại |

Nếu mentor đổi target: ≤1 phút → poll ≤30s vẫn pass; ≤30s → poll 10s pass (max 15.4s); <10s → không đạt bằng chỉnh poll, phải giảm sàn ingest 2.1s (collector batch/refresh) — bài toán khác. Sàn dưới poll 10s: xem 05_adrs Sổ đăng ký (vòng detector tuần tự + query timeout 5s từng quan sát được).


## Phụ lục 4 (13/07) — trạng thái kiểm chứng 4 tham số detector

Trả lời "poll 30s / window 5m / min_count 1–3 / cooldown 600s — đã đo chưa, có cần vậy không":

| Tham số | Trạng thái | Đánh giá bản chất |
|---|---|---|
| **poll 30s** | ✅ ĐO (MTTD max 35.4s, sensitivity [10,60]s, query 5ms) | Cần & verified. Giữ 30s. |
| **min_count** | ⚠️ Đã hạ hết về **1** (K2 recall-dominates); FP-run 15′ = 0 FP | "1–3" co về "1" — **không cần giá trị 3**. Sự cố hiếm-nghiêm-trọng: mọi lần xuất hiện = incident. |
| **window 5m/10m** | ❌ Chưa đo FP theo window | Lookback thô. 5m default, 10m cho db-pool/dns bù min_count=1. |
| **cooldown 600s** | ❌ Chưa đo — convention | Chống re-page mỗi poll; bớt tối quan trọng khi có dedup (TF1-70). |

**Kế hoạch đo cuối (TF1-71 trên EKS):** FP-run 24h dưới tải thật → tune window/cooldown bằng số FP + tần suất page chấp nhận được, thay convention. Trước đó: window/cooldown giữ nguyên với nhãn assumption, không trình như số đo.
