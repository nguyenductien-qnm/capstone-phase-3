# Spec: Golden Signals Anomaly Detection (Latency & Error Rate)

> **Phạm vi:** Tài liệu này đặc tả tầng **phát hiện** (detection) — TF1-49.
> Vòng xử lý khép kín (dry-run → blast-radius → verify → rollback) thuộc TF1-50,
> đặc tả tại [`anomaly_remediation.md`](anomaly_remediation.md). Không lặp lại ở đây.

## 1. Mục tiêu & Phạm vi

Soạn thảo đặc tả kỹ thuật giám sát hai tín hiệu vàng (Golden Signals) của hệ thống storefront:
- **Latency (p95):** SLO cam kết < 1s.
- **Error Rate (HTTP 5xx):** Tỷ lệ lỗi backend.

Sử dụng **SMA 3σ** (Simple Moving Average trên cửa sổ trượt 30 mẫu, threshold = 3σ) để lọc nhiễu và chuyển đổi time-series metrics thô thành tín hiệu bất thường thật sự. *(Đính chính 21/07: spec ban đầu ghi EWMA α=0.2 — sai so với code runtime. `detector.py` và `evaluate_detector.py` dùng SMA đơn giản: `mean = sum(history[-30:]) / len(history[-30:])`, không có hệ số alpha. Xem chi tiết §3.)*

---

## 2. Golden Signals — Monitored Metrics

| Signal | Metric | SLO / Alert Threshold | Detection Method |
|---|---|---|---|
| **Latency** | `http_request_duration_seconds` (p95) | SLO: < 1s · Alert: SMA deviation > 3σ | SMA 3σ + Prometheus rule |
| **Error Rate** | `http_requests_total{status=~"5.."}` / tổng requests | Alert: > 1% trong 5 phút | Prometheus rule + SMA 3σ |

---

## 3. Detection Configuration (SMA 3σ)

> **Đính chính 21/07:** Spec phiên bản trước mô tả EWMA với `alpha = 0.2` — đây là thuật toán không được triển khai trong code. Runtime thực tế (`detector.py:55–76`, `evaluate_detector.py`) dùng **SMA đơn giản** trên cửa sổ trượt 30 mẫu. Spec này đã được cập nhật để khớp code.

### 3.1 p95 Latency — SMA 3σ Detection

Theo dõi `http_request_duration_seconds` (p95) qua thuật toán SMA 3σ để phát hiện **gradual degradation**.

**Tham số SMA:**

| Tham số | Giá trị | Lý do chọn |
|---|---|---|
| `window` | **30 mẫu** | Cửa sổ đủ rộng để baseline ổn định; tương đương ~7.5 phút với scrape 15s. |
| `min_history` | **5 mẫu** | Số mẫu tối thiểu trước khi bắt đầu tính dynamic threshold. |
| `threshold` | **3.0 σ** | ~0.3% false-positive rate với phân phối chuẩn; canon SPC (L=3 theo Montgomery/NIST). |
| Scrape interval | **15s** | Đủ granular để bắt degradation trong vòng 2–3 phút. |

**Giới hạn & Bù đắp:**
- SMA phản ứng chậm với drift dài hạn (baseline tự trượt theo) — bắt được gradual degradation nhờ variance tăng dần trước khi mean dịch chuyển hẳn.
- Sudden spike (p95 vọt lên đột ngột trong 1–2 scrape) được bắt bởi Prometheus rule riêng (xem §3.3).

**Implementation (khớp `detector.py`):**

```python
def detect_latency_anomaly(history: list[float], new_value: float, threshold: float = 3.0) -> bool:
    """
    Phát hiện latency anomaly bằng SMA 3σ — khớp detector.py runtime.

    Args:
        history: danh sách giá trị lịch sử (tối đa 30 mẫu gần nhất).
        new_value: giá trị p95 latency mới nhất.
        threshold: std deviation threshold (mặc định 3σ).

    Returns:
        True nếu new_value lệch > threshold × std_dev so với mean.
    """
    if len(history) < 5:
        return False
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std_dev = variance ** 0.5
    dynamic_th = mean + threshold * std_dev
    return new_value > dynamic_th and (new_value - mean) > 0.001
```

### 3.2 HTTP 5xx Error Rate — SMA 3σ Detection

Theo dõi tỷ lệ lỗi HTTP 5xx qua SMA 3σ để phát hiện **gradual increase** trong error rate.

**Tham số SMA:**

| Tham số | Giá trị | Lý do chọn |
|---|---|---|
| `window` | **30 mẫu** | Cùng latency — consistency giữa 2 signal. |
| `threshold` | **3.0 σ** | ~0.3% false-positive rate. |
| Scrape interval | **15s** | Theo latency. |

**Lưu ý:**
- Error rate baseline phụ thuộc vào traffic volume — SMA 3σ tự normalize qua std deviation.
- Ví dụ: nếu baseline error rate = 0.05% ± 0.02% (1σ), thì alert trigger khi error rate > 0.11% (baseline + 3σ).

**Implementation:**

```python
def detect_error_rate_anomaly(history: list[float], new_value: float, threshold: float = 3.0) -> bool:
    """
    Phát hiện error rate anomaly bằng SMA 3σ — khớp detector.py runtime.

    Args:
        history: danh sách giá trị lịch sử error rate (tối đa 30 mẫu).
        new_value: error rate mới nhất trong [0, 1].
        threshold: std deviation threshold.

    Returns:
        True nếu new_value lệch > threshold × std_dev so với mean.
    """
    if len(history) < 5:
        return False
    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std_dev = variance ** 0.5
    dynamic_th = mean + threshold * std_dev
    return new_value > dynamic_th and (new_value - mean) > 0.001
```

### 3.3 Complementary Prometheus Rules — Bắt Sudden Spikes

SMA 3σ cần ≥5 mẫu lịch sử và phản ứng chậm với spike đột ngột → cần rule Prometheus để bắt nhanh:

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
- **Rule 1:** Latency > 1s (SLO) trong 2 phút → alert. Bắt sudden spike mà SMA 3σ chưa kịp detect (cần ≥5 mẫu lịch sử).
- **Rule 2:** Error rate > 1% trong 5 phút → alert. Ngưỡng 1% được chọn vì:
  - Thường xuyên error rate < 0.1% (healthy state).
  - 1% tương đương ~1 lỗi per 100 requests → đáng để alert.
  - Balance giữa bắt real issues vs. false alarm từ transient failures.

---

## 4. Safety Considerations for Detection

### 4.1 Preventing False Positives

Vì bất kỳ anomaly detection nào cũng kích hoạt remediation tự động, chi phí của false positive cao. Chiến lược:

- **Dual detection:** SMA 3σ (sensitive to trends) + Prometheus rule (fast spike catch). Chỉ trigger remediation khi cả hai đồng ý hoặc escalate to on-call.
- **Threshold tuning:** window=30, threshold=3σ được chọn để minimize false alarm từ giờ cao điểm traffic spikes.
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
| **p95 Latency** | SMA 3σ | window=30, min_history=5, threshold=3σ, interval=15s | Bắt gradual degradation (trend shift) |
| **p95 Latency** | Prometheus rule | threshold > 1s, for=2m | Bắt sudden spike |
| **Error Rate** | SMA 3σ | window=30, min_history=5, threshold=3σ, interval=15s | Bắt gradual increase trong error rate |
| **Error Rate** | Prometheus rule | threshold > 1%, for=5m | Bắt sudden spike / threshold breach |

**Lý do dual detection:**
- SMA 3σ: nhạy với trend, bắt được degradation dần dần khi variance tăng.
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
