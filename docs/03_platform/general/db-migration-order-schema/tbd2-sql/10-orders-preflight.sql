\set ON_ERROR_STOP on
\echo 'M09/TBD2 orders migration preflight'

DO $$
DECLARE
  orders_oid REGCLASS := to_regclass('checkout.orders');
  owner_oid OID;
  legacy_not_null BOOLEAN;
  long_transactions INTEGER;
BEGIN
  IF pg_is_in_recovery() THEN
    RAISE EXCEPTION 'orders migration must run on the writer, not a replica';
  END IF;

  IF orders_oid IS NULL THEN
    RAISE EXCEPTION 'required table checkout.orders does not exist';
  END IF;

  SELECT c.relowner
  INTO owner_oid
  FROM pg_class AS c
  WHERE c.oid = orders_oid;

  IF NOT pg_has_role(current_user, owner_oid, 'USAGE') THEN
    RAISE EXCEPTION 'current role % is not a member of the checkout.orders owner role', current_user;
  END IF;

  IF NOT has_table_privilege(current_user, orders_oid, 'SELECT,INSERT,UPDATE') THEN
    RAISE EXCEPTION 'current role % lacks SELECT, INSERT, or UPDATE on checkout.orders', current_user;
  END IF;

  SELECT a.attnotnull
  INTO legacy_not_null
  FROM pg_attribute AS a
  WHERE a.attrelid = orders_oid
    AND a.attname = 'order_metadata'
    AND a.attnum > 0
    AND NOT a.attisdropped;

  IF legacy_not_null IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'legacy order_metadata must exist and be NOT NULL before migration';
  END IF;

  SELECT COUNT(*)
  INTO long_transactions
  FROM pg_stat_activity
  WHERE datname = current_database()
    AND pid <> pg_backend_pid()
    AND xact_start < clock_timestamp() - interval '5 minutes';

  IF long_transactions > 0 THEN
    RAISE EXCEPTION 'preflight found % transaction(s) older than 5 minutes', long_transactions;
  END IF;
END
$$;

SELECT clock_timestamp() AS observed_at,
       current_database() AS database_name,
       current_user AS database_user,
       pg_is_in_recovery() AS is_replica;

SELECT to_regclass('checkout.orders') AS orders_table,
       has_table_privilege(current_user, 'checkout.orders', 'SELECT,INSERT,UPDATE') AS data_privileges;

SELECT a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       a.attnotnull AS not_null
FROM pg_attribute AS a
WHERE a.attrelid = 'checkout.orders'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum;

SELECT COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE created_at >= clock_timestamp() - interval '15 minutes') AS rows_last_15m,
       pg_size_pretty(pg_total_relation_size('checkout.orders')) AS total_size
FROM checkout.orders;

SELECT pid,
       usename,
       state,
       wait_event_type,
       wait_event,
       clock_timestamp() - xact_start AS transaction_age
FROM pg_stat_activity
WHERE datname = current_database()
  AND xact_start IS NOT NULL
ORDER BY xact_start
LIMIT 20;

SELECT locktype,
       mode,
       granted,
       COUNT(*) AS lock_count
FROM pg_locks
WHERE relation = 'checkout.orders'::regclass
GROUP BY locktype, mode, granted
ORDER BY granted, mode;
