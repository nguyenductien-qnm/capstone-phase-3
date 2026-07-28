\set ON_ERROR_STOP on

-- Forward compatibility gate.
-- Before running:
--   * every ready checkout pod must be dual_write
--   * every ready accounting pod must be dual_read
--   * no old ReplicaSet may still receive traffic
--   * 14-orders-verify.sql and 15-orders-enforce-not-null.sql must pass
--
-- This keeps order_metadata for the rollback horizon but makes it nullable so
-- payload-only write_new inserts can succeed.
SET lock_timeout = '2s';
SET statement_timeout = '15s';

DO $$
DECLARE
  payload_not_null BOOLEAN;
  legacy_not_null BOOLEAN;
  missing_payloads BIGINT;
  mismatched_payloads BIGINT;
BEGIN
  SELECT a.attnotnull
  INTO payload_not_null
  FROM pg_attribute AS a
  WHERE a.attrelid = 'checkout.orders'::regclass
    AND a.attname = 'order_payload'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  SELECT a.attnotnull
  INTO legacy_not_null
  FROM pg_attribute AS a
  WHERE a.attrelid = 'checkout.orders'::regclass
    AND a.attname = 'order_metadata'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  IF payload_not_null IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'order_payload must be NOT NULL before preparing write_new';
  END IF;
  IF legacy_not_null IS NULL THEN
    RAISE EXCEPTION 'order_metadata is missing; write_new preparation is not applicable';
  END IF;
  IF legacy_not_null IS FALSE THEN
    RAISE NOTICE 'order_metadata is already nullable; write_new is already prepared';
    RETURN;
  END IF;

  SELECT COUNT(*) FILTER (WHERE order_payload IS NULL),
         COUNT(*) FILTER (WHERE order_payload IS DISTINCT FROM order_metadata)
  INTO missing_payloads, mismatched_payloads
  FROM checkout.orders;

  IF missing_payloads <> 0 OR mismatched_payloads <> 0 THEN
    RAISE EXCEPTION
      'write_new preparation failed: missing payloads=%, mismatched payloads=%',
      missing_payloads, mismatched_payloads;
  END IF;
END
$$;

ALTER TABLE checkout.orders
  ALTER COLUMN order_metadata DROP NOT NULL;

SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'checkout'
  AND table_name = 'orders'
  AND column_name IN ('order_metadata', 'order_payload')
ORDER BY column_name;
