# MANDATE-23 Eval Report — 20260728_000325

**Tổng:** 16/16 pass · hard bar ĐẠT

| Nhóm | Ca | Pass | Lý do | Cache | Latency |
|---|---|---|---|---|---|
| cache | first-miss | ✅ | lần đầu miss | miss | 5.74s |
| cache | repeat-hit | ✅ | lần hai hit_exact (5.74s → 1.58s) | hit_exact | 1.58s |
| cache | invalidation | ✅ | sau khi đổi review: miss (phải miss, không trả cũ sai) | miss | 20.66s |
| semantic | paraphrase-hit | ✅ | diễn đạt khác cùng ý: hit_semantic (similarity=0.8862338662147522) | hit_semantic | 2.22s |
| semantic | opposite-must-miss | ✅ | đổi mốc giá dưới→trên: miss (không được hit_semantic) | miss | 17.48s |
| semantic | negation-must-miss | ✅ | câu phủ định: miss (không được hit_semantic) | miss | 5.02s |
| shortterm | three-turns | ✅ | lượt 3 nhắc lại sản phẩm của lượt trước: ['Starsense Explorer Refractor Telescope'] | miss | 3.31s |
| longterm | stored | ✅ | memory đã ghi: experience_level=beginner |  use_case=stargazing | — | 0.0s |
| longterm | recall-new-session | ✅ | phiên mới nhớ trình độ=True, mục đích=True | miss | 4.37s |
| longterm | pii-redacted | ✅ | PII không nằm trong ai.user_memory | — | 0.0s |
| crossuser | no-cache-leak | ✅ | user B hỏi câu user A: miss (không được hit) | miss | 4.39s |
| crossuser | no-session-borrow | ✅ | session người khác không lộ ngữ cảnh | miss | 14.49s |
| bypass | cart-not-cached | ✅ | câu chạm giỏ hàng: bypass (phải bypass) | bypass | 5.95s |
| numbers | hit-rate | ✅ | hit-rate 50% (6/12: exact 6, semantic 0) | — | 0.0s |
| numbers | latency | ✅ | p50/p95 hit 1.06s/1.12s · miss 13.35s/30.48s | — | 0.0s |
| numbers | cost-before-after | ✅ | token 133000 → 77788 (-55212) · USD chuẩn hoá Nova Lite $0.008395 → $0.004939 (-41%); USD thực tế A/B $0.027056 → $0.004938 | — | 0.0s |

Evidence: `ai/evals/evidence_m23/20260728_000325`