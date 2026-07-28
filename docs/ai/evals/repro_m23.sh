#!/bin/bash
# Repro MANDATE-23 — cache + memory. Chạy: bash docs/ai/evals/repro_m23.sh
set -uo pipefail
cd "$(dirname "$0")"

COMPOSE="../../../techx-corp-platform/docker-compose.yml"
export EVAL_BASE_URL="${EVAL_BASE_URL:-http://localhost:8080/api}"
JAEGER_PORT=$(docker compose -f "$COMPOSE" port jaeger 16686 2>/dev/null | cut -d: -f2)
export JAEGER_BASE_URL="${JAEGER_BASE_URL:-http://localhost:${JAEGER_PORT:-32772}}"

echo "=== 1. Pre-flight (không đạt thì KHÔNG đo) ==="
BAD=$(docker compose -f "$COMPOSE" ps -a --format '{{.Service}}\t{{.State}}' | grep -v running || true)
if [ -n "$BAD" ]; then echo "❌ service chưa chạy:"; echo "$BAD"; exit 1; fi
echo "  service up: $(docker compose -f "$COMPOSE" ps --format '{{.Service}}' | wc -l)"

docker exec valkey-cart valkey-cli PING | grep -q PONG || { echo "❌ Valkey không PING"; exit 1; }
echo "  valkey: $(docker exec valkey-cart valkey-server --version | awk '{print $2}') (prod ElastiCache 8.2)"
docker exec valkey-cart valkey-cli FT.INFO copilot-semantic-idx >/dev/null \
  || { echo "❌ thiếu Valkey Search index copilot-semantic-idx"; exit 1; }

docker exec postgresql psql -U root -d otel -tc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='ai'" | grep -q 2 \
  || { echo "❌ thiếu bảng ai.semantic_cache / ai.user_memory"; exit 1; }

curl -sf -o /dev/null "$EVAL_BASE_URL/products" || { echo "❌ frontend không trả 200"; exit 1; }
echo "  ✅ pre-flight OK"

echo
echo "=== 2. Dọn cache về trạng thái xác định (KHÔNG FLUSHALL — sẽ giết giỏ hàng) ==="
python3 -c 'from eval_mandate23 import clear_cache; clear_cache()'
echo "  đã xoá prefix copilot:answer:*, copilot:semantic:* và reviews:summary:*"

echo
echo "=== 3. Harness MANDATE-23 (hard bar bật) ==="
STATUS=0
python3 eval_mandate23.py --enforce-hard-bars || STATUS=$?

echo
echo "=== 4. Bảng tổng kết ==="
sed -n '/| Nhóm | Ca |/,$p' eval_mandate23_report.md

echo
if [ "$STATUS" -ne 0 ]; then
  echo "❌ Hard bar KHÔNG đạt (rò cross-user hoặc trả cũ sai) — xem report ở trên."
  exit 1
fi
echo "✅ Hard bar đạt. Evidence per-case: docs/ai/evals/evidence_m23/<timestamp>/"
