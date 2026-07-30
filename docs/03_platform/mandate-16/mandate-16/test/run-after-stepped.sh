#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../../../" && pwd)"
WORKSPACE_ROOT="$(cd -- "$REPO_ROOT/.." && pwd)"
LOCUST_DIR="$REPO_ROOT/techx-corp-platform/src/load-generator"
SHAPE_FILE="$SCRIPT_DIR/mandate16_after_shape.py"
EVIDENCE_ROOT="$WORKSPACE_ROOT/.tmp/evidence-m16/after/runs"
NAMESPACE="${K8S_NAMESPACE:-techx-develop}"
ARGO_NAMESPACE="${ARGO_NAMESPACE:-argocd}"
ARGO_APP="${ARGO_APP:-develop-techx-corp}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-19091}"
JAEGER_PORT="${JAEGER_PORT:-16687}"
OTLP_PORT="${OTLP_PORT:-14317}"
FLAGD_PORT="${FLAGD_PORT:-18016}"
SAMPLE_INTERVAL_SECONDS="${SAMPLE_INTERVAL_SECONDS:-15}"
IDLE_WINDOW="${IDLE_WINDOW:-5m}"
IDLE_MAX_REQUESTS="${IDLE_MAX_REQUESTS:-10}"
IDLE_TIMEOUT_SECONDS="${IDLE_TIMEOUT_SECONDS:-600}"

declare -a BACKGROUND_PIDS=()

die() {
  echo "Error: $*" >&2
  exit 1
}

retry_command() {
  local attempt
  for attempt in 1 2 3 4 5; do
    if "$@"; then
      return 0
    fi
    echo "Retry $attempt/5: $*" >&2
    sleep 2
  done
  return 1
}

