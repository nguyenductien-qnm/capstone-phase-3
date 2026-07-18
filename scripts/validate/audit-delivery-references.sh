#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
failures=0
fail() { printf 'FAIL: %s\n' "$*" >&2; failures=$((failures + 1)); }

while IFS= read -r action; do
  ref="${action##*@}"
  [[ "$ref" =~ ^[0-9a-fA-F]{40}$ ]] || fail "unpinned GitHub action: $action"
done < <(rg -n --no-heading '^[[:space:]-]*uses:[[:space:]]*[^@]+@[^[:space:]#]+' "$ROOT/.github/workflows" | sed -E 's/.*uses:[[:space:]]*([^[:space:]#]+).*/\1/')

while IFS= read -r line; do
  image="${line#FROM }"
  image="${image#--platform=* }"
  image="${image%% AS *}"
  [[ "$image" == *'@sha256:'* || "$image" == '$'* || "$image" == base || "$image" == builder ]] || fail "unpinned Docker base image: $line"
done < <(rg -h '^FROM ' "$ROOT/techx-corp-platform/src" -g 'Dockerfile*' || true)

if (( failures > 0 )); then
  printf '%d delivery reference violation(s) found. Pin actions to full commit SHAs and Docker FROM images to digests.\n' "$failures" >&2
  exit 1
fi
echo "delivery reference audit passed"
