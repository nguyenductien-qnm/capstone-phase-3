# MANDATE-23 loop log

## 2026-07-27 — L2 migration / iteration 1

- **Scope:** chuyển L2 semantic cache từ pgvector sang Valkey Search; CDO đã cho phép nâng ElastiCache.
- **Thay đổi:** Terraform ElastiCache Valkey `8.2`; local `valkey/valkey-bundle:8.1` với Search module; `shopping-copilot` tạo `copilot-semantic-idx`, lưu vector FLOAT32 HNSW theo scope hash, TTL và giới hạn 200 entry/scope; giữ rule-guard phủ định/toán tử giá/con số/tên riêng.
- **Rebuild:** `shopping-copilot` và `valkey-cart` đã build/recreate bắt buộc.
- **Kết quả:** semantic fast harness **3/3 pass**: paraphrase `hit_semantic`, đổi mốc giá `miss`, phủ định `miss`.
- **Hạ tầng phụ:** email Dockerfile bổ sung `g++` cho grpc native extension; `docker compose build email` **pass**.
- **Chưa chốt:** cache/invalidation harness bị treo ở bước dọn prefix; cần sửa helper cleanup trước khi chạy full repro. Không phân loại đây là lỗi L2.

## 2026-07-27 — cleanup helper / cache fast lane

- **Root cause:** shell `xargs docker exec` cleanup could hang even with an empty scan result.
- **Fix:** Python helper now scans with bounded timeout and deletes keys in batches without shell piping.
- **Result:** cache fast harness **3/3 pass**: first miss, exact repeat hit, source-change invalidation miss.

## 2026-07-27 — numbers / trace-cost instrumentation

- **Root cause:** lần chạy trực tiếp trước đó không export `JAEGER_BASE_URL`, nên Jaeger port mặc định `32772` không còn đúng port compose hiện tại (`32783`); trace extraction trả 0 token/USD. Đây là lỗi cách chạy harness, không phải lỗi cache hay Bedrock.
- **Cách chạy đúng:** lấy port động bằng `docker compose port jaeger 16686` rồi chạy `eval_mandate23.py --only numbers --enforce-hard-bars`.
- **Kết quả:** numbers **3/3 pass** — hit-rate 50% (6/12), p50/p95 hit 1.36s/1.42s so với miss 19.12s/36.17s, token 134,297 → 66,157 (-68,140), USD $0.044288 → $0.021019 (-53%). Evidence: `evidence_m23/20260727_193952/`.
- **Ghi chú hạ tầng:** trong lúc đo, product-catalog có các RPC timeout 25s ở một số request; các request vẫn tạo trace và cost được tính. Cần phân loại khi chạy full repro, không sửa harness để che timeout.
