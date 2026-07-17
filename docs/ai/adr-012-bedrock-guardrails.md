# ADR-012 — Adopt Amazon Bedrock Guardrails, retire hand-rolled v3

- **Status:** Accepted (2026-07-17) — supersedes the v3 guardrail decision in ADR-011.
- **Context:** TF1-61 / MANDATE-06 (AI trust & safety). Deadline 2026-07-18.
- **Deciders:** AIO team. Signed: _(mentor sign-off pending)_.

## Context

MANDATE-06 requires the AI layer to *prove* it is trustworthy: block prompt-injection
buried in reviews, filter PII, never leak the system prompt, and — critically — **not
hallucinate** ("không bịa"; say "review không đề cập" when the source doesn't answer).
Constraints: don't break the product-page SLO, optimise token/cost ("đừng quăng model
to cho xong"), don't touch flagd.

The v3 implementation was 945 lines **duplicated byte-identical across two services**
(1890 total): hand-rolled homoglyph tables, leetspeak/base64 normalisation, Shannon
entropy, a 20-string known-attack corpus embedded per-request with Titan, a
`SessionGuardrail` anomaly tracker, and a Nova LLM-judge. It ran a **Titan embed call +
a Nova judge call per request** — the opposite of the mandate's "don't throw a big model"
— and still had **no real faithfulness check** (only a citation number-match hack).

## Decision

Replace v3 with **managed Amazon Bedrock Guardrails** (we already run Bedrock — zero new
infra), applied via the standalone `ApplyGuardrail` API:

| Layer | Mechanism |
|---|---|
| INPUT rail | prompt-attack filter (HIGH) + PII ANONYMIZE + denied-topic (system-prompt extraction). Fail-**closed**. |
| OUTPUT rail | **contextual grounding** (faithfulness + relevance, threshold 0.7) + PII mask. Fail-**open** but still regex-masks PII. |
| Pre-filter | thin length-cap + a few obvious regex — free short-circuit before paying Bedrock. |
| Agent actions | tool allow-list + confirmation gate for cart writes — stays in `agent.py` (no guardrail library covers excessive-agency). |

Guardrail resource lives in an **AI-owned standalone Terraform module**
(`terraform/ai-guardrails/`) — separate state, does **not** touch any CDO module. App
reads `BEDROCK_GUARDRAIL_ID` / `BEDROCK_GUARDRAIL_VERSION` via `values-aio-llm.yaml`
(AI-owned). Feature flag `LLM_BEDROCK_GUARDRAIL` (default on); off → degrade to regex
pre-filter.

Net: **945 → 246 lines/file** (−1398 total).

## Cost comparison (measured rates, not vibes)

Bedrock rates: content-filter/denied-topic **$0.15**/1k text-units (TU), PII/grounding
**$0.10**/1k TU, **1 TU = 1000 chars**. Nova-micro $0.035/$0.14 per 1M in/out, Titan-embed
$0.11/1M. TF budget **$300/week**. Assumed 1 summary: source top-8 reviews ≈2000 chars,
query ~100, response ~500.

| Option | $/week (AI budget) | Infra | Grounding | Verdict |
|---|---|---|---|---|
| **A. Bedrock Guardrails** | **~$15 (5%)** — in-rail 2TU×$0.40 + out-rail ~4TU×$0.10 ≈ $0.0012/req × ~10.5k req/wk | $0 | ✅ managed | **Chosen** — only option with real faithfulness; 3× traffic still 15% |
| B. v3 hand-rolled (flags off) | ~$0 | $0 | ❌ (citation hack) | Fails the exact scored axis |
| B'. v3 (flags on) | ~$1 + 2 extra round-trips ~0.7s | $0 | ❌ | Cheaper but no faithfulness, +latency, 1890 ln |
| C. +self-host ML (phase-2) | **~$0** into AI budget (**CDO confirmed pod capacity**) + Bedrock $15 | CDO pod | ✅ (Bedrock) + PII NER | Only if eval proves a Bedrock gap |

## Consequences

**Positive:** faithfulness gate (the mandate-critical feature), −1398 lines, no bespoke
maintenance, reproducible eval via `ApplyGuardrail` assessment, no new infra, drops the
per-request Titan+Nova round-trips.

**Negative / risks:**
- **PII CloudWatch gap:** guardrail PII masking applies to the API response only — raw PII
  is still written to CloudWatch model-invocation logs. Mitigation if this handles
  regulated data: KMS-encrypt those log groups + restrict IAM. (No regulated data today.)
- **Not live-verified in this change** — no AWS SSO in the authoring session. PR is
  code-complete; live `terraform apply` + threshold tuning need the team's SSO.
- **Grounding runs OUTPUT only**, source ≤100k chars → cap top-K reviews.
- **Threshold 0.7** is a starting point — tune against the eval set (raise if
  hallucinations pass, lower if legit answers blocked).
- `trace`/`outputScope=FULL` must stay **off in prod** (exposes raw PII); enable only for
  offline eval debugging.

## Phase-2 (ML) — deferred, not dropped

CDO confirmed extra pod capacity, removing the infra blocker that killed Presidio/ONNX in
v3. Phase-2 adds a local ML gate (Prompt Guard 2 86M / Presidio PII NER) **before** Bedrock,
behind flag `llmLocalMlGuard`, **only after** the eval set measures a gap Bedrock leaves
open (tracked by `ml_vs_bedrock_disagreement`). Small models only — an 8B LlamaGuard is the
"big model" the mandate warns against. Having pods is not a reason to add ML; a measured
gap is.
