#!/bin/bash
# ============================================================
# Locust Load Test Manager
# ============================================================
# Usage:
#   ./locust-test.sh setup [users] [duration]  — Prepare resources
#   ./locust-test.sh run                        — Start load test
#   ./locust-test.sh status                     — Check status
#   ./locust-test.sh metrics                    — Query Prometheus
#   ./locust-test.sh stop                       — Stop load test (scale to 0)
#   ./locust-test.sh cleanup                    — Remove all resources
#   ./locust-test.sh help                       — Show this help
# ============================================================

set -euo pipefail

# --- Default Config ---
LOCUST_USERS="${LOCUST_USERS:-300}"
LOCUST_SPAWN_RATE="${LOCUST_SPAWN_RATE:-75}"
LOCUST_DURATION="${LOCUST_DURATION:-15m}"
NAMESPACE="techx-develop"
DEPLOYMENT_NAME="locust-loadtest"
CONFIGMAP_NAME="locust-full-flow"
IMAGE="804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-load-generator-5369fc8"
LOCUST_DIR="$(dirname "$0")/../../../../techx-corp-platform/src/load-generator"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Functions ---
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# --- Commands ---
cmd_setup() {
    print_header "SETTING UP LOAD TEST RESOURCES"
    
    local users=${1:-$LOCUST_USERS}
    local duration=${2:-$LOCUST_DURATION}
    
    echo "Config:"
    echo "  Users:      $users"
    echo "  Spawn rate: $((users / 4))"
    echo "  Duration:   $duration"
    echo "  Namespace:  $NAMESPACE"
    echo ""
    
    # Step 1: Create ConfigMap
    echo "Step 1: Creating ConfigMap..."
    if [ -f "$LOCUST_DIR/locustfile.py" ] && [ -f "$LOCUST_DIR/people.json" ]; then
        kubectl create configmap "$CONFIGMAP_NAME" \
            --from-file=locustfile.py="$LOCUST_DIR/locustfile.py" \
            --from-file=people.json="$LOCUST_DIR/people.json" \
            -n "$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f - 2>&1
        print_status "ConfigMap $CONFIGMAP_NAME created"
    else
        print_error "Locust files not found in $LOCUST_DIR"
        exit 1
    fi
    
    # Step 2: Create Deployment
    echo ""
    echo "Step 2: Creating Deployment..."
    cat <<EOF | kubectl apply -f - 2>&1
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $DEPLOYMENT_NAME
  namespace: $NAMESPACE
  labels:
    app: $DEPLOYMENT_NAME
    purpose: load-testing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: $DEPLOYMENT_NAME
  template:
    metadata:
      labels:
        app: $DEPLOYMENT_NAME
        purpose: load-testing
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: locust
        image: $IMAGE
        args:
        - "-f"
        - "/mnt/locust/locustfile.py"
        - "--host"
        - "http://frontend-proxy:80"
        - "--web-host"
        - "0.0.0.0"
        - "--web-port"
        - "8089"
        - "--class-picker"
        env:
        - name: LOCUST_USERS
          value: "$users"
        - name: LOCUST_SPAWN_RATE
          value: "$((users / 4))"
        - name: LOCUST_RUN_DURATION
          value: "$duration"
        - name: LOCUST_HEADLESS
          value: "true"
        - name: LOCUST_AUTOSTART
          value: "true"
        - name: LOCUST_BROWSER_TRAFFIC_ENABLED
          value: "false"
        - name: OTEL_COLLECTOR_NAME
          value: "otel-collector"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector:4317"
        - name: PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION
          value: "python"
        - name: FLAGD_HOST
          value: "flagd"
        - name: FLAGD_PORT
          value: "8013"
        - name: FLAGD_OFREP_PORT
          value: "8016"
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        volumeMounts:
        - name: locust-scripts
          mountPath: /mnt/locust
          readOnly: true
        ports:
        - containerPort: 8089
          name: web
      volumes:
      - name: locust-scripts
        configMap:
          name: $CONFIGMAP_NAME
EOF
    print_status "Deployment $DEPLOYMENT_NAME created"
    
    echo ""
    print_status "Setup complete! Run './locust-test.sh run' to start the test."
}

cmd_run() {
    print_header "STARTING LOAD TEST"
    
    # Check if deployment exists
    if ! kubectl get deploy "$DEPLOYMENT_NAME" -n "$NAMESPACE" &>/dev/null; then
        print_error "Deployment not found. Run './locust-test.sh setup' first."
        exit 1
    fi
    
    # Check if pod is running
    echo "Waiting for pod to start..."
    kubectl rollout status deploy/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=60s 2>&1 || true
    
    echo ""
    echo "Pod status:"
    kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME"
    
    echo ""
    print_status "Load test started!"
    echo ""
    echo "Monitor with:"
    echo "  ./locust-test.sh status    — Check pod status"
    echo "  ./locust-test.sh metrics   — Query Prometheus metrics"
    echo ""
    echo "The test will run for $LOCUST_DURATION then auto-stop."
}

cmd_status() {
    print_header "LOAD TEST STATUS"
    
    echo "=== Deployment ==="
    kubectl get deploy "$DEPLOYMENT_NAME" -n "$NAMESPACE" 2>&1 || print_warning "Deployment not found"
    
    echo ""
    echo "=== Pods ==="
    kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME" 2>&1 || print_warning "No pods found"
    
    echo ""
    echo "=== Resource Usage ==="
    kubectl top pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME" 2>&1 || print_warning "Metrics not available"
    
    echo ""
    echo "=== Config ==="
    kubectl get deploy "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].env}' 2>&1 | python3 -c "
import json, sys
try:
    envs = json.load(sys.stdin)
    for e in envs:
        if 'LOCUST' in e['name']:
            print(f\"  {e['name']}={e['value']}\")
except:
    print('  Config not available')
" 2>&1 || true
}

cmd_metrics() {
    print_header "PROMETHEUS METRICS"
    
    echo "=== E2E p95 Latency ==="
    kubectl exec -n "$NAMESPACE" deploy/prometheus -- wget -q -O- 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name="frontend-proxy",span_kind="SPAN_KIND_SERVER"}[5m]))by(le))' 2>&1 | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    if d['data']['result']:
        val = float(d['data']['result'][0]['value'][1])
        print(f'  {val:.2f} ms')
    else:
        print('  No data available')
