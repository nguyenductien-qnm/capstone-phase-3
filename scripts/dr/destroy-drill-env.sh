#!/usr/bin/env bash
# Mandate 20 (CDO-271): Cleanup temporary RDS drill instance
# Usage: ./scripts/dr/destroy-drill-env.sh <TARGET_DRILL_DB_IDENTIFIER> [REGION]

set -euo pipefail

TARGET_INSTANCE="${1:-}"
REGION="${2:-us-east-1}"

if [ -z "$TARGET_INSTANCE" ]; then
  echo "Usage: $0 <TARGET_DRILL_DB_IDENTIFIER> [REGION]"
  echo "Example: $0 ecommerce-dev-postgres-primary-drill us-east-1"
  exit 1
fi

echo "=== MANDATE 20: CLEANUP DRILL ENVIRONMENT ==="
echo "Target Instance: ${TARGET_INSTANCE}"
echo "Region         : ${REGION}"

# Safety Rule M7: Must end with '-drill' to prevent accidental deletion of primary production/develop instances
if [[ "$TARGET_INSTANCE" != *"-drill" ]]; then
  echo "CRITICAL ERROR: Safety check failed!"
  echo "Target DB identifier '${TARGET_INSTANCE}' does NOT end with '-drill'."
  echo "Refusing to modify or delete non-drill RDS instances!"
  exit 1
fi

echo "[1/2] Disabling deletion protection on drill instance ${TARGET_INSTANCE}..."
aws rds modify-db-instance \
  --db-instance-identifier "$TARGET_INSTANCE" \
  --no-deletion-protection \
  --apply-immediately \
  --region "$REGION" > /dev/null

echo "Waiting for deletion protection modification to process..."
aws rds wait db-instance-available \
  --db-instance-identifier "$TARGET_INSTANCE" \
  --region "$REGION"

echo "[2/2] Deleting RDS drill instance ${TARGET_INSTANCE}..."
aws rds delete-db-instance \
  --db-instance-identifier "$TARGET_INSTANCE" \
  --skip-final-snapshot \
  --region "$REGION" > /dev/null

echo "Cleanup initiated for ${TARGET_INSTANCE}."
echo "Check status with: aws rds describe-db-instances --db-instance-identifier ${TARGET_INSTANCE} --region ${REGION}"
