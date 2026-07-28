#!/usr/bin/env bash
set -euo pipefail

SQL_DIR="docs/shared/ops-reviews/tbd2/tbd2-sql"
FORWARD_DB="orders_migration_forward"
ROLLBACK_DB="orders_migration_rollback"

psql_db() {
  local database=$1
  shift
  psql --no-psqlrc --set=ON_ERROR_STOP=1 --dbname="$database" "$@"
}

create_legacy_fixture() {
  local database=$1
  dropdb --if-exists "$database"
  createdb "$database"
  psql_db "$database" <<'SQL'
CREATE SCHEMA checkout;

CREATE TABLE checkout.orders (
  order_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  currency_code TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL DEFAULT 'PROCESSING',
  order_metadata JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO checkout.orders (
  order_id,
  user_id,
  order_metadata
) VALUES (
  'legacy-order',
  'legacy-user',
  '{"userId":"legacy-user","userCurrency":"USD","address":{"country":"TH"},"orderItems":[{"item":{"productId":"legacy-product","quantity":1},"cost":{"currencyCode":"USD","units":10,"nanos":0}}],"shippingCostLocalized":{"currencyCode":"USD","units":1,"nanos":0},"total":{"currencyCode":"USD","units":11,"nanos":0}}'
);
SQL
}

run_expand_and_dual_write() {
  local database=$1

  psql_db "$database" --file="$SQL_DIR/10-orders-preflight.sql"
  psql_db "$database" --file="$SQL_DIR/11-orders-expand.sql"
  psql_db "$database" --file="$SQL_DIR/12-orders-indexes-concurrently.sql"

  psql_db "$database" <<'SQL'
INSERT INTO checkout.orders (
  order_id,
  user_id,
  order_metadata,
  order_payload,
  idempotency_key,
  idempotency_request_hash,
  order_result
) VALUES (
  'dual-order',
  'dual-user',
  '{"userId":"dual-user","userCurrency":"USD","address":{"country":"TH"},"orderItems":[{"item":{"productId":"dual-product","quantity":1},"cost":{"currencyCode":"USD","units":20,"nanos":0}}],"shippingCostLocalized":{"currencyCode":"USD","units":1,"nanos":0},"total":{"currencyCode":"USD","units":21,"nanos":0}}',
  '{"userId":"dual-user","userCurrency":"USD","address":{"country":"TH"},"orderItems":[{"item":{"productId":"dual-product","quantity":1},"cost":{"currencyCode":"USD","units":20,"nanos":0}}],"shippingCostLocalized":{"currencyCode":"USD","units":1,"nanos":0},"total":{"currencyCode":"USD","units":21,"nanos":0}}',
  'dual-write-key',
  'dual-write-hash',
  '{"orderId":"dual-order"}'
);
SQL

  while [ "$(psql_db "$database" --tuples-only --no-align --command='SELECT COUNT(*) FROM checkout.orders WHERE order_payload IS NULL')" != "0" ]; do
    psql_db "$database" --set=batch_size=10 --file="$SQL_DIR/13-orders-backfill-one-batch.sql"
  done

  psql_db "$database" --file="$SQL_DIR/14-orders-verify.sql"
  psql_db "$database" --file="$SQL_DIR/15-orders-enforce-not-null.sql"
  psql_db "$database" --file="$SQL_DIR/16-orders-cleanup-helper-index.sql"
}

assert_write_new_blocked_before_gate() {
  local database=$1

  if psql_db "$database" <<'SQL'
INSERT INTO checkout.orders (
  order_id,
  user_id,
  order_payload,
  idempotency_key,
  idempotency_request_hash,
  order_result
) VALUES (
  'premature-write-new',
  'premature-user',
  '{}',
  'premature-key',
  'premature-hash',
  '{"orderId":"premature-write-new"}'
);
SQL
  then
    echo "write_new insert unexpectedly succeeded before order_metadata was relaxed" >&2
    exit 1
  fi
}

insert_write_new_row() {
  local database=$1
  local order_id=$2
  local user_id=$3

  psql_db "$database" --set=order_id="$order_id" --set=user_id="$user_id" <<'SQL'
INSERT INTO checkout.orders (
  order_id,
  user_id,
  order_payload,
  idempotency_key,
  idempotency_request_hash,
  order_result
) VALUES (
  :'order_id',
  :'user_id',
  jsonb_build_object(
    'userId', :'user_id',
    'userCurrency', 'USD',
    'address', jsonb_build_object('country', 'TH'),
    'orderItems', jsonb_build_array(
      jsonb_build_object(
        'item', jsonb_build_object('productId', 'new-product', 'quantity', 1),
        'cost', jsonb_build_object('currencyCode', 'USD', 'units', 30, 'nanos', 0)
      )
    ),
    'shippingCostLocalized', jsonb_build_object('currencyCode', 'USD', 'units', 1, 'nanos', 0),
    'total', jsonb_build_object('currencyCode', 'USD', 'units', 31, 'nanos', 0)
  ),
  :'order_id' || '-key',
  :'order_id' || '-hash',
  jsonb_build_object('orderId', :'order_id')
);
SQL
}

run_forward_contract_test() {
  create_legacy_fixture "$FORWARD_DB"
  run_expand_and_dual_write "$FORWARD_DB"
  assert_write_new_blocked_before_gate "$FORWARD_DB"

  psql_db "$FORWARD_DB" --file="$SQL_DIR/16a-orders-prepare-write-new.sql"
  insert_write_new_row "$FORWARD_DB" "write-new-order" "write-new-user"

  psql_db "$FORWARD_DB" <<'SQL'
INSERT INTO checkout.orders (
  order_id,
  user_id,
  order_payload,
  idempotency_key
) VALUES (
  'broken-idempotency-order',
  'broken-user',
  '{}',
  'broken-key'
);
SQL

  if psql_db "$FORWARD_DB" --file="$SQL_DIR/16b-orders-verify-pre-contract.sql"; then
    echo "pre-contract verification accepted an incomplete idempotency tuple" >&2
    exit 1
  fi

  psql_db "$FORWARD_DB" --command="DELETE FROM checkout.orders WHERE order_id = 'broken-idempotency-order'"
  psql_db "$FORWARD_DB" --file="$SQL_DIR/16b-orders-verify-pre-contract.sql"
  psql_db "$FORWARD_DB" --file="$SQL_DIR/17-orders-contract-drop-legacy.sql"

  psql_db "$FORWARD_DB" <<'SQL'
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'checkout'
      AND table_name = 'orders'
      AND column_name = 'order_metadata'
  ) THEN
    RAISE EXCEPTION 'contract did not drop order_metadata';
  END IF;

  IF EXISTS (SELECT 1 FROM checkout.orders WHERE order_payload IS NULL) THEN
    RAISE EXCEPTION 'contract left a row without order_payload';
  END IF;
END
$$;
SQL
}

