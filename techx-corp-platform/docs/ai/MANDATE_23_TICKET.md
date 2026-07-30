# MANDATE-23: GenAI Caching & Memory (TF1-M23)

## 1. Context
- Add GenAI L1 (Exact) and L2 (Semantic) Caching for Shopping Copilot and Ask-AI.
- Add Short-term and Long-term user memory per Copilot session to personalize and provide better experience.

## 2. Requirements
- L1 cache using Valkey (content-addressed hash keys).
- L2 Semantic cache using pgvector and Titan embed.
- Short-term session context in Valkey (TTL-bounded).
- Long-term memory in PostgreSQL (persistent user preferences).

## 3. Evidence
- **PR/Commit links**: Provided in Git branch `feat/mandate-23-genai-caching-memory`.
- **E2E Working Proof**: Cache responses return correctly, LLM latency decreases on hits. Short-term and long-term memory load contexts reliably based on test evaluations.
- **Signed ADR**: See `docs/ai/ADR-017.md`.

## 4. SQL commands for Invalidations
```sql
UPDATE reviews.productreviews SET description = 'Updated review for test', score = 5 WHERE product_id = 'OLJCESPC7Z' AND id = 123;
```
