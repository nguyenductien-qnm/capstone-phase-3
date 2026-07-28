\set ON_ERROR_STOP on

SET lock_timeout = '2s';
SET statement_timeout = '15s';

ALTER TABLE checkout.orders
  ADD COLUMN IF NOT EXISTS order_payload JSONB;

ALTER TABLE checkout.orders
  ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

ALTER TABLE checkout.orders
  ADD COLUMN IF NOT EXISTS idempotency_request_hash TEXT;

ALTER TABLE checkout.orders
  ADD COLUMN IF NOT EXISTS order_result JSONB;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'checkout'
  AND table_name = 'orders'
  AND column_name IN (
    'order_metadata',
    'order_payload',
    'idempotency_key',
    'idempotency_request_hash',
    'order_result'
  )
ORDER BY ordinal_position;
