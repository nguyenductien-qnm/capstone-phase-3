\set ON_ERROR_STOP on

DO $$
DECLARE
  rollback_mismatches BIGINT;
BEGIN
  SELECT COUNT(*)
  INTO rollback_mismatches
  FROM checkout.orders
  WHERE order_metadata IS DISTINCT FROM order_payload
    AND order_payload IS NOT NULL;

  IF rollback_mismatches <> 0 THEN
    RAISE EXCEPTION 'rollback verification failed: % rows still differ', rollback_mismatches;
  END IF;
END
$$;

SELECT COUNT(*) AS rollback_mismatches
FROM checkout.orders
WHERE order_metadata IS DISTINCT FROM order_payload
  AND order_payload IS NOT NULL;
