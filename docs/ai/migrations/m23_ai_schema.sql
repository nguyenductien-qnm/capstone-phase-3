-- MANDATE-23 — durable user-memory schema for RDS production.
-- L2 semantic cache lives in ElastiCache Valkey 8.2 Search; RDS stores only
-- durable cross-session memory. Run with an RDS owner account:
--   psql "$RDS_URL" -v ON_ERROR_STOP=1 -f m23_ai_schema.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS ai;

CREATE TABLE IF NOT EXISTS ai.user_memory (
    user_id    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, key)
);

GRANT USAGE ON SCHEMA ai TO otelu;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai.user_memory TO otelu;

COMMIT;

-- Verify:
--   \dn
--   \dt ai.*
