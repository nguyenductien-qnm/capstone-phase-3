\set ON_ERROR_STOP on

-- Destructive contract. Run only after:
--   * checkout phase = write_new on every ready pod
--   * accounting phase = read_new on every ready pod
--   * rollback horizon has elapsed
--   * no old ReplicaSet can be scaled back up
--   * 14-orders-verify.sql reports zero missing/mismatch rows
SET lock_timeout = '2s';
SET statement_timeout = '15s';

ALTER TABLE checkout.orders
  DROP COLUMN IF EXISTS order_metadata;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'checkout'
  AND table_name = 'orders'
ORDER BY ordinal_position;
