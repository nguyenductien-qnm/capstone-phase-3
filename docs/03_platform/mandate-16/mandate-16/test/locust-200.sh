#!/bin/bash
# ============================================================
# Locust Load Test — 200 users / spawn 50
# ============================================================
# Usage:
#   ./locust-200.sh setup   — Create K8s resources
#   ./locust-200.sh run     — Start load test
#   ./locust-200.sh status  — Check pod status
#   ./locust-200.sh metrics — Query Prometheus
#   ./locust-200.sh stop    — Stop (scale to 0)
#   ./locust-200.sh cleanup — Remove resources
# ============================================================

export LOCUST_USERS=200
export LOCUST_SPAWN_RATE=50
export LOCUST_DURATION="${LOCUST_DURATION:-15m}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/locust-test.sh" "$@"
