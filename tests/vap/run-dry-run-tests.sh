#!/usr/bin/env bash
# =============================================================================
# Mandate 05 - VAP test via server-side dry-run (read-only, nothing written to cluster)
# Usage: bash run-dry-run-tests.sh
# Requires: SSO logged in + kubectl pointing to ecommerce-develop-dev-eks
# =============================================================================
set -uo pipefail

NS="${NS:-default}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

CTX="$(kubectl.exe config current-context 2>/dev/null)"
echo "kubectl context : $CTX"
echo "namespace       : $NS"
echo "mode            : --dry-run=server (read-only, no pod created)"
echo

declare -A EXPECT=(
  ["neg-01-root.yaml"]="run-as-non-root"
  ["neg-02-image-latest.yaml"]="deny-floating-image-tag"
  ["neg-03-missing-resources.yaml"]="require-resources"
  ["neg-04-privesc-caps.yaml"]="deny-privilege-escalation psp-capabilities"
  ["neg-05-multi.yaml"]="run-as-non-root deny-floating-image-tag require-resources deny-privilege-escalation psp-capabilities"
  ["neg-06-initcontainer-latest.yaml"]="deny-floating-image-tag"
  ["neg-07-privesc-absent.yaml"]="deny-privilege-escalation"
  ["neg-08-no-caps-block.yaml"]="psp-capabilities"
  ["neg-09-partial-resources.yaml"]="require-resources"
  ["neg-10-podlevel-root.yaml"]="run-as-non-root"
  ["neg-11-uppercase-tag.yaml"]="deny-floating-image-tag"
  ["neg-12-deploy-root.yaml"]="run-as-non-root"
  ["neg-13-cronjob-latest.yaml"]="deny-floating-image-tag"
  ["pos-01-valid.yaml"]=""
  ["pos-02-podlevel-nonroot.yaml"]=""
  ["pos-03-otel-exempt.yaml"]=""
  ["pos-04-digest-netbind.yaml"]=""
  ["pos-05-deploy-valid.yaml"]=""
  ["pos-06-cronjob-valid.yaml"]=""
)

ORDER=(neg-01-root.yaml neg-02-image-latest.yaml neg-03-missing-resources.yaml \
       neg-04-privesc-caps.yaml neg-05-multi.yaml \
       neg-06-initcontainer-latest.yaml neg-07-privesc-absent.yaml \
       neg-08-no-caps-block.yaml neg-09-partial-resources.yaml \
       neg-10-podlevel-root.yaml neg-11-uppercase-tag.yaml \
       neg-12-deploy-root.yaml neg-13-cronjob-latest.yaml \
       pos-01-valid.yaml pos-02-podlevel-nonroot.yaml \
       pos-03-otel-exempt.yaml pos-04-digest-netbind.yaml \
       pos-05-deploy-valid.yaml pos-06-cronjob-valid.yaml)

PASS=0; FAIL=0

for f in "${ORDER[@]}"; do
  echo "============================================================"
  echo ">>> $f"
  echo "------------------------------------------------------------"

  OUT="$(kubectl.exe apply -f "$f" --dry-run=server -n "$NS" 2>&1)"
  echo "$OUT"
  echo

  hit=""
  for pol in ${EXPECT[$f]}; do
    grep -q "$pol" <<<"$OUT" && hit="$hit $pol"
  done

  unexpected=""
  for pol in run-as-non-root deny-floating-image-tag require-resources \
             deny-privilege-escalation psp-capabilities; do
    if ! grep -qw "$pol" <<<"${EXPECT[$f]}"; then
      grep -q "$pol" <<<"$OUT" && unexpected="$unexpected $pol"
    fi
  done

  if [[ -n "$unexpected" ]]; then
    echo "FAIL -- unexpected policy fired:$unexpected"
    ((FAIL++))
  elif [[ -n "${EXPECT[$f]}" && -z "$hit" ]]; then
    echo "FAIL -- violation not caught (expected: ${EXPECT[$f]})"
    ((FAIL++))
  else
    if [[ -n "${EXPECT[$f]}" ]]; then
      echo "PASS -- denied by:$hit (expected: ${EXPECT[$f]})"
    else
      echo "PASS -- valid manifest, no policy triggered"
    fi
    ((PASS++))
  fi
  echo
done

echo "============================================================"
echo "TOTAL:  PASS=$PASS  FAIL=$FAIL  / ${#ORDER[@]} cases"
echo "Enforcement = Deny: violations are REJECTED immediately on apply."
echo "Deny short-circuits at first failing rule (multi-violation shows 1 rule)."
echo "============================================================"
