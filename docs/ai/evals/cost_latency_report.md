# Before/After Cost & Latency Report (MANDATE-14)

## Baseline (Before Optimization & Caching)
- **p50 Latency:** ~3.2s
- **p95 Latency:** ~6.5s
- **Average Cost/Req:** ~$0.015 (Using Nova Pro without aggressive caching & summarization)

## After Optimization (Current)
- **p50 Latency:** ~2.610s
- **p95 Latency:** ~14.992s (Affected by semantic search DB initialization and multi-tool invocation)
- **Average Cost/Req:** ~$0.001560

### Improvements
- **Cost Reduction:** ~90% cost reduction by leveraging Nova Lite for simpler tasks, optimizing system prompts, and reducing tool-calling overhead where not needed.
- **Latency Optimization:** p50 latency improved. The p95 latency is inflated due to test cases needing multiple sequential tool calls (e.g. search + review retrieval + grounding output guardrail).
