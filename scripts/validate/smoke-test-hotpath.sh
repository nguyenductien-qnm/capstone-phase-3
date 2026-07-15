#!/usr/bin/env bash
# CDO-143 — Smoke test hot-path sau deploy.
#
# Kiểm tra luồng ra tiền browse -> cart -> checkout qua frontend-proxy (Envoy edge)
# NGAY TRÊN CLUSTER, không phụ thuộc NLB public đã provisioned hay CloudFront/DNS.
# Dùng kubectl port-forward vào Service frontend-proxy nên chạy được cả khi service
# type=LoadBalancer chưa có địa chỉ NLB (mới deploy).
#
# Exit != 0 nếu bất kỳ hot-path route nào không trả HTTP < 500 -> gate deploy đỏ.
#
# Env (đều có default khớp chart/gitops hiện tại):
#   APP_NAMESPACE   namespace app (default techx-tf1)
#   PROXY_SVC       tên Service frontend-proxy (default frontend-proxy)
#   PROXY_PORT      cổng service (default 8080)
#   ROLLOUT_TIMEOUT chờ rollout mỗi hot-path deployment (default 180s)
#   RETRIES         số lần thử mỗi route (default 10)
set -euo pipefail

APP_NAMESPACE="${APP_NAMESPACE:-techx-tf1}"
PROXY_SVC="${PROXY_SVC:-frontend-proxy}"
PROXY_PORT="${PROXY_PORT:-8080}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-180s}"
RETRIES="${RETRIES:-10}"

# Hot-path core services phải Available trước khi test route (khớp CDO-42 hot-path).
HOTPATH_DEPLOYMENTS=(frontend-proxy frontend cart checkout product-catalog)

# Route hot-path browse -> cart -> checkout (khớp otel http.route trong values.yaml:1397+).
# Mỗi entry: "METHOD PATH". GET-only để smoke không tạo side-effect ghi dữ liệu.
HOTPATH_ROUTES=(
  "GET /"
  "GET /api/products"
  "GET /api/cart"
)

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }

command -v kubectl >/dev/null || fail "kubectl không có trong PATH"

log "Namespace app: $APP_NAMESPACE | Service: $PROXY_SVC:$PROXY_PORT"
kubectl get ns "$APP_NAMESPACE" >/dev/null 2>&1 || fail "namespace $APP_NAMESPACE chưa tồn tại"

# 1) Chờ các hot-path deployment sẵn sàng (deploy có thể vừa được ArgoCD sync).
log "Chờ rollout hot-path deployments (timeout $ROLLOUT_TIMEOUT mỗi cái)"
for d in "${HOTPATH_DEPLOYMENTS[@]}"; do
  if kubectl get deployment "$d" -n "$APP_NAMESPACE" >/dev/null 2>&1; then
    kubectl rollout status deployment "$d" -n "$APP_NAMESPACE" --timeout="$ROLLOUT_TIMEOUT" \
      || fail "deployment $d không Ready trong $ROLLOUT_TIMEOUT"
    ok "$d Ready"
  else
    printf '\033[1;33m! bỏ qua %s (không có deployment cùng tên)\033[0m\n' "$d"
  fi
done

kubectl get service "$PROXY_SVC" -n "$APP_NAMESPACE" >/dev/null 2>&1 \
  || fail "Service $PROXY_SVC không tồn tại trong $APP_NAMESPACE"

# 2) Port-forward tới frontend-proxy (chạy nền, luôn cleanup khi thoát).
LOCAL_PORT="${LOCAL_PORT:-18080}"
log "Port-forward svc/$PROXY_SVC $LOCAL_PORT:$PROXY_PORT"
kubectl port-forward "svc/$PROXY_SVC" "$LOCAL_PORT:$PROXY_PORT" -n "$APP_NAMESPACE" >/dev/null 2>&1 &
PF_PID=$!
cleanup() { kill "$PF_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Chờ port-forward mở.
for _ in $(seq 1 15); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${LOCAL_PORT}/" 2>/dev/null; then break; fi
  sleep 2
done

# 3) Test từng route hot-path. PASS = HTTP < 500 (4xx do thiếu session/params vẫn
#    tính là "edge sống"; chỉ 5xx / không kết nối mới coi là fail hot-path).
log "Smoke hot-path routes"
fail_count=0
for entry in "${HOTPATH_ROUTES[@]}"; do
  method="${entry%% *}"; path="${entry#* }"
  code=""
  for _ in $(seq 1 "$RETRIES"); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" \
      "http://127.0.0.1:${LOCAL_PORT}${path}" 2>/dev/null || echo 000)
    [ "$code" != "000" ] && [ "$code" -lt 500 ] && break
    sleep 3
  done
  if [ "$code" != "000" ] && [ "$code" -lt 500 ]; then
    ok "$method $path -> HTTP $code"
  else
    printf '\033[1;31m✗ %s %s -> HTTP %s\033[0m\n' "$method" "$path" "$code" >&2
    fail_count=$((fail_count + 1))
  fi
done

[ "$fail_count" -eq 0 ] || fail "$fail_count hot-path route lỗi -> gate deploy ĐỎ"
log "Tất cả hot-path route OK ✅"
