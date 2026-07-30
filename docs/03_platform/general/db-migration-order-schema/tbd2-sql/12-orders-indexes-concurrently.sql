\set ON_ERROR_STOP on

-- Must run with psql autocommit. CREATE INDEX CONCURRENTLY is not allowed
-- inside BEGIN/COMMIT.
SET lock_timeout = '2s';
SET statement_timeout = '30min';

SELECT EXISTS (
  SELECT 1
  FROM pg_index AS i
  JOIN pg_class AS c ON c.oid = i.indexrelid
  WHERE i.indrelid = 'checkout.orders'::regclass
    AND c.relname = 'checkout_orders_user_idempotency_uidx'
    AND (NOT i.indisready OR NOT i.indisvalid)
) AS drop_invalid_idempotency_index
\gset

\if :drop_invalid_idempotency_index
DROP INDEX CONCURRENTLY checkout.checkout_orders_user_idempotency_uidx;
\endif

SELECT EXISTS (
  SELECT 1
  FROM pg_index AS i
  JOIN pg_class AS c ON c.oid = i.indexrelid
  WHERE i.indrelid = 'checkout.orders'::regclass
    AND c.relname = 'checkout_orders_payload_missing_idx'
    AND (NOT i.indisready OR NOT i.indisvalid)
) AS drop_invalid_payload_index
\gset

\if :drop_invalid_payload_index
DROP INDEX CONCURRENTLY checkout.checkout_orders_payload_missing_idx;
\endif

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS
  checkout_orders_user_idempotency_uidx
ON checkout.orders (user_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS
  checkout_orders_payload_missing_idx
ON checkout.orders (order_id)
WHERE order_payload IS NULL;

DO $$
DECLARE
  invalid_indexes TEXT;
BEGIN
  SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
  INTO invalid_indexes
  FROM pg_index AS i
  JOIN pg_class AS c ON c.oid = i.indexrelid
  WHERE i.indrelid = 'checkout.orders'::regclass
    AND c.relname IN (
      'checkout_orders_user_idempotency_uidx',
      'checkout_orders_payload_missing_idx'
    )
    AND (NOT i.indisready OR NOT i.indisvalid);

  IF invalid_indexes IS NOT NULL THEN
    RAISE EXCEPTION 'concurrent index build left invalid indexes: %', invalid_indexes;
  END IF;

  IF to_regclass('checkout.checkout_orders_user_idempotency_uidx') IS NULL
     OR to_regclass('checkout.checkout_orders_payload_missing_idx') IS NULL THEN
    RAISE EXCEPTION 'one or more required checkout indexes are missing';
  END IF;
END
$$;

SELECT c.relname AS index_name,
       i.indisready,
       i.indisvalid,
       pg_get_indexdef(i.indexrelid) AS definition
FROM pg_index AS i
JOIN pg_class AS c ON c.oid = i.indexrelid
WHERE i.indrelid = 'checkout.orders'::regclass
  AND c.relname IN (
    'checkout_orders_user_idempotency_uidx',
    'checkout_orders_payload_missing_idx'
  )
ORDER BY c.relname;
