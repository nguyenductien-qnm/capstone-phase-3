-- Product Catalog semantic-search migration for the production RDS database.
-- Run as db_admin (or another role allowed to CREATE EXTENSION and GRANT).
-- Safe to re-run.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS catalog.product_embeddings_v2 (
    product_id VARCHAR(255) PRIMARY KEY,
    embedding VECTOR(1024)
);

CREATE INDEX IF NOT EXISTS idx_product_embeddings_v2
    ON catalog.product_embeddings_v2
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

GRANT USAGE ON SCHEMA catalog TO otelu;
GRANT SELECT ON ALL TABLES IN SCHEMA catalog TO otelu;
GRANT SELECT, INSERT, UPDATE ON catalog.product_embeddings_v2 TO otelu;
