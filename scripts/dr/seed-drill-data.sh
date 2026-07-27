#!/usr/bin/env bash
# Mandate 20 (CDO-262): Seed drill data into PostgreSQL database & compute T0 baseline checksum
# Usage: ./scripts/dr/seed-drill-data.sh [PGHOST] [PGPORT] [PGUSER] [PGDATABASE] [PGPASSWORD]

set -euo pipefail

HOST="${1:-${PGHOST:-localhost}}"
PORT="${2:-${PGPORT:-5432}}"
USER="${3:-${PGUSER:-postgres}}"
DB="${4:-${PGDATABASE:-accounting}}"
PASSWORD="${5:-${PGPASSWORD:-}}"

if [ -n "$PASSWORD" ]; then
  export PGPASSWORD="$PASSWORD"
fi

SCHEMA_NAME="drill_m20"
TABLE_NAME="orders_audit"

echo "=== MANDATE 20: SEED DRILL DATA (T0 Baseline) ==="
echo "Target DB: ${HOST}:${PORT}/${DB} schema:${SCHEMA_NAME}"

T0_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "[1/3] Creating schema '${SCHEMA_NAME}' and table '${TABLE_NAME}'..."
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" <<EOF
CREATE SCHEMA IF NOT EXISTS ${SCHEMA_NAME};

CREATE TABLE IF NOT EXISTS ${SCHEMA_NAME}.${TABLE_NAME} (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    customer_id VARCHAR(64) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
EOF

echo "[2/3] Seeding test records into ${SCHEMA_NAME}.${TABLE_NAME}..."
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" <<EOF
INSERT INTO ${SCHEMA_NAME}.${TABLE_NAME} (order_id, customer_id, amount, status, created_at)
VALUES 
  ('ORD-DRILL-001', 'CUST-101', 199.99, 'COMPLETED', NOW() - INTERVAL '10 minutes'),
  ('ORD-DRILL-002', 'CUST-102', 49.50, 'COMPLETED', NOW() - INTERVAL '8 minutes'),
  ('ORD-DRILL-003', 'CUST-103', 1250.00, 'PROCESSING', NOW() - INTERVAL '5 minutes'),
  ('ORD-DRILL-004', 'CUST-104', 89.00, 'COMPLETED', NOW() - INTERVAL '3 minutes'),
  ('ORD-DRILL-005', 'CUST-105', 310.25, 'PENDING', NOW() - INTERVAL '1 minute');
EOF

echo "[3/3] Calculating T0 Row Count and MD5 Checksum..."
SUMMARY=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -t -A -c "
SELECT 
  count(*) || '|' || md5(string_agg(id::text || order_id || amount::text || status, ',' ORDER BY id))
FROM ${SCHEMA_NAME}.${TABLE_NAME};
")

ROW_COUNT=$(echo "$SUMMARY" | cut -d'|' -f1)
MD5_HASH=$(echo "$SUMMARY" | cut -d'|' -f2)

echo "=================================================="
echo "  T0 UTC Timestamp : ${T0_TIMESTAMP}"
echo "  Row Count        : ${ROW_COUNT}"
echo "  MD5 Checksum     : ${MD5_HASH}"
echo "=================================================="
echo "SAVE THIS TIMESTAMP FOR PITR RESTORE: ${T0_TIMESTAMP}"
