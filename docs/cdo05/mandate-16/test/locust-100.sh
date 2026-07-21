#!/bin/bash
# ============================================================
# Locust Load Test — 100 users / spawn 25
# ============================================================
# Usage:
#   ./locust-100.sh setup   — Create K8s resources
#   ./locust-100.sh run     — Start load test
#   ./locust-100.sh status  — Check pod status
#   ./locust-100.sh metrics — Query Prometheus
#   ./locust-100.sh stop    — Stop (scale to 0)
#   ./locust-100.sh cleanup — Remove resources
# ============================================================

export LOCUST_USERS=100
export LOCUST_SPAWN_RATE=25
export LOCUST_DURATION="${LOCUST_DURATION:-15m}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/locust-test.sh" "$@"
