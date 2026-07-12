# Spec: Golden Signals Anomaly Detection (Latency & Error Rate)

> **Phạm vi:** Tài liệu này đặc tả tầng **phát hiện** (detection) — TF1-49.
> Vòng xử lý khép kín (dry-run → blast-radius → verify → rollback) thuộc TF1-50,
> đặc tả tại [`anomaly_remediation.md`](anomaly_remediation.md). Không lặp lại ở đây.

## 1. Mục tiêu & Phạm vi

Soạn thảo đặc tả kỹ thuật giám sát hai tín hiệu vàng (Golden Signals) của hệ thống storefront:
- **Latency (p95):** SLO cam kết < 1s.
- **Error Rate (HTTP 5xx):** Tỷ lệ lỗi backend.

Sử dụng EWMA (alpha = 0.2, threshold = 3σ) để lọc nhiễu và chuyển đổi time-series metrics thô thành tín hiệu bất thường thật sự.

---

## 2. Golden Signals — Monitored Metrics

| Signal | Metric | SLO / Alert Threshold | Detection Method |
|---|---|---|---|
| **Latency** | `http_request_duration_seconds` (p95) | SLO: < 1s · Alert: EWMA deviation > 3σ | EWMA + Prometheus rule |
| **Error Rate** | `http_requests_total{status=~"5.."}` / tổng requests | Alert: > 1% trong 5 phút | Prometheus rule + EWMA |

---

## 3. Detection Configuration (EWMA)

### 3.1 p95 Latency — EWMA Detection

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

### 3.2 HTTP 5xx Error Rate — EWMA Detection

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

### 3.3 Complementary Prometheus Rules — Bắt Sudden Spikes

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

## 4. Safety Considerations for Detection

### 4.1 Preventing False Positives

Vì bất kỳ anomaly detection nào cũng kích hoạt remediation tự động, chi phí của false positive cao. Chiến lược:

- **Dual detection:** EWMA (sensitive to trends) + Prometheus rule (fast spike catch). Chỉ trigger remediation khi cả hai đồng ý hoặc escalate to on-call.
- **Threshold tuning:** α = 0.2, threshold = 3σ được chọn để minimize false alarm từ giờ cao điểm traffic spikes.
- **Verification buffer:** Remediation engine chỉ confirm recovery khi p95 < 800ms (buffer 200ms so với SLO 1s) — tránh flip-flopping ở edge.

### 4.2 Blast-radius Awareness

Detection spec phải biết rằng:
- Mỗi anomaly alert có thể trigger max 1 pod restart/namespace/giờ (an control layer constraint).
- 3 lần remediation thất bại liên tiếp → circuit breaker opens → page on-call (human takes over).
- Detection phải có độ specificity đủ cao để tránh cascading false restarts.

---

## 5. Tóm tắt Detection Strategy

| Metric | Detection Method | Tham số | Tác dụng |
|---|---|---|---|
| **p95 Latency** | EWMA | α=0.2, threshold=3σ, interval=15s | Bắt gradual degradation (trend shift) |
| **p95 Latency** | Prometheus rule | threshold > 1s, for=2m | Bắt sudden spike |
| **Error Rate** | EWMA | α=0.2, threshold=3σ, interval=15s | Bắt gradual increase trong error rate |
| **Error Rate** | Prometheus rule | threshold > 1%, for=5m | Bắt sudden spike / threshold breach |

**Lý do dual detection:**
- EWMA: nhạy với trend, bắt được degradation dần dần.
- Prometheus rule: phản ứng nhanh, bắt spike đột ngột.
- Cùng nhau: coverage đầy đủ cho cả 2 loại anomaly, đồng thời giảm false alarm bằng cách yêu cầu confirmation.


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
