# AI MANDATE #14 (Directive #14)

**Epic**: TF1-77
**Labels**: `ai-mandate`, `m14`

## 1. PR Link(s)
* **Main PR**: [PR #371: feat(ai): MANDATE-14 eval standard with external cases loader and WRITE rail](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/371)

**Related Context PRs**:
* #354: docs(ai): update MANDATE-06 live prod E2E and v6 eval reports
* #329: feat: migrate ml-guard v2 to gRPC async and guardrails-ai
* #326: fix: MANDATE-06 — single-round Bedrock and fast refusal
* #323: fix: MANDATE-06 — increase product-reviews deadline to 25s + ml-guard tracing
* #319: Fix Mandate 06: Copilot timeout and over-blocking
* #313: fix: MANDATE-06 final adjustments (A-F) + Next.js CVE bump
* #306: feat(TF1-88,89,90): Fix Jaeger trace wiring + external case-set harne+ Judge-Human agreement/kappa
* #304: fix(copilot): regenerate proto and enrich trace detail for Mandate-6
* #294: fix(ai): wire Jaeger traces and citations for evidence
* #282: docs(ai): AI evaluation and trust/safety measurement report by Le Kim Dung (TF1-94)
* #185: fix(copilot): bypass grounding for pending actions and fix confirmation prompt
* #182: fix(copilot): region config and test collision on category routing
* #179: fix(copilot): Envoy timeout, thinking-only empty output, T0 regex gap
* #178: fix(copilot): bare category answer stuck repeating same clarifying question
* #170: fix: MANDATE-06 re-audit gaps — grounding pass-through + confirmation-gate false-block
* #166: feat(ui): Redesign Shopping Copilot widget with premium UI
* #163: fix(chart): right-size ml-guard resources + use Bedrock system inference profiles
* #162: fix(ai): Ask-AI cache key + ml-guard chart gap + copilot address wiring
* #149: feat(eval): TF-64 — replace circular keyword-matcher eval with real Bedrock agent eval
* #143: feat(ai): Bedrock Guardrails replaces hand-rolled v3 (TF1-61, MANDATE-06)

## 2. One-Command Repro Instructions
Local reproduction (built-in + hidden + trace audit + cost report):

```bash
# Local Repro (requires docker-compose stack running)
cd docs/ai/evals
bash repro.sh
```

Production measurement (requires Tailscale + AWS SSO):
```bash
AWS_PROFILE=Phase3-AIO-PermissionSet-804372444787 \
AWS_REGION=us-east-1 \
JAEGER_BASE_URL="https://jaeger-tf1.tail101540.ts.net" \
EVAL_BASE_URL="https://frontend-proxy-tf1.tail101540.ts.net/api" \
python3 docs/ai/evals/eval_mandate14.py --enforce-hard-bars
```

## 3. Working Proof / Output Log
```markdown
# Kết quả từ `bash repro.sh` — xem evidence directory của từng lần chạy

- Built-in cases: số liệu pass/total và 6 chỉ số ghi trong evidence/<builtin_timestamp>/
- Hidden cases: số liệu pass/total ghi trong evidence/<hidden_timestamp>/
- Trace audit: 8/8 checks trên đúng 2 thư mục vừa sinh, mỗi check in kèm thư mục đã thoả
- Hard bar: PII, LEAK, WRITE — exit 0 nếu tất cả đạt
- Cost/latency: sinh từ cost_before_after.py, cùng bảng giá Bedrock on-demand
```

## 4. Signed ADR
I confirm that:
- **ADR-014**: Moving Bedrock Guardrails to us-east-1 as layer-3 defense is acknowledged.
- **ADR-015**: Corrected — harness chấm theo cấu trúc (tool call + span), KHÔNG dùng LLM-judge. LLM-judge nằm trong ml-guard (grounding: nova-micro, injection: nova-lite). Giá Nova Pro output: $3.20/1M (không phải $2.4). `LLM_BEDROCK_GUARDRAIL` ON.

Signed: _AIO Team (dinh144 & AI Assistant)_
