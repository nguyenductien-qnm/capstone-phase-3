#!/bin/bash
# ============================================================
# Locust Load Test — 300 users / spawn 75
# ============================================================
# Usage:
#   ./locust-300.sh setup   — Create K8s resources
#   ./locust-300.sh run     — Start load test
#   ./locust-300.sh status  — Check pod status
#   ./locust-300.sh metrics — Query Prometheus
#   ./locust-300.sh stop    — Stop (scale to 0)
#   ./locust-300.sh cleanup — Remove resources
# ============================================================

export LOCUST_USERS=300
export LOCUST_SPAWN_RATE=75
export LOCUST_DURATION="${LOCUST_DURATION:-15m}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/locust-test.sh" "$@"
