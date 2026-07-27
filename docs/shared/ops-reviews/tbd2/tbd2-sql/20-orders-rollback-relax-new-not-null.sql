\set ON_ERROR_STOP on

-- Run only after 19-orders-rollback-verify.sql passes and before deploying
-- an old image that writes order_metadata only. Expanded columns and indexes
-- remain in place, so a later forward migration is idempotent.
SET lock_timeout = '2s';
SET statement_timeout = '15s';

ALTER TABLE checkout.orders
  ALTER COLUMN order_payload DROP NOT NULL;

ALTER TABLE checkout.orders
  DROP CONSTRAINT IF EXISTS checkout_orders_payload_nn;

SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'checkout'
  AND table_name = 'orders'
  AND column_name = 'order_payload';
