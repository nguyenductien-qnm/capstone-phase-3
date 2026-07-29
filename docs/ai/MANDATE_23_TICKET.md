# AI MANDATE #23

## 1. Link PR/commit
Branch: `feat/mandates-23-to-25-and-ui-refactoring`

| Commit | Nội dung |
|---|---|
| `f9768646` | fix(ai): MANDATE-23 caching and memory actually work end to end |
| `4cc47e58` | feat(ai): MANDATE-23 GenAI caching and memory integration |
| *(pending)* | envelope cache (citations+tool provenance), guardrail parallel, leak needle, product-id guard |

**PR chính:** *(sẽ tạo sau khi push)*

**PR liên quan:** chung nhánh với MANDATE-14 (TF1-113, PR #371) do cache MANDATE-23 ảnh hưởng trực tiếp đến MANDATE-14 (cache hit làm mất citations → task/grounding/citation đều trượt).

---

## 2. Cách chạy lại (repro)

**Một lệnh:**
```bash
cd docs/ai/evals && bash repro_m23.sh
```

**Từng nhóm:**
```bash
./eval_mandate23.py --only cache      # L1 exact (miss → hit → invalidation)
./eval_mandate23.py --only semantic   # L2 semantic (paraphrase hit, opposite/negation miss)
./eval_mandate23.py --only shortterm  # Bộ nhớ ngắn hạn (3-turn context)
./eval_mandate23.py --only longterm   # Bộ nhớ dài hạn (Postgres store/recall, PII redact)
./eval_mandate23.py --only crossuser  # Cách ly user (cache leak, session borrow)
./eval_mandate23.py --only bypass     # Cart ops không cache
./eval_mandate23.py --only numbers    # hit-rate, latency, cost-before-after
```

Môi trường local cần 30 service của stack đang chạy, Valkey phải ở chế độ `server` (prod ElastiCache) — script tự kiểm tra pre-flight.

---

## 3. Bằng chứng chạy thật

Lần chạy nghiệm thu: **28/07/2026**, evidence `docs/ai/evals/evidence_m23/20260728_000325/` (16 file JSON).

**16/16 pass · hard bar ĐẠT · exit 0**

| Nhóm | Ca | Pass | Lý do | Cache | Latency |
|---|---|---|---|---|---|
| cache | first-miss | ✅ | lần đầu miss | miss | 5.74s |
| cache | repeat-hit | ✅ | lần hai hit_exact (5.74s → 1.58s) | hit_exact | 1.58s |
| cache | invalidation | ✅ | sau khi đổi review: miss (phải miss, không trả cũ sai) | miss | 20.66s |
| semantic | paraphrase-hit | ✅ | diễn đạt khác cùng ý: hit_semantic (similarity=0.886) | hit_semantic | 2.22s |
| semantic | opposite-must-miss | ✅ | đổi mốc giá dưới→trên: miss (không được hit_semantic) | miss | 17.48s |
| semantic | negation-must-miss | ✅ | câu phủ định: miss (không được hit_semantic) | miss | 5.02s |
| shortterm | three-turns | ✅ | lượt 3 nhắc lại sản phẩm của lượt trước: Starsense Explorer | miss | 3.31s |
| longterm | stored | ✅ | memory đã ghi: experience_level=beginner, use_case=stargazing | — | 0.0s |
| longterm | recall-new-session | ✅ | phiên mới nhớ trình độ=True, mục đích=True | miss | 4.37s |
| longterm | pii-redacted | ✅ | PII không nằm trong ai.user_memory | — | 0.0s |
| crossuser | no-cache-leak | ✅ | user B hỏi câu user A: miss (không được hit) | miss | 4.39s |
| crossuser | no-session-borrow | ✅ | session người khác không lộ ngữ cảnh | miss | 14.49s |
| bypass | cart-not-cached | ✅ | câu chạm giỏ hàng: bypass (phải bypass) | bypass | 5.95s |
| numbers | hit-rate | ✅ | hit-rate 50% (6/12: exact 6, semantic 0) | — | 0.0s |
| numbers | latency | ✅ | p50/p95 hit 1.06s/1.12s · miss 13.35s/30.48s | — | 0.0s |
| numbers | cost-before-after | ✅ | token 133000 → 77788 (-55212) · USD Nova Lite $0.0084 → $0.0049 (-41%) | — | 0.0s |

### File đính kèm

| File | Nội dung |
|---|---|
| `docs/ai/evals/eval_mandate23.py` | harness (16 test case, hard bar bật) |
| `docs/ai/evals/repro_m23.sh` | repro một lệnh + pre-flight check |
| `docs/ai/evals/param_sweep_m23.py` | sweep SEMANTIC_CACHE_MIN_SIM 0.70-0.95, chốt 0.85 |
| `docs/ai/evals/param_sweep_m23.md` | kết quả sweep (cặp khác nghĩa đạt 0.919, cặp cùng ý 0.659) |
| `docs/ai/evals/evidence_m23/20260728_000325/` (16 JSON) | evidence per-case, mỗi file kèm cache_status, similarity, latency |
| `docs/ai/evals/eval_mandate23_report.md` | báo cáo tổng hợp per-case |

---

## 4. ADR ký tên

- **[ADR-017](adr/ADR-017-genai-cache-memory.md)** — *GenAI Caching & Memory (MANDATE-23)*, Status Accepted, Date 2026-07-27, **Author: Nguyễn Hữu Dinh (AIO03 – TF1)**.

Tóm tắt quyết định kiến trúc:
1. **L1 exact** ở Valkey (cache-aside, key 7 phần: `user_id:model_ver:code_fp:catalog_fp:mem_fp:sess_fp:question_fp`), **L2 semantic** ở pgvector `ai.semantic_cache` (Titan Embed v2 1024d, HNSW cosine + rule guard), **L3** Bedrock prompt cache.
2. Ngưỡng similarity một mình **không đủ** — cặp khác nghĩa đạt 0.919 trong khi cặp cùng ý chỉ 0.659. Rule-guard `semantic_guard.py` (phủ định, mốc giá, số, sản phẩm) → false-hit 0%, chốt `SEMANTIC_CACHE_MIN_SIM = 0.85`.
3. Short-term memory ở Valkey (TTL 1h, `owner_user_id`), long-term ở Postgres `ai.user_memory` (ElastiCache có eviction, `SnapshotRetentionLimit=0`).
4. Câu chạm giỏ hàng → `bypass`, không cache. Fallback/rail-block → `cacheable=False`.
5. Cache envelope `{v, t, c, a}` giữ citations + tool records khi hit — nếu không MANDATE-14 chấm trượt grounding/citation/task.

Ký: **AIO Team — dinh144**

---

## SQL đổi bản ghi nguồn (cho Mentor)
Sử dụng câu lệnh SQL sau để thay đổi dữ liệu của review nguồn, nhằm kiểm tra cache invalidation qua việc content_fp thay đổi (cache miss + nội dung mới):

```sql
UPDATE reviews.productreviews 
SET description = 'This telescope is terrible, I can''t see anything!' 
WHERE product_id = 'OLJCESPC7Z' AND username = 'stargazer_mike';
```
