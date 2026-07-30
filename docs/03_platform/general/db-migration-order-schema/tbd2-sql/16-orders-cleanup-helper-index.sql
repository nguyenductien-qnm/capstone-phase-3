\set ON_ERROR_STOP on

-- Must run with psql autocommit, after order_payload is NOT NULL.
SET lock_timeout = '2s';
SET statement_timeout = '30min';

DROP INDEX CONCURRENTLY IF EXISTS checkout.checkout_orders_payload_missing_idx;
