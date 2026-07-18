#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 --namespace NS --pod POD [--output FILE] [--pod-json FILE]" >&2; exit 2; }
ns=""; pod=""; pod_json=""; output="-"
while (($#)); do
  case "$1" in
    --namespace) ns="$2"; shift 2;;
    --pod) pod="$2"; shift 2;;
    --pod-json) pod_json="$2"; shift 2;;
    --output) output="$2"; shift 2;;
    *) usage;;
  esac
done
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }
[[ -n "$pod_json" || ( -n "$ns" && -n "$pod" ) ]] || usage

if [[ -z "$pod_json" ]]; then
  command -v kubectl >/dev/null || { echo "kubectl is required in live mode" >&2; exit 2; }
  pod_json="$(mktemp)"
  trap 'rm -f "$pod_json"' EXIT
  kubectl -n "$ns" get pod "$pod" -o json > "$pod_json"
fi

image_id="$(jq -r '.status.containerStatuses[0].imageID // empty' "$pod_json")"
image_ref="$(jq -r '.spec.containers[0].image // empty' "$pod_json")"
namespace="$(jq -r '.metadata.namespace // empty' "$pod_json")"
pod_name="$(jq -r '.metadata.name // empty' "$pod_json")"
digest="${image_id##*@}"
[[ "$digest" =~ ^sha256:[a-f0-9]{64}$ ]] || { echo "missing or invalid runtime image digest" >&2; exit 1; }
[[ "$image_ref" == *"@$digest" ]] || { echo "image reference does not match runtime image digest" >&2; exit 1; }

labels="$(jq -c '.metadata.labels // {}' "$pod_json")"
annotations="$(jq -c '.metadata.annotations // {}' "$pod_json")"
source_repo="$(jq -r '."org.opencontainers.image.source" // empty' <<<"$labels")"
source_repo="${source_repo:-$(jq -r '."delivery.techx.io/source-repository" // empty' <<<"$annotations")}"
commit="$(jq -r '."org.opencontainers.image.revision" // empty' <<<"$labels")"
commit="${commit:-$(jq -r '."delivery.techx.io/commit" // empty' <<<"$annotations")}"
pr="$(jq -r '."delivery.techx.io/pr-number" // empty' <<<"$annotations")"
workflow="$(jq -r '."delivery.techx.io/workflow" // empty' <<<"$annotations")"
run_id="$(jq -r '."delivery.techx.io/run-id" // empty' <<<"$annotations")"
signer="$(jq -r '."delivery.sigstore.dev/identity" // empty' <<<"$annotations")"
issuer="$(jq -r '."delivery.sigstore.dev/issuer" // empty' <<<"$annotations")"
sbom="$(jq -r '."delivery.supply-chain/sbom" // empty' <<<"$annotations")"
provenance="$(jq -r '."delivery.supply-chain/provenance" // empty' <<<"$annotations")"

for pair in "namespace=$namespace" "pod=$pod_name" "image=$image_ref" "source repository=$source_repo" "commit=$commit" "PR number=$pr" "workflow=$workflow" "run ID=$run_id" "signer identity=$signer" "issuer=$issuer" "SBOM=$sbom" "provenance=$provenance"; do
  [[ -n "${pair#*=}" && "${pair#*=}" != null ]] || { echo "missing evidence: ${pair%%=*}" >&2; exit 1; }
done

render() {
  cat <<EOF
# Delivery forensic report

- Pod: $namespace/$pod_name
- Image reference: $image_ref
- Runtime image digest: $digest
- Source repository: $source_repo
- Commit SHA: $commit
- PR number: $pr
- Workflow / run: $workflow / $run_id
- Signature identity: $signer
- Signature issuer: $issuer
- SBOM: $sbom
- Provenance: $provenance
EOF
}
if [[ "$output" == "-" ]]; then render; else render > "$output"; fi
