\set ON_ERROR_STOP on
\if :{?batch_size}
\else
  \set batch_size 500
\endif

-- Pre-contract rollback path. Keep the legacy column until the rollback
-- horizon expires and copy any write_new rows back in bounded batches.
-- Run 19 verify and 20 relax before rolling an old legacy-only image back.
-- A phase-aware rollback may stay on dual_write/dual_read and skip step 20.
-- Expanded columns remain in place during a live rollback.
SET lock_timeout = '2s';
SET statement_timeout = '30s';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_attribute
    WHERE attrelid = 'checkout.orders'::regclass
      AND attname = 'order_metadata'
      AND attnum > 0
      AND NOT attisdropped
  ) THEN
    RAISE EXCEPTION 'pre-contract rollback is unavailable: order_metadata was already dropped';
  END IF;
END
$$;

WITH picked AS (
  SELECT order_id
  FROM checkout.orders
  WHERE order_metadata IS DISTINCT FROM order_payload
    AND order_payload IS NOT NULL
  ORDER BY order_id
  FOR UPDATE SKIP LOCKED
  LIMIT :batch_size
),
updated AS (
  UPDATE checkout.orders AS o
  SET order_metadata = o.order_payload,
      updated_at = clock_timestamp()
  FROM picked
  WHERE o.order_id = picked.order_id
  RETURNING o.order_id
)
SELECT COUNT(*) AS rows_rolled_back
FROM updated;
