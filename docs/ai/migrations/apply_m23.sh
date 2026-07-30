#!/usr/bin/env bash
# Apply and verify MANDATE-23 durable memory schema on the target PostgreSQL/RDS database.
set -euo pipefail

: "${RDS_URL:?Set RDS_URL to the target PostgreSQL connection string}"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

psql "$RDS_URL" -v ON_ERROR_STOP=1 -f "$SCRIPT_DIR/m23_ai_schema.sql"

verified=$(psql "$RDS_URL" -v ON_ERROR_STOP=1 -Atc "
SELECT CASE WHEN
  to_regclass('ai.user_memory') IS NOT NULL
  AND has_schema_privilege('otelu', 'ai', 'USAGE')
  AND has_table_privilege('otelu', 'ai.user_memory', 'SELECT,INSERT,UPDATE,DELETE')
THEN 'ok' ELSE 'missing' END;")

if [[ "$verified" != "ok" ]]; then
  echo "MANDATE-23 verification failed: table or otelu grants are missing" >&2
  exit 1
fi

echo "MANDATE-23 verified: ai.user_memory exists and otelu has required grants"