run_rollback_test() {
  create_legacy_fixture "$ROLLBACK_DB"
  run_expand_and_dual_write "$ROLLBACK_DB"
  psql_db "$ROLLBACK_DB" --file="$SQL_DIR/16a-orders-prepare-write-new.sql"
  insert_write_new_row "$ROLLBACK_DB" "rollback-order" "rollback-user"

  while [ "$(psql_db "$ROLLBACK_DB" --tuples-only --no-align --command='SELECT COUNT(*) FROM checkout.orders WHERE order_metadata IS DISTINCT FROM order_payload')" != "0" ]; do
    psql_db "$ROLLBACK_DB" --set=batch_size=10 --file="$SQL_DIR/18-orders-rollback-one-batch.sql"
  done

  psql_db "$ROLLBACK_DB" --file="$SQL_DIR/19-orders-rollback-verify.sql"
  psql_db "$ROLLBACK_DB" --file="$SQL_DIR/20-orders-rollback-relax-new-not-null.sql"

  psql_db "$ROLLBACK_DB" <<'SQL'
INSERT INTO checkout.orders (
  order_id,
  user_id,
  order_metadata
) VALUES (
  'legacy-after-rollback',
  'legacy-after-rollback-user',
  '{"userId":"legacy-after-rollback-user"}'
);

DO $$
DECLARE
  metadata_not_null BOOLEAN;
  payload_not_null BOOLEAN;
BEGIN
  SELECT a.attnotnull
  INTO metadata_not_null
  FROM pg_attribute AS a
  WHERE a.attrelid = 'checkout.orders'::regclass
    AND a.attname = 'order_metadata'
    AND NOT a.attisdropped;

  SELECT a.attnotnull
  INTO payload_not_null
  FROM pg_attribute AS a
  WHERE a.attrelid = 'checkout.orders'::regclass
    AND a.attname = 'order_payload'
    AND NOT a.attisdropped;

  IF metadata_not_null IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'rollback did not restore order_metadata NOT NULL';
  END IF;
  IF payload_not_null IS DISTINCT FROM FALSE THEN
    RAISE EXCEPTION 'rollback did not relax order_payload NOT NULL';
  END IF;
END
$$;
SQL
}

run_forward_contract_test
run_rollback_test
echo "orders migration integration: PASS"
