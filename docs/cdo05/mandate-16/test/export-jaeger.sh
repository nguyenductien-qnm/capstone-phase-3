#!/usr/bin/env bash

set -euo pipefail

JAEGER_URL="${JAEGER_URL:-http://127.0.0.1:16686/jaeger/ui}"
LOOKBACK="${LOOKBACK:-20m}"
OUTPUT_DIR="${1:-jaeger-export}"

mkdir -p "$OUTPUT_DIR"

for service in frontend cart checkout product-catalog recommendation; do
  curl --fail --silent --show-error \
    "$JAEGER_URL/api/traces?service=$service&lookback=$LOOKBACK&limit=100" \
    --output "$OUTPUT_DIR/$service.json"
done

echo "Jaeger traces exported to $OUTPUT_DIR"
