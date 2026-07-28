# MANDATE-23 Production Deployment Checklist

**Branch:** `feat/mandate-23-genai-caching-memory`
**Ngày:** 2026-07-28
**Người phụ trách:** Nguyễn Hữu Dinh (AIO03 – TF1)

## Tổng quan

MANDATE-23 (GenAI Caching & Memory) cần 3 thay đổi hạ tầng để hoạt động trên production (`ecommerce-dev-eks` / namespace `techx-tf1`). Không thay đổi nào tự động — tất cả phải làm thủ công theo thứ tự dưới đây.

## Kiểm tra tiền điều kiện

Trước khi bắt đầu, xác nhận các secrets đã tồn tại trên cluster:

```bash
kubectl -n techx-tf1 get secret valkey-secret -o jsonpath='{.data}' | jq 'keys'
# Phải có: address, auth_token

kubectl -n techx-tf1 get secret db-secret -o jsonpath='{.data}' | jq 'keys'
# Phải có: reviews-db-conn

kubectl -n techx-tf1 get secret bedrock-config -o jsonpath='{.data}' | jq 'keys'
# Phải có: BEDROCK_AWS_ROLE_ARN, BEDROCK_AWS_EXTERNAL_ID
```

## Bước 1: Migration PostgreSQL RDS — tạo schema `ai` + bảng `user_memory`

**File:** `docs/ai/migrations/m23_ai_schema.sql`

Pgvector extension đã có sẵn trên RDS (đang dùng cho `catalog.product_embeddings_v2`). Migration này chỉ tạo schema mới và bảng durable memory.

```bash
# Lấy RDS URL từ secret (nếu chưa có)
RDS_URL=$(kubectl -n techx-tf1 get secret db-secret -o jsonpath='{.data.reviews-db-conn}' | base64 -d)

# Chạy migration
psql "$RDS_URL" -v ON_ERROR_STOP=1 -f docs/ai/migrations/m23_ai_schema.sql
```

**Verify:**
```sql
\dn ai
\dt ai.*
-- Phải thấy: ai.user_memory
```

> **Lưu ý:** `ai.semantic_cache` (pgvector) trong `init.sql` chỉ dùng cho local Docker Compose. Trên production, L2 semantic cache dùng **Valkey Search FT.SEARCH** trên ElastiCache 8.2 — không dùng pgvector cho cache.

## Bước 2: Terraform — nâng ElastiCache Valkey từ 7.2 → 8.2

**File:** `terraform/modules/elasticache/main.tf` (đã sửa `engine_version = "8.2"`)

Valkey 8.2 cần cho `FT.SEARCH` vector index (L2 semantic cache). Phiên bản 7.2 không có tính năng này.

```bash
cd terraform/
terraform init
terraform plan   # Kiểm tra chỉ có thay đổi engine_version
terraform apply  # Thực hiện trong MAINTENANCE WINDOW
```

⚠️ **Cảnh báo downtime:** Nâng engine version ElastiCache sẽ reboot replication group — gián đoạn cache vài phút. Cart service có thể mất giỏ hàng tạm thời nếu chưa có fallback. **Làm trong maintenance window, báo trước cho CDO.**

**Verify:**
```bash
aws elasticache describe-replication-groups \
  --replication-group-id ecommerce-dev-valkey \
  --query 'ReplicationGroups[0].EngineVersion'
# Phải trả về: "8.2"
```

## Bước 3: ArgoCD sync — deploy Helm values mới cho shopping-copilot

**File:** `platform/charts/application/values.yaml` (đã thêm env vars MANDATE-23)

Sau khi merge PR, ArgoCD sẽ tự động sync. Các env vars mới cho `shopping-copilot`:

| Env var | Giá trị | Nguồn |
|---|---|---|
| `VALKEY_ADDR` | - | secret `valkey-secret` key `address` |
| `VALKEY_TLS` | `true` | Hardcoded (production dùng TLS) |
| `VALKEY_AUTH_TOKEN` | - | secret `valkey-secret` key `auth_token` |
| `DB_CONNECTION_STRING` | - | secret `db-secret` key `reviews-db-conn` |
| `SEMANTIC_CACHE_ENABLED` | `true` | Hardcoded |
| `SEMANTIC_CACHE_MIN_SIM` | `0.85` | Từ param sweep (`docs/ai/evals/param_sweep_m23.md`) |
| `COPILOT_CACHE_TTL` | `3600` | L1 exact cache TTL (1 giờ) |
| `COPILOT_SESSION_TTL` | `3600` | Session TTL (1 giờ) |
| `COPILOT_MAX_SESSION_MESSAGES` | `20` | Max messages per session |

**Verify sau deploy:**
```bash
# Pod đã restart với env mới
kubectl -n techx-tf1 get pods -l app=shopping-copilot

# Kiểm tra env trong pod
kubectl -n techx-tf1 exec deploy/shopping-copilot -- env | grep -E 'VALKEY|SEMANTIC|COPILOT'

# Log khởi động — phải thấy Valkey Search index created
kubectl -n techx-tf1 logs deploy/shopping-copilot --tail=50 | grep -i 'valkey\|cache\|search'
```

## Bước 4: Chạy eval smoke test

Sau khi cả 3 bước hoàn tất, chạy eval để xác nhận cache hoạt động trên production:

```bash
cd docs/ai/evals/

# Eval MANDATE-23 (cache + memory)
python eval_mandate23.py --env prod  # Target: 16/16 hard bar

# Eval MANDATE-14 (guardrail — regression check)
python eval_mandate14.py --env prod  # Target: 41/41 built-in + 25/25 hidden
```

## Thứ tự bắt buộc

```
Bước 1 (RDS migration)
  → Bước 2 (Valkey upgrade)
    → Bước 3 (ArgoCD sync)
      → Bước 4 (Smoke test)
```

- **Bước 1** chạy được ngay, không ảnh hưởng hệ thống đang chạy
- **Bước 2** phải xong trước Bước 3 — copilot pod mới gọi `FT.SEARCH` trên Valkey 8.2
- **Bước 3** sẽ restart copilot pod — xác nhận pod lên healthy trước khi chạy eval

## Rollback

Nếu có vấn đề:
1. **Rollback Helm:** revert `values.yaml` env vars → ArgoCD sync
2. **Rollback Valkey:** `terraform apply` với `engine_version = "7.2"` (mất dữ liệu cache, không mất cart nếu cart TTL 60m đã bật)
3. **Rollback RDS:** `DROP SCHEMA ai CASCADE` (mất user_memory data — chấp nhận được vì chưa có traffic thật)
