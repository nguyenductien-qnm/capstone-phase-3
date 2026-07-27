#!/usr/bin/env bash
# Mandate 20 (CDO-263): Simulate data loss by dropping drill schema in PostgreSQL
# Usage: ./scripts/dr/simulate-data-loss.sh [PGHOST] [PGPORT] [PGUSER] [PGDATABASE] [PGPASSWORD] [--force]

set -euo pipefail

HOST="${1:-${PGHOST:-localhost}}"
PORT="${2:-${PGPORT:-5432}}"
USER="${3:-${PGUSER:-postgres}}"
DB="${4:-${PGDATABASE:-accounting}}"
PASSWORD="${5:-${PGPASSWORD:-}}"
FORCE="${6:-}"

if [ -n "$PASSWORD" ]; then
  export PGPASSWORD="$PASSWORD"
fi

SCHEMA_NAME="drill_m20"

echo "=== MANDATE 20: SIMULATE DATA LOSS (T1 Event) ==="
echo "Target DB: ${HOST}:${PORT}/${DB} schema:${SCHEMA_NAME}"

# Safety Check: Schema MUST be drill_m20
if [ "$SCHEMA_NAME" != "drill_m20" ]; then
  echo "ERROR: Safety check failed! Target schema must strictly be 'drill_m20'."
  exit 1
fi

if [ "$FORCE" != "--force" ]; then
  read -p "WARNING: You are about to DROP SCHEMA ${SCHEMA_NAME} CASCADE on ${HOST}. Continue? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

T1_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "[1/2] Dropping schema '${SCHEMA_NAME}'..."
psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -c "DROP SCHEMA IF EXISTS ${SCHEMA_NAME} CASCADE;"

echo "[2/2] Data loss event executed."
echo "=================================================="
echo "  T1 (Data Loss Event) UTC Timestamp: ${T1_TIMESTAMP}"
echo "  Status                           : Schema ${SCHEMA_NAME} DROPPED"
echo "=================================================="
