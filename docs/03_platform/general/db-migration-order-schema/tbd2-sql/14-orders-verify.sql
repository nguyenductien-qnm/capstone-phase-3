\set ON_ERROR_STOP on

-- Pre-write_new verification.
-- Run after every checkout writer is dual_write and backfill step 13 reports
-- zero rows. At this gate both columns must still match. Do not reuse this
-- script after write_new starts; use 16b-orders-verify-pre-contract.sql.
SELECT COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE order_payload IS NULL) AS payload_missing,
       COUNT(*) FILTER (
         WHERE order_payload IS DISTINCT FROM order_metadata
       ) AS payload_mismatch,
       COUNT(*) FILTER (
         WHERE idempotency_key IS NOT NULL
           AND (
             idempotency_request_hash IS NULL
             OR order_result IS NULL
           )
       ) AS incomplete_idempotent_rows
FROM checkout.orders;

SELECT user_id,
       idempotency_key,
       COUNT(*) AS duplicate_count
FROM checkout.orders
WHERE idempotency_key IS NOT NULL
GROUP BY user_id, idempotency_key
HAVING COUNT(*) > 1;

SELECT c.relname AS index_name,
       i.indisready,
       i.indisvalid
FROM pg_index AS i
JOIN pg_class AS c ON c.oid = i.indexrelid
WHERE i.indrelid = 'checkout.orders'::regclass
  AND c.relname IN (
    'checkout_orders_user_idempotency_uidx',
    'checkout_orders_payload_missing_idx'
  )
ORDER BY c.relname;

DO $$
DECLARE
  missing_payloads BIGINT;
  mismatched_payloads BIGINT;
  incomplete_idempotent BIGINT;
  duplicate_idempotency_keys BIGINT;
  ready_indexes INTEGER;
BEGIN
  SELECT COUNT(*) FILTER (WHERE order_payload IS NULL),
         COUNT(*) FILTER (WHERE order_payload IS DISTINCT FROM order_metadata),
         COUNT(*) FILTER (
           WHERE idempotency_key IS NOT NULL
             AND (idempotency_request_hash IS NULL OR order_result IS NULL)
         )
  INTO missing_payloads, mismatched_payloads, incomplete_idempotent
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

  SELECT COUNT(*)
  INTO ready_indexes
  FROM pg_index AS i
  JOIN pg_class AS c ON c.oid = i.indexrelid
  WHERE i.indrelid = 'checkout.orders'::regclass
    AND c.relname IN (
      'checkout_orders_user_idempotency_uidx',
      'checkout_orders_payload_missing_idx'
    )
    AND i.indisready
    AND i.indisvalid;

  IF missing_payloads <> 0
     OR mismatched_payloads <> 0
     OR incomplete_idempotent <> 0
     OR duplicate_idempotency_keys <> 0
     OR ready_indexes <> 2 THEN
    RAISE EXCEPTION
      'verification failed: missing=%, mismatch=%, incomplete_idempotent=%, duplicate_keys=%, ready_indexes=% (expected 2)',
      missing_payloads, mismatched_payloads, incomplete_idempotent,
      duplicate_idempotency_keys, ready_indexes;
  END IF;
END
$$;
