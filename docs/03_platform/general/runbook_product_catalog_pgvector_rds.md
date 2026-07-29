# Product Catalog pgvector migration on RDS

The Helm PostgreSQL ConfigMap is only rendered when `components.postgresql.enabled` is true. Production uses the RDS instance `ecommerce-dev-postgres`, so that ConfigMap is not a production migration mechanism.

## Preconditions

- AIO confirms in writing that `arn:aws:iam::384511757667:role/techx-bedrock-invoke` allows `bedrock:InvokeModel` for `amazon.titan-embed-text-v2:0` in `us-east-1`.
- AIO confirms the trust policy accepts Account A (`804372444787`) with external ID `phase3-bedrock-cross-account`.
- Take the normal RDS snapshot/change record before applying DDL.
- Connect as `db_admin` (or an equivalent role). Do not run this as `otelu`; it cannot create extensions or grant privileges.

## Apply

From the repository root, run the checked-in idempotent migration against the production RDS endpoint:

```bash
psql "$RDS_ADMIN_URL" --set ON_ERROR_STOP=1 \\
  --file docs/runbook/sql/product-catalog-pgvector-rds.sql
```

Do not substitute `techx-tf1` or a local PostgreSQL container for the RDS endpoint.

## Seed embeddings

After the DDL succeeds, seed one embedding per catalog product before enabling the feature. The script uses the AWS default credential chain or the configured cross-account role and upserts through `otelu`:

```bash
AWS_REGION=us-east-1 \\
DB_CONNECTION_STRING="$RDS_APP_URL" \\
BEDROCK_AWS_ROLE_ARN="$BEDROCK_AWS_ROLE_ARN" \\
BEDROCK_AWS_EXTERNAL_ID="$BEDROCK_AWS_EXTERNAL_ID" \\
python3 techx-corp-platform/scripts/embed_products.py
```

Verify that the embedding row count matches the product count before rollout:

```sql
SELECT (SELECT count(*) FROM catalog.products) AS products,
       (SELECT count(*) FROM catalog.product_embeddings_v2) AS embeddings;
```

## Verify

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
SELECT to_regclass('catalog.product_embeddings_v2');
SELECT indexname FROM pg_indexes
WHERE schemaname = 'catalog' AND indexname = 'idx_product_embeddings_v2';
SELECT grantee, table_schema, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'otelu'
  AND table_schema = 'catalog'
ORDER BY table_name, privilege_type;
```

Expected permissions: `otelu` has `SELECT` on catalog tables, and `SELECT`/`INSERT`/`UPDATE` on `catalog.product_embeddings_v2`; it must not receive write privileges on `catalog.products`.

## Rollout gate

Only set `SEMANTIC_SEARCH_ENABLED=true` in the environment after the migration and the AIO cross-account confirmation have both passed. The sandbox AIO values file enables the flag; develop intentionally leaves it unset because that environment uses the in-cluster LLM and does not have the Bedrock egress/role configuration.
