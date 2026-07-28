\set ON_ERROR_STOP on

-- Post-write_new, pre-contract verification.
-- Run only after every checkout pod is write_new, every accounting pod is
-- read_new, the rollback horizon has elapsed, and old ReplicaSets cannot be
-- scaled back up. New rows are allowed to have NULL order_metadata.
DO $$
DECLARE
  missing_payloads BIGINT;
  incomplete_idempotent BIGINT;
  duplicate_idempotency_keys BIGINT;
  ready_unique_index BOOLEAN;
  payload_not_null BOOLEAN;
  legacy_nullable BOOLEAN;
BEGIN
  SELECT COUNT(*) FILTER (WHERE order_payload IS NULL),
         COUNT(*) FILTER (
           WHERE num_nonnulls(
             idempotency_key,
             idempotency_request_hash,
             order_result
           ) NOT IN (0, 3)
         )
  INTO missing_payloads, incomplete_idempotent
  FROM checkout.orders;

  SELECT COUNT(*)
  INTO duplicate_idempotency_keys
  FROM (
    SELECT 1
    FROM checkout.orders
    WHERE idempotency_key IS NOT NULL
    GROUP BY user_id, idempotency_key
    HAVING COUNT(*) > 1
  ) AS duplicates;

  SELECT COALESCE(bool_and(i.indisready AND i.indisvalid), FALSE)
  INTO ready_unique_index
  FROM pg_index AS i
  JOIN pg_class AS c ON c.oid = i.indexrelid
  WHERE i.indrelid = 'checkout.orders'::regclass
    AND c.relname = 'checkout_orders_user_idempotency_uidx';

  SELECT a.attnotnull
  INTO payload_not_null
  FROM pg_attribute AS a
  WHERE a.attrelid = 'checkout.orders'::regclass
    AND a.attname = 'order_payload'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  SELECT NOT a.attnotnull
  INTO legacy_nullable
  FROM pg_attribute AS a
  WHERE a.attrelid = 'checkout.orders'::regclass
    AND a.attname = 'order_metadata'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  IF missing_payloads <> 0
     OR incomplete_idempotent <> 0
     OR duplicate_idempotency_keys <> 0
     OR ready_unique_index IS DISTINCT FROM TRUE
     OR payload_not_null IS DISTINCT FROM TRUE
     OR legacy_nullable IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION
      'pre-contract verification failed: missing=%, incomplete_idempotent=%, duplicate_keys=%, unique_index_ready=%, payload_not_null=%, legacy_nullable=%',
      missing_payloads, incomplete_idempotent, duplicate_idempotency_keys,
      ready_unique_index, payload_not_null, legacy_nullable;
  END IF;
END
$$;

SELECT COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE order_payload IS NULL) AS payload_missing,
       COUNT(*) FILTER (WHERE order_metadata IS NULL) AS payload_only_rows
FROM checkout.orders;
