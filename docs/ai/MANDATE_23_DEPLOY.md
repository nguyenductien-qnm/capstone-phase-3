# MANDATE-23 + AI Infrastructure — Production Deployment Checklist

**Branch:** `feat/mandate-23-genai-caching-memory`
**Ngày:** 2026-07-28 (verified live trên cluster `ecommerce-dev-eks` / namespace `techx-tf1`)
**Người phụ trách:** Nguyễn Hữu Dinh (AIO03 – TF1)

## Production Audit (28/07 — live check)

| Component | Current | Required | Action |
|---|---|---|---|
| **ElastiCache Valkey** | `7.2.6` / `cache.t4g.micro` / `valkey` | `8.2` | Terraform apply |
| **RDS PostgreSQL** | `17.10` / `db.t4g.micro` 20GB Multi-AZ | Same (no change) | None |
| **pgvector extension** | ✅ Available (used by `product_embeddings_v2`) | Same | None |
| **Schema `ai`** | ❌ Not created | `ai.user_memory` table | Run `m23_ai_schema.sql` |
| **Schema `catalog` / `product_embeddings_v2`** | ❓ Not verified | Table + HNSW index | Run `ai_data_schema.sql` |
| **Secret `valkey-secret`** | ✅ `address` + `auth_token` | Same | None |
| **Secret `db-secret`** | ✅ `reviews-db-conn` | Same | None |
| **Secret `bedrock-config`** | ✅ (for ml-guard) | Same | None |
| **Shopping-copilot deploy** | ✅ Running (1/1, 21h uptime) | Needs env vars | ArgoCD sync |
| **Copilot MANDATE-23 env** | ❌ No `VALKEY_*` / `SEMANTIC_*` / `COPILOT_*` | 9 new env vars | ArgoCD sync |

## Bước 0: Migration PostgreSQL RDS — toàn bộ schema AI

Có 2 file migration cần chạy. Cả hai đều là `CREATE ... IF NOT EXISTS` nên chạy lại được nhiều lần.

### 0a. Schema `ai.user_memory` (MANDATE-23 durable memory)

**File:** `docs/ai/migrations/m23_ai_schema.sql`

```bash
RDS_URL=$(kubectl -n techx-tf1 get secret db-secret -o jsonpath='{.data.reviews-db-conn}' | base64 -d)
psql "$RDS_URL" -v ON_ERROR_STOP=1 -f docs/ai/migrations/m23_ai_schema.sql
```

### 0b. Schema `catalog.product_embeddings_v2` (Semantic Search + Recommendations)

**File:** `techx-corp-platform/src/postgresql/init.sql` (dòng 140-147)

Table này dùng Titan Embeddings V2 1024d + HNSW index cho semantic search (ADR-008) và AI recommendations (ADR-009). Trên local Docker Compose, init.sql tự chạy. Trên production, phải chạy thủ công.

```sql
-- Chạy trên RDS production:
CREATE TABLE IF NOT EXISTS catalog.product_embeddings_v2 (
    product_id  TEXT PRIMARY KEY,
    embedding   VECTOR(1024)
);
CREATE INDEX IF NOT EXISTS idx_product_embeddings_v2
    ON catalog.product_embeddings_v2
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

GRANT SELECT ON catalog.product_embeddings_v2 TO otelu;
```

> **Lưu ý:** Đây mới chỉ tạo bảng. Để có dữ liệu embedding, cần chạy script populate embeddings (gọi Titan Embed V2 qua Bedrock cho từng sản phẩm). Script này chưa có trong repo — cần viết riêng hoặc chạy batch job từ product-catalog service.

## Bước 1: Terraform — nâng ElastiCache Valkey từ 7.2.6 → 8.2

**File:** `terraform/modules/elasticache/main.tf` (đã sửa `engine_version = "8.2"`)

**Hiện trạng verified 28/07:**
- Engine: `valkey`
- EngineVersion: `7.2.6` (node `ecommerce-dev-valkey-001`)
- NodeType: `cache.t4g.micro`
- SnapshotRetentionLimit: `7` (snapshot enabled — dữ liệu cart được backup)
- AutomaticFailover: `enabled` (Multi-AZ)

Valkey 8.2 cần cho `FT.SEARCH` vector index (L2 semantic cache). Phiên bản 7.2.6 không có tính năng này.

```bash
cd terraform/
terraform init
terraform plan   # Kiểm tra chỉ có thay đổi engine_version
terraform apply  # Thực hiện trong MAINTENANCE WINDOW
```

