# ADR-013 — ML Guard Cascade thay Bedrock Guardrails làm primary (MANDATE-06)

- **Status:** Accepted (2026-07-17) — supersedes ADR-012.
- **Context:** TF1-61 / MANDATE-06. Yêu cầu mới: không phụ thuộc Bedrock Guardrails,
  phải có ML self-host (CDO đã confirm cấp tài nguyên pod).

## Tại sao lật ADR-012 (fact, không vibes)

Docs AWS chính chủ (`guardrails-supported-languages`, đọc 17/07/2026):

| Policy Bedrock Guardrails | Tiếng Việt? |
|---|---|
| Prompt-attack / content filter | Chỉ **Standard tier** (Classic = EN/FR/ES → **vô hiệu với VN**) |
| **Contextual grounding** | ❌ **EN/FR/ES only** + docs ghi rõ *"Conversational QA / Chatbot use cases are not supported"* |
| PII filter | ✅ VN Optimized |

AWS: *"Guardrails are ineffective with languages that aren't supported."* → tính năng
grounding (lý do chọn Bedrock ở ADR-012) **không hoạt động cho câu trả lời tiếng Việt**.
Thêm: Bedrock Guardrails tính tiền **mỗi request** ($0.10–0.15/1k text-unit) →
attacker spam Ask AI = **economic DoS** độn cost tuyến tính; ML pod self-host = fixed cost.

## Quyết định — cascade 3 tầng (mọi con số đo thật 17/07, local + us-east-1 default profile)

| Tầng | Cơ chế | Kết quả đo | Cost |
|---|---|---|---|
| T0 in-process | regex VN/EN + PII redact + length cap | chặn direct/indirect pattern, 0ms | $0 |
| T1 `ml-guard` pod | **mDeBERTa-v3-base-mnli-xnli** (MIT, XNLI có VN) NLI grounding: `contra≥0.5→block`, `entail≥0.3→pass`, giữa→judge | grounding VN 6/6 (bịa: contra 0.98+; grounded: ≤0.007); RSS 1148MB fp32; p50 1.8s (laptop 2 threads) | $0 marginal (CDO pod) |
| T2 Nova judge | **injection: Nova Lite** few-shot (Micro chỉ 4/7 — trượt VN jailbreak); **grounding neutral-zone: Nova Micro** | injection **7/7**, grounding **4/4**, p50 ~550ms | ~$0.00002–0.00004/check → **<$1/wk** @10.5k req |
| Bedrock Guardrails | flag `LLM_BEDROCK_GUARDRAIL` **default OFF**; giữ code path + TF module làm option nếu cần Standard tier sau | — | $0 khi off |

Eval tổng (`docs/ai/evals/eval_mandate06_v5.py`, tái tạo được): **18/18 pass**
(7 injection VN/EN + indirect, 5 grounding, 2 PII, 1 leak, 3 benign không chặn oan), p50 498ms.

Zero-shot NLI cho injection VN đã thử và **loại** (4/7, trượt cả 3 attack VN — đo trước khi chọn judge).

## Cost so sánh cuối

| Option | $/wk | Injection VN | Grounding VN | Spam→cost |
|---|---|---|---|---|
| Bedrock Classic (ADR-012) | ~$15 | ❌ vô hiệu | ❌ | độn tuyến tính |
| Bedrock Standard tier | ~$15–18 | ✅ | ❌ EN-only | độn tuyến tính |
| **Cascade (ADR-013)** | **<$1** | ✅ 7/7 đo | ✅ 4/4 + NLI 6/6 đo | T1 fixed; T2 chỉ sau khi T0/T1 lọc |

## Hành vi lỗi
- INPUT: regex luôn chạy; judge chết → **fail-open có chủ đích** (regex đã chặn tầng thô) — log warning.
- OUTPUT: ml-guard chết → rơi xuống Nova judge; judge chết → fail-open, **PII luôn mask**.
- Action Gate cart (excessive-agency) giữ ở `agent.py` — không đổi.

## Monitoring per-layer (trục "monitor được các layer")
- ml-guard: `/metrics` Prometheus (`ml_guard_decisions_total{action}`, latency avg).
- Services: log có cấu trúc `Grounding BLOCK (ml-guard contra=…)` / `(judge … said NO)` /
  `[Guardrail INPUT] blocked` — đếm được qua log backend (TF1-76).
- Eval report tự sinh: `docs/ai/evals/eval_mandate06_v5_report.md`.

## Consequences / risks
- Nova Lite injection judge = 1 call LLM phụ mỗi input (~550ms, $0.00002) — chấp nhận vì
  reviews path best-effort + cache 7d; copilot p95 5.7s vẫn trong trần.
- ml-guard image nướng model (~1.1GB) — build CI lâu hơn; đổi lại pod không egress HF.
- **Tài nguyên cho Local ML (Phase-2)** (áp dụng cho `shopping-copilot` và `product-reviews` pods):
  - **Dung lượng Disk/Image:** Tăng thêm **~1.1GB** (Model ProtectAI DeBERTa ~738MB + SpaCy model ~400MB) tải lúc build/chạy.
  - **Bộ nhớ RAM:** Cần cấp thêm ít nhất **1.5GB - 2.0GB RAM limit** cho mỗi pod (tổng limit tối thiểu khuyến nghị: **2.5GB per pod**) để load mô hình PyTorch và Presidio vào bộ nhớ mà không bị OOM (Out of Memory).
  - **CPU:** Khuyến nghị tăng CPU limit thêm **1.0 Core** per pod để CPU inference cho Local ML chạy mượt mà (giữ latency < 300ms cho phần Local ML check).
- Threshold NLI (0.5/0.3) chọn từ bench 17/07 — tune tiếp bằng eval khi có traffic thật.
- Region judge us-east-1 (default profile / IRSA role tương đương); SSO role bị chặn east-1
  — ghi rõ trong integration để CDO cấp IAM đúng region cho pod.
