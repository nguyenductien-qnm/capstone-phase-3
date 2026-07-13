#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENVOY="$REPO_ROOT/techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml"
TAILSCALE="$REPO_ROOT/platform/gitops/tailscale"

fail() {
  echo "MANDATE-01 check failed: $1" >&2
  exit 1
}

for route in loadgen jaeger grafana; do
  ! rg -q "match:.*\"/$route" "$ENVOY" || fail "public /$route route remains"
done
rg -q 'match:.*"/otlp-http/' "$ENVOY" || fail "/otlp-http/ route missing"
QUICK_TUNNEL="$REPO_ROOT/platform/cloudflare-tunnel.yaml"
test -e "$QUICK_TUNNEL" || fail "quick tunnel manifest missing"
rg -q 'http://frontend-proxy:8080' "$QUICK_TUNNEL" || fail "quick tunnel target changed"

check_ingress() {
  local file="$1" namespace="$2" tag="$3" host="$4" service="$5" port="$6"
  rg -q "namespace: $namespace" "$file" || fail "$file namespace"
  rg -q "tailscale.com/tags: \"$tag\"" "$file" || fail "$file tag"
  rg -q -- "- $host" "$file" || fail "$file host"
  rg -q "^[[:space:]]+name: $service$" "$file" || fail "$file backend service"
  rg -q "^[[:space:]]+number: $port$" "$file" || fail "$file backend port"
}

check_ingress "$TAILSCALE/grafana-ingress.yaml" techx-tf1 tag:ops-grafana grafana-tf1 grafana 80
check_ingress "$TAILSCALE/jaeger-ingress.yaml" techx-tf1 tag:ops-jaeger jaeger-tf1 jaeger 16686
check_ingress "$TAILSCALE/argocd-ingress.yaml" argocd tag:ops-argocd argocd-tf1 argocd-server 80
check_ingress "$TAILSCALE/locust-ingress.yaml" techx-tf1 tag:ops-locust locust-tf1 load-generator 8089

rg -q 'server.insecure: "true"' "$TAILSCALE/argocd-server-params.yaml" || fail "ArgoCD HTTP backend not enabled"
rg -q 'path: platform/gitops/tailscale' "$REPO_ROOT/platform/gitops/applications/tailscale-ingress.yaml" || fail "ArgoCD child app path"

echo "MANDATE-01 static checks passed"
