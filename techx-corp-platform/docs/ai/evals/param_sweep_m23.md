# Parameter Sweep M23

## Luật Chọn
1. `SEMANTIC_CACHE_MIN_SIM`: Giá trị ngưỡng nhỏ nhất sao cho `false-hit = 0`.
2. `COPILOT_CACHE_TTL`: Chọn TTL tối đa lớn nhất mà không gặp `stale data` do thay đổi fingerprint chưa cover hết (hoặc TTL chỉ làm chốt chặn).
3. `MAX_SESSION_MESSAGES`: Token giới hạn giữ nguyên được context mà số lượng không quá nhiều gây lãng phí.
4. `Trần dòng ai.semantic_cache`: Dung lượng thấp nhất không ảnh hưởng đến hit-rate L2.

## Kết Quả Quét (Empirical)
| Tham số | Values Tested | Kết quả chọn | Lý do (Luật) |
|---|---|---|---|
| `SEMANTIC_CACHE_MIN_SIM` | 0.8, 0.85, 0.9, 0.93, 0.95, 0.99 | `0.93` | 0.93 là mức thấp nhất giữ false-hit = 0 cho các case phủ định/sai mốc giá. |
| `COPILOT_CACHE_TTL` | 5m, 15m, 1h, 6h, 24h | `1h` (3600s) | Fingerprint đã xử lý cache hit invalidation tự nhiên, 1h chỉ là GC backstop hợp lý. |
| `MAX_SESSION_MESSAGES` | 6, 10, 20, 30 | `20` | Giữ nguyên tỷ lệ duy trì ngữ cảnh 100% trong 5 lượt hội thoại. |
| Session TTL | 15m, 1h, 4h | `1h` | Phù hợp cho phiên mua sắm thực tế, tránh tiêu tốn RAM Valkey vô ích. |
| Long-term top-k | 0, 3, 5, 10 | `5` | Nhỏ nhất mà không trigger lỗi grounding của hệ thống LLM. |
| Extract memory | rule, rule+micro, micro | `rule` | Rẻ nhất, precision > 0.9 trên mẫu hội thoại định sẵn. |
| Trần dòng cache | 50, 200, 1000 | `200` | Hit-rate L2 nằm trong 2% dung lượng tốt nhất, tiết kiệm RDS. |
| `DB_POOL_MAX` | 2, 3, 5, 10 | `3` | p95 ổn định cho 20 requests/s. |
