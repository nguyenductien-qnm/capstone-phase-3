\set ON_ERROR_STOP on

-- Run only after every ready checkout pod is dual_write and no legacy
-- ReplicaSet can receive traffic. The NOT VALID check below still constrains
-- new writes immediately, so a legacy writer would fail as soon as it exists.
SET lock_timeout = '2s';
SET statement_timeout = '30min';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'checkout.orders'::regclass
      AND conname = 'checkout_orders_payload_nn'
  ) THEN
    ALTER TABLE checkout.orders
      ADD CONSTRAINT checkout_orders_payload_nn
      CHECK (order_payload IS NOT NULL) NOT VALID;
  END IF;
END
$$;

-- Validation scans existing rows without holding ACCESS EXCLUSIVE for the
-- duration. It still consumes I/O and must be monitored under load.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'checkout.orders'::regclass
      AND conname = 'checkout_orders_payload_nn'
      AND NOT convalidated
  ) THEN
    ALTER TABLE checkout.orders
      VALIDATE CONSTRAINT checkout_orders_payload_nn;
  END IF;
END
$$;

SET lock_timeout = '2s';
ALTER TABLE checkout.orders
  ALTER COLUMN order_payload SET NOT NULL;

SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'checkout'
  AND table_name = 'orders'
  AND column_name = 'order_payload';

SELECT conname, convalidated
FROM pg_constraint
WHERE conrelid = 'checkout.orders'::regclass
  AND conname = 'checkout_orders_payload_nn';
