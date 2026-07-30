# Spec: Model Gateway & A/B Testing cho LLM (Hạng mục Đua Top)

> **Trạng thái:** Implemented  
> **Trụ:** Performance Efficiency / Cost Optimization / Reliability  
> **Ngày:** 2026-07-09  
> **Tác giả:** Nhóm AI (AIO03) - TF1  
> **ADR liên quan:** ADR-010  

---

## 1. Bối cảnh & Vấn đề

### 1.1 Thực trạng hiện tại

Service `llm` (`src/llm/`) gọi trực tiếp AWS Bedrock từ Python code:

```python
# Gọi cứng một model duy nhất
response = bedrock_client.invoke_model(
    modelId=os.environ.get('LLM_MODEL_ID', 'amazon.nova-lite-v1:0'),
    body=payload
)
```

**Hạn chế:**
- **Không có A/B testing:** Muốn so sánh Nova Lite vs Nova Pro phải thay ENV và redeploy cả pod.
- **Không có metrics per-model:** Không biết model nào tốt hơn (chất lượng, latency, cost).
- **Không có canary deployment:** Muốn test model mới phải all-or-nothing.
- **Không có shadow testing:** Không thể chạy model mới song song để so sánh output.

### 1.2 Yêu cầu từ RULES.md

> Line 66: **Mở rộng (đua top):** [...] model gateway + A/B khi đổi model.

---

## 2. Phương án đã đánh giá

### 2.1 Option A: Python Gateway + OpenFeature/flagd ⭐ **CHỌN**

**Kiến trúc:**
```
Request arrives
      │
      ▼
┌─────────────────────────────────┐
│  LLM Service (Python)           │
│                                 │
│  ┌───────────────────────────┐  │
│  │  Model Router (Gateway)   │  │
│  │                           │  │
│  │  1. Evaluate flagd flag   │──────► flagd
│  │     "llmModelRouting"     │◄────── { model: "nova-lite", weight: 80% }
│  │                           │        { model: "nova-pro",  weight: 20% }
│  │  2. Select model based    │  │
│  │     on flag variant       │  │
│  │                           │  │
│  │  3. Call Bedrock with     │──────► AWS Bedrock
│  │     selected model        │◄────── response
│  │                           │  │
│  │  4. Emit OTel metrics     │──────► Prometheus
│  │     tagged with model_id  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**Ưu điểm:**
- **Zero infrastructure thêm:** Reuse `flagd` đã chạy trên EKS (đã có trong demo stack).
- **Dynamic traffic split:** Thay đổi phân bổ traffic bằng cách cập nhật file JSON flag → không cần redeploy.
- **Native OTel integration:** Metrics đã có sẵn, chỉ cần thêm tag `model_id`.
- **Gradual rollout:** Bắt đầu 5% traffic cho model mới → tăng dần lên 100%.

**Nhược điểm:**
- Coupled với application code (không phải sidecar/proxy pattern).

### 2.2 Option B: LiteLLM Proxy

**Kiến trúc:** Deploy LiteLLM container trên EKS, cấu hình routing qua `config.yaml`.

**Ưu điểm:**
- Feature-rich: load balancing, fallback, rate limiting, cost tracking.
- OpenAI-compatible API.

**Nhược điểm:**
- **Thêm 1 microservice** phải deploy, monitor, và maintain trên EKS.
- **Overhead network hop** (service → litellm → bedrock).
- **Overkill** cho hệ thống chỉ dùng 2-3 models trên cùng 1 provider (Bedrock).

**Kết luận:** ❌ Loại — thêm complexity không cần thiết.

### 2.3 Option C: AWS API Gateway + Lambda

**Kiến trúc:** Request → API Gateway → Lambda (routing logic) → Bedrock.

**Nhược điểm:**
- **Unnecessary network hop** cho internal EKS service.
- **Cold start** của Lambda thêm ~200ms.
- **Chi phí:** API Gateway + Lambda invocations.

**Kết luận:** ❌ Loại — không phù hợp cho internal service-to-service communication.

### 2.4 Option D: Envoy Proxy Sidecar

**Kiến trúc:** Envoy proxy sidecar trước LLM service, custom filter cho model routing.

**Nhược điểm:**
- **Complexity quá cao** cho 3-week capstone.
- Envoy custom filter development cần C++ hoặc WASM.

**Kết luận:** ❌ Loại — effort quá lớn.

---

## 3. Case Study

### 3.1 Netflix A/B Testing cho ML Models
- **Architecture:** Centralized ML Model Serving platform. Traffic split bằng internal experimentation framework.
- **Key insight:** "Always run shadow mode first — send 100% traffic to both models, but only serve responses from the incumbent. Compare quality offline before switching live traffic."
- **Takeaway:** Shadow mode → canary (5%) → gradual rollout (25% → 50% → 100%).
- **Tham khảo:** [Netflix Tech Blog - ML Platform](https://netflixtechblog.com/)

### 3.2 DoorDash Dynamic Model Configuration
- **Architecture:** Feature flag system (LaunchDarkly) để điều khiển model selection, prompt templates, và temperature.
- **Key insight:** "We treat model configuration as a feature flag, not a code deployment."
- **Takeaway:** Flag-driven model selection giảm MTTR khi cần rollback model.
- **Tham khảo:** [DoorDash Engineering - ML Infrastructure](https://doordash.engineering/)

### 3.3 LinkedIn Model Gateway
- **Architecture:** Internal "Model Gateway" service routing requests to different model backends.
- **Metrics tracked:** Latency, throughput, error rate, cost per request — all tagged by model ID.
- **Key insight:** Centralized gateway enables cost attribution per team/feature.
- **Tham khảo:** [LinkedIn Engineering Blog](https://engineering.linkedin.com/)

### 3.4 Uber Michelangelo Model Serving
- **Architecture:** Model registry → model serving layer → canary deployment with automatic rollback.
- **Key insight:** Canary serving with automated quality metrics comparison. If new model degrades quality by > 2%, auto-rollback.
- **Tham khảo:** [Uber Engineering - Michelangelo](https://www.uber.com/en-US/blog/michelangelo-machine-learning-platform/)

---

## 4. Kế hoạch triển khai

### Phase 1: flagd Configuration (Day 1)

```json
// src/flagd/demo.flagd.json — thêm flag mới
{
  "llmModelRouting": {
    "state": "ENABLED",
    "variants": {
      "ab_test_active": {
        "amazon.nova-lite-v1:0": 80,
        "amazon.nova-pro-v1:0": 20
      },
      "lite_only": {
        "amazon.nova-lite-v1:0": 100
      }
    },
    "defaultVariant": "ab_test_active"
  }
}
```

### Phase 2: Model Router Implementation (Day 1-2)

Tạo component dùng chung ở `src/product-reviews/model_router.py` (và tương tự ở `src/shopping-copilot/`, `src/llm/`):

```python
# model_router.py