cleanup() {
  local process_id
  for process_id in "${BACKGROUND_PIDS[@]:-}"; do
    kill "$process_id" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for required_command in kubectl curl jq uv git sha256sum; do
  command -v "$required_command" >/dev/null 2>&1 || die "$required_command is required"
done

[[ -f "$SHAPE_FILE" ]] || die "shape file not found: $SHAPE_FILE"
[[ -f "$LOCUST_DIR/locustfile.py" ]] || die "locustfile.py not found"
[[ -f "$LOCUST_DIR/requirements.txt" ]] || die "requirements.txt not found"

current_branch="$(git -C "$REPO_ROOT" branch --show-current)"
[[ "$current_branch" == "feat/mandate16" ]] || die "expected feat/mandate16, got $current_branch"

automated_sync="$(retry_command kubectl -n "$ARGO_NAMESPACE" get application "$ARGO_APP" -o jsonpath='{.spec.syncPolicy.automated}')"
[[ -z "$automated_sync" ]] || \
  die "ArgoCD automated sync must be disabled during the drifted after run, got: $automated_sync"

declare -A EXPECTED_IMAGES=(
  [cart]="1.0-cart-e80b0dc"
  [checkout]="1.0-checkout-e80b0dc"
  [frontend]="1.0-frontend-e80b0dc"
  [frontend-proxy]="1.0-frontend-proxy-e80b0dc"
  [product-catalog]="1.0-product-catalog-e80b0dc"
)

for deployment_name in cart checkout frontend frontend-proxy product-catalog; do
  deployed_image="$(retry_command kubectl -n "$NAMESPACE" get deployment "$deployment_name" -o jsonpath='{.spec.template.spec.containers[0].image}')"
  [[ "$deployed_image" == *":${EXPECTED_IMAGES[$deployment_name]}" ]] || \
    die "$deployment_name has unexpected image: $deployed_image"
done

echo "Waiting for critical deployments to become fully ready..."
readiness_deadline_epoch="$(( $(date +%s) + 600 ))"
while true; do
  all_deployments_ready=true
  for deployment_name in cart checkout frontend frontend-proxy product-catalog; do
    desired_replicas="$(retry_command kubectl -n "$NAMESPACE" get deployment "$deployment_name" -o jsonpath='{.spec.replicas}')"
    ready_replicas="$(retry_command kubectl -n "$NAMESPACE" get deployment "$deployment_name" -o jsonpath='{.status.readyReplicas}')"
    if [[ "$ready_replicas" != "$desired_replicas" ]]; then
      all_deployments_ready=false
      echo "  $deployment_name ready=${ready_replicas:-0}/$desired_replicas"
    fi
  done
  [[ "$all_deployments_ready" == "true" ]] && break
  (( $(date +%s) < readiness_deadline_epoch )) || die "critical deployments did not become ready"
  sleep 10
done

locust_replicas="$(retry_command kubectl -n "$NAMESPACE" get deployment locust-loadtest -o jsonpath='{.spec.replicas}')"
[[ "$locust_replicas" == "0" ]] || die "in-cluster locust-loadtest must be scaled to zero"

target_url="${TARGET_URL:-}"
if [[ -z "$target_url" ]]; then
  load_balancer_host="$(retry_command kubectl -n "$NAMESPACE" get service frontend-proxy-public -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
  [[ -n "$load_balancer_host" ]] || die "frontend-proxy-public has no load balancer hostname"
  target_url="http://$load_balancer_host"
fi

run_id="after-stepped-$(date -u +'%Y%m%dT%H%M%SZ')"
run_dir="$EVIDENCE_ROOT/$run_id"
mkdir -p "$run_dir"
echo "$run_dir" > "$EVIDENCE_ROOT/latest-run.txt"

start_port_forward() {
  local service_name="$1"
  local port_mapping="$2"
  local log_name="$3"
  kubectl -n "$NAMESPACE" port-forward "service/$service_name" "$port_mapping" \
    >"$run_dir/$log_name" 2>&1 &
  BACKGROUND_PIDS+=("$!")
}

start_port_forward prometheus "$PROMETHEUS_PORT:9090" prometheus-port-forward.log
start_port_forward jaeger "$JAEGER_PORT:16686" jaeger-port-forward.log
start_port_forward otel-collector "$OTLP_PORT:4317" otel-port-forward.log
start_port_forward flagd "$FLAGD_PORT:8016" flagd-port-forward.log

for _ in $(seq 1 30); do
  if curl --silent --fail --max-time 2 "http://127.0.0.1:$PROMETHEUS_PORT/-/ready" >/dev/null \
    && curl --silent --fail --max-time 2 "http://127.0.0.1:$JAEGER_PORT/jaeger/ui/api/services" >/dev/null; then
    break
  fi
  sleep 1
done

curl --silent --show-error --fail --max-time 10 "$target_url/" >/dev/null || \
  die "cannot reach target: $target_url"

prometheus_query() {
  curl --silent --show-error --fail --get "http://127.0.0.1:$PROMETHEUS_PORT/api/v1/query" \
    --data-urlencode "query=$1"
}

echo "Waiting for frontend-proxy background traffic <= $IDLE_MAX_REQUESTS requests/$IDLE_WINDOW..."
idle_deadline_epoch="$(( $(date +%s) + IDLE_TIMEOUT_SECONDS ))"
while true; do
  request_count="$(prometheus_query "sum(increase(traces_span_metrics_calls_total{service_name=\"frontend-proxy\",span_kind=\"SPAN_KIND_SERVER\"}[$IDLE_WINDOW]))" \
    | jq -r '.data.result[0].value[1] // "0"')"
  if awk -v observed="$request_count" -v maximum="$IDLE_MAX_REQUESTS" \
    'BEGIN { exit !(observed + 0 <= maximum + 0) }'; then
    break
  fi
  (( $(date +%s) < idle_deadline_epoch )) || die "idle window was not reached; observed $request_count requests"
  echo "  $(date -u +'%Y-%m-%dT%H:%M:%SZ') observed=$request_count; waiting..."
  sleep 15
done

kubectl -n "$NAMESPACE" get deployment cart checkout frontend frontend-proxy product-catalog product-reviews -o yaml > "$run_dir/k8s-deployments-before.yaml"
kubectl -n "$NAMESPACE" get hpa -o yaml > "$run_dir/k8s-hpa-before.yaml"
kubectl -n "$NAMESPACE" get pods -o wide > "$run_dir/k8s-pods-before.txt"
kubectl get nodes -o wide > "$run_dir/k8s-nodes-before.txt"
kubectl -n "$ARGO_NAMESPACE" get application "$ARGO_APP" -o yaml > "$run_dir/argocd-before.yaml"
git -C "$REPO_ROOT" rev-parse HEAD > "$run_dir/git-workspace-sha.txt"
git -C "$REPO_ROOT" rev-parse develop > "$run_dir/git-develop-sha.txt"
git -C "$REPO_ROOT" branch --show-current > "$run_dir/git-branch.txt"
sha256sum "$LOCUST_DIR/locustfile.py" "$SHAPE_FILE" > "$run_dir/workload-sha256.txt"

sample_cluster() {
  while true; do
    sample_timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    {
      echo "timestamp=$sample_timestamp"
      kubectl -n "$NAMESPACE" get hpa -o custom-columns='NAME:.metadata.name,CURRENT:.status.currentReplicas,DESIRED:.status.desiredReplicas,CPU:.status.currentMetrics[0].resource.current.averageUtilization' 2>&1
      kubectl -n "$NAMESPACE" get pods -o custom-columns='NAME:.metadata.name,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount,PHASE:.status.phase,NODE:.spec.nodeName' 2>&1
      kubectl top nodes 2>&1
      kubectl -n "$NAMESPACE" top pods 2>&1
      echo
    } >> "$run_dir/k8s-samples.log"

    prometheus_query 'sum(rate(traces_span_metrics_calls_total{span_kind="SPAN_KIND_SERVER"}[1m])) by (service_name)' \
      | jq -c --arg timestamp "$sample_timestamp" '{timestamp: $timestamp, metric: "request_rate", result: .data.result}' \
      >> "$run_dir/prometheus-samples.ndjson" || true
    prometheus_query 'sum(rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR",span_kind="SPAN_KIND_SERVER"}[1m])) by (service_name)' \
      | jq -c --arg timestamp "$sample_timestamp" '{timestamp: $timestamp, metric: "error_rate", result: .data.result}' \
      >> "$run_dir/prometheus-samples.ndjson" || true
    sleep "$SAMPLE_INTERVAL_SECONDS"
  done
}

sample_cluster &
sampler_pid="$!"
BACKGROUND_PIDS+=("$sampler_pid")

start_epoch="$(date +%s)"
start_utc="$(date -u -d "@$start_epoch" +'%Y-%m-%dT%H:%M:%SZ')"
echo "$start_utc" > "$run_dir/start-utc.txt"
{
  echo -e "stage\tusers\tstart_utc\tsteady_start_utc\tend_utc"
  echo -e "100\t100\t$(date -u -d "@$start_epoch" +'%Y-%m-%dT%H:%M:%SZ')\t$(date -u -d "@$((start_epoch + 60))" +'%Y-%m-%dT%H:%M:%SZ')\t$(date -u -d "@$((start_epoch + 300))" +'%Y-%m-%dT%H:%M:%SZ')"
  echo -e "200\t200\t$(date -u -d "@$((start_epoch + 300))" +'%Y-%m-%dT%H:%M:%SZ')\t$(date -u -d "@$((start_epoch + 360))" +'%Y-%m-%dT%H:%M:%SZ')\t$(date -u -d "@$((start_epoch + 600))" +'%Y-%m-%dT%H:%M:%SZ')"
  echo -e "300\t300\t$(date -u -d "@$((start_epoch + 600))" +'%Y-%m-%dT%H:%M:%SZ')\t$(date -u -d "@$((start_epoch + 660))" +'%Y-%m-%dT%H:%M:%SZ')\t$(date -u -d "@$((start_epoch + 1500))" +'%Y-%m-%dT%H:%M:%SZ')"
} > "$run_dir/stage-windows.tsv"

echo "Starting Mandate 16 after benchmark at $start_utc"
echo "Evidence: $run_dir"
cd "$LOCUST_DIR"
OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:$OTLP_PORT" \
FLAGD_HOST=127.0.0.1 \
FLAGD_OFREP_PORT="$FLAGD_PORT" \
uv run --with-requirements requirements.txt python -m locust \
  -f "$SHAPE_FILE" \
  --host "$target_url" \
  --headless \
  --only-summary \
  --html "$run_dir/locust-report.html" \
  --csv "$run_dir/locust" \
  --csv-full-history \
  2>&1 | tee "$run_dir/locust.log"

end_epoch="$(date +%s)"
end_utc="$(date -u -d "@$end_epoch" +'%Y-%m-%dT%H:%M:%SZ')"
echo "$end_utc" > "$run_dir/end-utc.txt"
kill "$sampler_pid" 2>/dev/null || true

kubectl -n "$NAMESPACE" get deployment cart checkout frontend frontend-proxy product-catalog product-reviews -o yaml > "$run_dir/k8s-deployments-after.yaml"
kubectl -n "$NAMESPACE" get hpa -o yaml > "$run_dir/k8s-hpa-after.yaml"
kubectl -n "$NAMESPACE" get pods -o wide > "$run_dir/k8s-pods-after.txt"
kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp > "$run_dir/k8s-events.txt"
kubectl top nodes > "$run_dir/k8s-nodes-after.txt" 2>&1 || true

start_microseconds="$((start_epoch * 1000000))"
end_microseconds="$((end_epoch * 1000000))"
for service_name in frontend-proxy frontend cart checkout product-catalog; do
  curl --silent --show-error --get "http://127.0.0.1:$JAEGER_PORT/jaeger/ui/api/traces" \
    --data-urlencode "service=$service_name" \
    --data-urlencode "start=$start_microseconds" \
    --data-urlencode "end=$end_microseconds" \
    --data-urlencode "limit=200" \
    > "$run_dir/jaeger-$service_name-traces.json" || true
done

echo "Benchmark completed at $end_utc"
echo "Evidence saved to $run_dir"
