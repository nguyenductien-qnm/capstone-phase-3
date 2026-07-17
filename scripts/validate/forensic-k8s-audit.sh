#!/usr/bin/env bash
set -euo pipefail
REGION="" CLUSTER="" START="" END="" USERNAME="" VERB="" NAMESPACE="" KIND="" NAME="" SOURCE_IP="" USER_AGENT="" STATUS="" DEMO=false
demo="" ns=""
cleanup_demo(){
  [[ -z "$ns" ]] || kubectl delete namespace "$ns" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup_demo EXIT
usage(){ echo "Usage: $0 --region R --cluster-name C --start ISO8601 --end ISO8601 [--username U] [--verb V] [--namespace N] [--resource-kind K] [--resource-name N] [--source-ip IP] [--user-agent UA] [--response-status CODE] [--generate-demo-event]"; }
while [[ $# -gt 0 ]]; do case "$1" in
 --region) REGION="$2";shift 2;; --cluster-name) CLUSTER="$2";shift 2;; --start) START="$2";shift 2;; --end) END="$2";shift 2;;
 --username) USERNAME="$2";shift 2;; --verb) VERB="$2";shift 2;; --namespace) NAMESPACE="$2";shift 2;; --resource-kind) KIND="$2";shift 2;; --resource-name) NAME="$2";shift 2;;
 --source-ip) SOURCE_IP="$2";shift 2;; --user-agent) USER_AGENT="$2";shift 2;; --response-status) STATUS="$2";shift 2;; --generate-demo-event) DEMO=true;shift;; -h|--help) usage;exit 0;; *) echo "Unknown: $1";exit 2;; esac; done
[[ -n "$REGION" && -n "$CLUSTER" ]] || { usage; exit 2; }
if $DEMO; then
  command -v kubectl >/dev/null || { echo "kubectl required for demo"; exit 2; }
  stamp="$(date -u +%Y%m%d%H%M%S)"; demo="audit-demo-$stamp"; ns="audit-forensic-$stamp"
  kubectl create namespace "$ns"
  kubectl -n "$ns" create configmap "$demo" --from-literal=purpose=forensic-drill
  kubectl -n "$ns" annotate configmap "$demo" audit.techx.io/drill="$(date -u +%FT%TZ)"
  kubectl -n "$ns" delete configmap "$demo"
  kubectl delete namespace "$ns" --wait=false
  echo "Demo create/patch/delete emitted for $ns/$demo; waiting 90s for ingestion..."; sleep 90
  NAMESPACE="$ns"; NAME="$demo"; START="${START:-$(date -u -d '15 minutes ago' +%FT%TZ)}"; END="${END:-$(date -u +%FT%TZ)}"
fi
[[ -n "$START" && -n "$END" ]] || { echo "--start and --end are required outside demo mode"; exit 2; }
q='fields @timestamp, user.username, user.groups, verb, requestURI, objectRef, sourceIPs, userAgent, responseStatus.code, auditID | filter @logStream like /kube-apiserver-audit-/ '
add(){ [[ -z "$2" ]] || q+="| filter $1 = '$(sed "s/'/\\\\'/g" <<<"$2")' "; }
add 'user.username' "$USERNAME"; add verb "$VERB"; add 'objectRef.namespace' "$NAMESPACE"; add 'objectRef.resource' "$KIND"; add 'objectRef.name' "$NAME"; add 'sourceIPs[0]' "$SOURCE_IP"; add 'responseStatus.code' "$STATUS"
[[ -z "$USER_AGENT" ]] || q+="| filter userAgent like /$(sed 's#[/\\]#\\&#g' <<<"$USER_AGENT")/ "
q+='| sort @timestamp desc | limit 200'
qid=$(aws logs start-query --region "$REGION" --log-group-name "/aws/eks/$CLUSTER/cluster" --start-time "$(date -d "$START" +%s)" --end-time "$(date -d "$END" +%s)" --query-string "$q" --query queryId --output text)
for _ in {1..30}; do result=$(aws logs get-query-results --region "$REGION" --query-id "$qid" --output json); state=$(jq -r .status <<<"$result"); [[ "$state" =~ ^(Complete|Failed|Cancelled|Timeout)$ ]] && break; sleep 2; done
jq . <<<"$result"; [[ "$state" == Complete ]]