except:
    print('  Query failed')
" 2>&1 || print_warning "Cannot query Prometheus"
    
    echo ""
    echo "=== E2E p99 Latency ==="
    kubectl exec -n "$NAMESPACE" deploy/prometheus -- wget -q -O- 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name="frontend-proxy",span_kind="SPAN_KIND_SERVER"}[5m]))by(le))' 2>&1 | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    if d['data']['result']:
        val = float(d['data']['result'][0]['value'][1])
        print(f'  {val:.2f} ms')
    else:
        print('  No data available')
except:
    print('  Query failed')
" 2>&1 || print_warning "Cannot query Prometheus"
    
    echo ""
    echo "=== Request Rate (frontend-proxy) ==="
    kubectl exec -n "$NAMESPACE" deploy/prometheus -- wget -q -O- 'http://localhost:9090/api/v1/query?query=sum(rate(traces_span_metrics_calls_total{service_name="frontend-proxy",span_kind="SPAN_KIND_SERVER"}[5m]))' 2>&1 | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    if d['data']['result']:
        val = float(d['data']['result'][0]['value'][1])
        print(f'  {val:.2f} req/s')
    else:
        print('  No data available')
except:
    print('  Query failed')
" 2>&1 || print_warning "Cannot query Prometheus"
    
    echo ""
    echo "=== Per-Service p95 Latency ==="
    kubectl exec -n "$NAMESPACE" deploy/prometheus -- wget -q -O- 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=~"frontend|product-catalog|cart|checkout|payment|shipping|currency",span_kind="SPAN_KIND_SERVER"}[5m]))by(le,service_name))' 2>&1 | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for r in sorted(d['data']['result'], key=lambda x: float(x['value'][1]), reverse=True):
        svc = r['metric']['service_name']
        val = float(r['value'][1])
        print(f'  {svc}: {val:.2f} ms')
except:
    print('  Query failed')
" 2>&1 || print_warning "Cannot query Prometheus"
}

cmd_cleanup() {
    print_header "CLEANING UP RESOURCES"
    
    echo "Deleting deployment..."
    kubectl delete deploy "$DEPLOYMENT_NAME" -n "$NAMESPACE" --ignore-not-found 2>&1
    print_status "Deployment deleted"
    
    echo ""
    echo "Keeping ConfigMap $CONFIGMAP_NAME for future tests."
    echo "To delete it too: kubectl delete configmap $CONFIGMAP_NAME -n $NAMESPACE"
    
    echo ""
    print_status "Cleanup complete!"
}

cmd_stop() {
    print_header "STOPPING LOAD TEST"
    
    if kubectl get deploy "$DEPLOYMENT_NAME" -n "$NAMESPACE" &>/dev/null; then
        kubectl scale deploy "$DEPLOYMENT_NAME" --replicas=0 -n "$NAMESPACE" 2>&1
        print_status "Scaled deployment to 0. Test stopped."
    else
        print_error "Deployment not found. Nothing to stop."
    fi
}

cmd_help() {
    print_header "LOCUST TEST MANAGER"
    
    echo "Usage:"
    echo "  ./locust-test.sh setup [users] [duration]  — Prepare resources"
    echo "  ./locust-test.sh run                        — Start load test"
    echo "  ./locust-test.sh status                     — Check status"
    echo "  ./locust-test.sh metrics                    — Query Prometheus"
    echo "  ./locust-test.sh stop                       — Stop load test (scale to 0)"
    echo "  ./locust-test.sh cleanup                    — Remove all resources"
    echo "  ./locust-test.sh help                       — Show this help"
    echo ""
    echo "Examples:"
    echo "  ./locust-test.sh setup                     — Setup with defaults (100 users, 15m)"
    echo "  ./locust-test.sh setup 150 10m             — Setup with 150 users, 10 minutes"
    echo "  ./locust-test.sh run                       — Start the test"
    echo "  ./locust-test.sh stop                      — Stop the test immediately"
    echo "  ./locust-test.sh metrics                   — Check current metrics"
    echo "  ./locust-test.sh cleanup                   — Clean up resources"
    echo ""
    echo "Environment Variables:"
    echo "  LOCUST_USERS       — Number of concurrent users (default: 100)"
    echo "  LOCUST_SPAWN_RATE  — Users spawned per second (default: users/4)"
    echo "  LOCUST_DURATION    — Test duration (default: 15m)"
}

check_prerequisites() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install it first."
        exit 1
    fi
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_error "Cannot connect to cluster or namespace '$NAMESPACE' not found!"
        exit 1
    fi
}

# --- Main ---
if [[ "${1:-help}" != "help" ]]; then
    check_prerequisites
fi
case "${1:-help}" in
    setup)
        cmd_setup "${2:-}" "${3:-}"
        ;;
    run)
        cmd_run
        ;;
    status)
        cmd_status
        ;;
    metrics)
        cmd_metrics
        ;;
    stop)
        cmd_stop
        ;;
    cleanup)
        cmd_cleanup
        ;;
    help|*)
        cmd_help
        ;;
esac
