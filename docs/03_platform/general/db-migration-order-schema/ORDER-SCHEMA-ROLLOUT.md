# Checkout order schema rollout

The SQL files in `tbd2-sql` are operational gates, not a single transaction.
Retry a step after resolving a lock timeout; do not increase the short DDL lock
timeouts while checkout is serving traffic.

## Forward rollout

1. Run `10-orders-preflight.sql`.
2. Run `11-orders-expand.sql`.
3. Run `12-orders-indexes-concurrently.sql` with psql autocommit.
4. Roll every accounting pod to `ACCOUNTING_ORDER_SCHEMA_PHASE=dual_read`.
   Confirm the old ReplicaSet has no active Kafka consumer.
5. Roll every checkout pod to `CHECKOUT_ORDER_SCHEMA_PHASE=dual_write`.
   Confirm no legacy writer can receive traffic.
6. Run `13-orders-backfill-one-batch.sql` repeatedly until it updates zero rows.
7. Run `14-orders-verify.sql`.
8. Run `15-orders-enforce-not-null.sql`.
9. Run `16-orders-cleanup-helper-index.sql` with psql autocommit.
10. Run `16a-orders-prepare-write-new.sql`.
11. Roll every checkout pod to `CHECKOUT_ORDER_SCHEMA_PHASE=write_new`.
12. Roll every accounting pod to `ACCOUNTING_ORDER_SCHEMA_PHASE=read_new`.
13. After the rollback horizon closes, disable old ReplicaSets and run
    `17-orders-contract-drop-legacy.sql`. The contract script executes
    `16b-orders-verify-pre-contract.sql` itself before dropping the old column.

Never move checkout to `write_new` before step 10. Never contract while an old
checkout or accounting ReplicaSet can be restarted.

## Pre-contract rollback

1. Roll every checkout pod back to `dual_write` and drain `write_new` traffic.
2. Keep accounting on `dual_read`.
3. Run `18-orders-rollback-one-batch.sql` repeatedly until it updates zero rows.
4. Run `19-orders-rollback-verify.sql`.
5. Run `20-orders-rollback-relax-new-not-null.sql`.
6. Only then deploy an old legacy-only checkout image.

After the contract step drops `order_metadata`, this legacy-image rollback is
no longer available. Recovery then requires re-expanding and backfilling the
legacy column before an old image can be deployed.
