# Spec: Model Gateway & A/B Testing cho LLM (Hạng mục Đua Top)

> **Trạng thái:** Draft  
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
      "nova-lite-100": {
        "reviews_model": "amazon.nova-lite-v1:0",
        "copilot_model": "amazon.nova-pro-v1:0"
      },
      "nova-lite-80-pro-20": {
        "reviews_model": "amazon.nova-lite-v1:0",
        "copilot_model": "amazon.nova-pro-v1:0",
        "reviews_ab": {
          "amazon.nova-lite-v1:0": 80,
          "amazon.nova-pro-v1:0": 20
        }
      },
      "nova-pro-100": {
        "reviews_model": "amazon.nova-pro-v1:0",
        "copilot_model": "amazon.nova-pro-v1:0"
      }
    },
    "defaultVariant": "nova-lite-100",
    "targeting": {
      "fractional": [
        ["nova-lite-100", 80],
        ["nova-lite-80-pro-20", 20]
      ]
    }
  }
}
```

### Phase 2: Model Router Implementation (Day 1-2)

```python
# llm/model_router.py

import os
import random
import logging
from openfeature import api as of_api
from opentelemetry import trace, metrics

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("model-router")

class ModelRouter:
    """Routes LLM requests to different models based on feature flags."""
    
    def __init__(self, bedrock_client, meter):
        self.bedrock_client = bedrock_client
        self.of_client = of_api.get_client()
        
        # Metrics per model
        self.request_counter = meter.create_counter(
            "llm.gateway.requests",
            description="Total LLM requests by model"
        )
        self.latency_histogram = meter.create_histogram(
            "llm.gateway.latency_ms",
            description="LLM request latency by model"
        )
        self.token_counter = meter.create_counter(
            "llm.gateway.tokens",
            description="Token usage by model"
        )
        self.cost_counter = meter.create_counter(
            "llm.gateway.estimated_cost_usd",
            description="Estimated cost by model"
        )
    
    def route_request(self, task_type: str, prompt: str, **kwargs):
        """Route an LLM request based on task type and feature flags."""
        with tracer.start_as_current_span("model_router.route") as span:
            # 1. Determine model from flag
            model_id = self._select_model(task_type)
            span.set_attribute("llm.model_id", model_id)
            span.set_attribute("llm.task_type", task_type)
            
            # 2. Call Bedrock
            import time
            start = time.monotonic()
            response = self._call_bedrock(model_id, prompt, **kwargs)
            elapsed_ms = (time.monotonic() - start) * 1000
            
            # 3. Emit metrics
            labels = {"model_id": model_id, "task_type": task_type}
            self.request_counter.add(1, labels)
            self.latency_histogram.record(elapsed_ms, labels)
            
            if "usage" in response:
                input_tokens = response["usage"].get("inputTokens", 0)
                output_tokens = response["usage"].get("outputTokens", 0)
                self.token_counter.add(input_tokens, {**labels, "token_type": "input"})
                self.token_counter.add(output_tokens, {**labels, "token_type": "output"})
                
                # Estimate cost
                cost = self._estimate_cost(model_id, input_tokens, output_tokens)
                self.cost_counter.add(cost, labels)
            
            logger.info(f"Routed {task_type} to {model_id} ({elapsed_ms:.0f}ms)")
            return response
    
    def _select_model(self, task_type: str) -> str:
        """Select model based on feature flag evaluation."""
        try:
            config = self.of_client.get_object_value(
                "llmModelRouting", 
                {"reviews_model": "amazon.nova-lite-v1:0", 
                 "copilot_model": "amazon.nova-pro-v1:0"}
            )
            
            if task_type == "reviews_summary":
                # Check A/B split
                if "reviews_ab" in config:
                    return self._weighted_select(config["reviews_ab"])
                return config.get("reviews_model", "amazon.nova-lite-v1:0")
            elif task_type == "copilot":
                return config.get("copilot_model", "amazon.nova-pro-v1:0")
            else:
                return "amazon.nova-lite-v1:0"
        except Exception as e:
            logger.warning(f"Flag evaluation failed: {e}, using default")
            return "amazon.nova-lite-v1:0"
    
    def _weighted_select(self, weights: dict) -> str:
        """Select model based on percentage weights."""
        models = list(weights.keys())
        probs = [weights[m] / sum(weights.values()) for m in models]
        return random.choices(models, weights=probs, k=1)[0]
    
    def _estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD per Bedrock pricing."""
        PRICING = {
            "amazon.nova-lite-v1:0": {"input": 0.00006, "output": 0.00024},
            "amazon.nova-pro-v1:0":  {"input": 0.0008,  "output": 0.0032},
            "amazon.nova-micro-v1:0": {"input": 0.000035, "output": 0.00014},
        }
        prices = PRICING.get(model_id, {"input": 0.001, "output": 0.004})
        return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1000
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
