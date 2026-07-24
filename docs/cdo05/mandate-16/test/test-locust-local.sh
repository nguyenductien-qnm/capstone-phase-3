#!/usr/bin/env bash

set -euo pipefail

# Run the existing load-generator locally so the load-generator pod CPU limit
# does not become part of the benchmark. Start a port-forward separately when
# TARGET_URL is not publicly reachable:
#   kubectl -n techx-develop port-forward svc/frontend-proxy 18080:80
#   TARGET_URL=http://127.0.0.1:18080 ./test-locust-local.sh

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../../../" && pwd)"
LOCUST_DIR="$REPO_ROOT/techx-corp-platform/src/load-generator"

TARGET_URL="${TARGET_URL:-http://127.0.0.1:18080}"
USERS="${LOCUST_USERS:-${1:-500}}"
SPAWN_RATE="${LOCUST_SPAWN_RATE:-${2:-125}}"
DURATION="${LOCUST_DURATION:-${3:-3m}}"
LOCUST_HOST="${LOCUST_HOST:-$TARGET_URL}"

die() {
  echo "Error: $*" >&2
  exit 1
}

command -v locust >/dev/null 2>&1 || die "locust is not installed or is not on PATH"
[[ "$USERS" =~ ^[0-9]+$ ]] && (( USERS > 0 )) || die "users must be a positive integer"
[[ "$SPAWN_RATE" =~ ^[0-9]+$ ]] && (( SPAWN_RATE > 0 )) || die "spawn rate must be a positive integer"
[[ -f "$LOCUST_DIR/locustfile.py" ]] || die "locustfile.py not found at $LOCUST_DIR"
[[ -f "$LOCUST_DIR/people.json" ]] || die "people.json not found at $LOCUST_DIR"

if ! curl --silent --show-error --fail --max-time 5 "$TARGET_URL/" >/dev/null; then
  die "cannot reach TARGET_URL=$TARGET_URL (start port-forward or set TARGET_URL)"
fi

echo "Running local Locust benchmark"
echo "  Target:      $TARGET_URL"
echo "  Users:       $USERS"
echo "  Spawn rate:  $SPAWN_RATE"
echo "  Duration:    $DURATION"
echo ""

cd "$LOCUST_DIR"
exec locust \
  -f locustfile.py \
  --host "$LOCUST_HOST" \
  --headless \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$DURATION" \
  --only-summary \
  --html "$SCRIPT_DIR/locust-local-report.html" \
  --csv "$SCRIPT_DIR/locust-local" \
  --csv-full-history