⚠️ **Cảnh báo downtime:** Nâng engine version ElastiCache sẽ reboot replication group — gián đoạn cache vài phút. Cart service sẽ mất dữ liệu trong Valkey (TTL 60m nên có thể khôi phục). **Làm trong maintenance window, báo trước cho CDO.**

**Verify:**
```bash
aws elasticache describe-cache-clusters \
  --cache-cluster-id ecommerce-dev-valkey-001 \
  --show-cache-node-info \
  --query 'CacheClusters[0].EngineVersion'
# Phải trả về: "8.2"
```

## Bước 2: ArgoCD sync — deploy Helm values mới cho shopping-copilot

**File:** `platform/charts/application/values.yaml` (đã thêm env vars MANDATE-23)

**Hiện trạng verified 28/07:** Copilot pod đang chạy (`shopping-copilot-86746df6b5-mftsx`, 21h uptime) nhưng KHÔNG có MANDATE-23 env vars. Chỉ có env cũ:

```
SHOPPING_COPILOT_PORT=50051
LLM_COPILOT_MAIN_MODEL=amazon.nova-pro-v1:0
LLM_COPILOT_FALLBACK_MODEL=amazon.nova-lite-v1:0
LLM_COPILOT_TIMEOUT=45.0
LLM_COPILOT_FALLBACK_TIMEOUT=2.7
```

Sau khi merge PR, ArgoCD sẽ tự động sync và thêm các env vars:

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
kubectl -n techx-tf1 get pods -l app.kubernetes.io/name=shopping-copilot
kubectl -n techx-tf1 exec deploy/shopping-copilot -- env | grep -E 'VALKEY|SEMANTIC|COPILOT'
kubectl -n techx-tf1 logs deploy/shopping-copilot --tail=50 | grep -i 'valkey\|cache\|search'
```

## Bước 3: Populate `product_embeddings_v2` (CDO cần chạy)

Sau khi bảng `product_embeddings_v2` đã được tạo (Bước 0b), cần populate embeddings cho tất cả sản phẩm trong catalog. Việc này gọi Bedrock Titan Embed V2 để sinh vector 1024 chiều cho mỗi sản phẩm.

**Chưa có script tự động trong repo.** CDO có 2 lựa chọn:

1. **Script Python batch** (khuyến nghị): Viết script gọi `bedrock.invoke_model` với model `amazon.titan-embed-text-v2:0`, embed từng sản phẩm, INSERT vào `product_embeddings_v2`.
2. **Tích hợp vào product-catalog service**: Mỗi khi thêm/sửa sản phẩm, tự động sinh embedding.

Chi phí: ~$0.00002/1K tokens, embed toàn bộ catalog (~200 sản phẩm) tốn khoảng $0.001.

## Bước 4: Chạy eval smoke test

Sau khi cả 3 bước hoàn tất:

```bash
cd docs/ai/evals/

# Eval MANDATE-23 (cache + memory)
python eval_mandate23.py --env prod  # Target: 16/16 hard bar

# Eval MANDATE-14 (guardrail — regression check)
python eval_mandate14.py --env prod  # Target: 41/41 built-in + 25/25 hidden
```

## Thứ tự bắt buộc

```
Bước 0 (RDS migration: ai.user_memory + catalog.product_embeddings_v2)
  → Bước 1 (Valkey 7.2.6 → 8.2 upgrade)
    → Bước 2 (ArgoCD sync)
      → Bước 3 (Populate product_embeddings_v2)
        → Bước 4 (Smoke test)
```

- **Bước 0** chạy được ngay, không ảnh hưởng hệ thống đang chạy
- **Bước 1** phải xong trước Bước 2 — copilot pod mới gọi `FT.SEARCH` trên Valkey 8.2
- **Bước 2** sẽ restart copilot pod — xác nhận pod lên healthy
- **Bước 3** không phụ thuộc Bước 1-2 (dùng chung RDS)

## Rollback

Nếu có vấn đề:
1. **Rollback Helm:** revert `values.yaml` env vars → ArgoCD sync
2. **Rollback Valkey:** `terraform apply` với `engine_version = "7.2"` (mất dữ liệu cache, không mất cart nếu cart TTL 60m đã bật)
3. **Rollback RDS:** `DROP SCHEMA ai CASCADE; DROP TABLE catalog.product_embeddings_v2;` (mất user_memory + embeddings data — chấp nhận được vì chưa có traffic thật)
