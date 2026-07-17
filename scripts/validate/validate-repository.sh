#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

terraform -chdir="$REPO_ROOT/terraform/environments/sandbox" fmt -check
terraform -chdir="$REPO_ROOT/terraform/environments/sandbox" init -backend=false -input=false
terraform -chdir="$REPO_ROOT/terraform/environments/sandbox" validate

helm lint "$REPO_ROOT/platform/charts/application" \
  -f "$REPO_ROOT/platform/gitops/environments/sandbox/values-observability.yaml" \
  -f "$REPO_ROOT/platform/gitops/environments/sandbox/values-flagd-sync.yaml"
