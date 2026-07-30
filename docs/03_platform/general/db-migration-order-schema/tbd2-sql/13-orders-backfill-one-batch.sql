\set ON_ERROR_STOP on
\if :{?batch_size}
\else
  \set batch_size 500
\endif

SET lock_timeout = '2s';
SET statement_timeout = '30s';

WITH picked AS (
  SELECT order_id
  FROM checkout.orders
  WHERE order_payload IS NULL
  ORDER BY order_id
  FOR UPDATE SKIP LOCKED
  LIMIT :batch_size
),
updated AS (
  UPDATE checkout.orders AS o
  SET order_payload = o.order_metadata,
      updated_at = clock_timestamp()
  FROM picked
  WHERE o.order_id = picked.order_id
  RETURNING o.order_id
)
SELECT COUNT(*) AS rows_backfilled
FROM updated;