import random
import os
from openfeature import api

class ModelRouter:
    def __init__(self):
        self.of_client = api.get_client()

    def get_main_model(self, default_model=None):
        if not default_model:
            default_model = os.environ.get('LLM_REVIEWS_MAIN_MODEL', os.environ.get('AWS_BEDROCK_MODEL', 'amazon.nova-lite-v1:0'))
            
        config = self.of_client.get_object_value("llmModelRouting", {})
        
        if not config:
            return default_model
            
        models = list(config.keys())
        weights = list(config.values())
        
        if not models or sum(weights) == 0:
            return default_model
            
        return random.choices(models, weights=weights, k=1)[0]
```

Tích hợp trực tiếp vào logic gọi LLM (`product_reviews_server.py`):

```python
from model_router import ModelRouter

# Lấy model bằng Model Router thay vì cứng từ ENV
router = ModelRouter()
main_model = router.get_main_model()

response = invoke_bedrock_converse_with_fallback(...)
```

### Phase 3: A/B Evaluation Dashboard (Day 3)

Sử dụng Prometheus/Grafana queries để so sánh:

```promql
# Latency by model
histogram_quantile(0.95, 
  rate(llm_gateway_latency_ms_bucket{task_type="reviews_summary"}[5m])
) by (model_id)

# Cost by model
sum(rate(llm_gateway_estimated_cost_usd_total[1h])) by (model_id)

# Error rate by model
sum(rate(llm_gateway_requests_total{status="error"}[5m])) by (model_id) 
/ sum(rate(llm_gateway_requests_total[5m])) by (model_id)
```

### Phase 4: Shadow Mode (Optional, Day 4)

Gọi cả 2 models song song nhưng chỉ serve kết quả từ model chính. Log output model phụ để so sánh offline.

---

## 5. Eval Criteria

| Metric | Target | Cách đo |
|---|---|---|
| Traffic split accuracy | ±5% of configured weight | Prometheus counter ratio |
| Latency overhead (routing) | < 5ms | OTel span duration for `model_router.route` |
| Metric granularity | Per model, per task_type | Grafana dashboard |
| Flag change → effect | < 30 seconds | flagd sync interval |
| Fallback on flag error | 100% to default model | Error injection test |

---

## 6. Rủi ro & Giảm thiểu

| Rủi ro | Khả năng | Giảm thiểu |
|---|---|---|
| flagd unavailable | Thấp | Default hardcoded fallback model |
| A/B split biased (small sample) | Trung bình | Đủ traffic trước khi kết luận (> 100 requests/variant) |
| Cost spike khi route nhiều traffic sang Nova Pro | Trung bình | Cost counter alert + cap Pro traffic ≤ 30% |
| Model output quality inconsistent giữa A/B variants | Trung bình | Eval script so sánh output quality offline |
