#!/usr/bin/env bash
set -euo pipefail
REGION="" TRAIL="" START="" END="" EVENT="" USER="" RESOURCE="" RW=""
usage(){ echo "Usage: $0 --region R --trail-name T --start ISO8601 --end ISO8601 [--event-name E] [--username U] [--resource-name R] [--read-only true|false]"; }
while [[ $# -gt 0 ]]; do case "$1" in --region) REGION="$2";shift 2;; --trail-name) TRAIL="$2";shift 2;; --start) START="$2";shift 2;; --end) END="$2";shift 2;; --event-name) EVENT="$2";shift 2;; --username) USER="$2";shift 2;; --resource-name) RESOURCE="$2";shift 2;; --read-only) RW="$2";shift 2;; -h|--help) usage;exit 0;; *) echo "Unknown: $1";exit 2;; esac; done
[[ -n "$REGION" && -n "$TRAIL" && -n "$START" && -n "$END" ]] || { usage; exit 2; }
aws cloudtrail get-trail-status --region "$REGION" --name "$TRAIL"
aws cloudtrail get-event-selectors --region "$REGION" --trail-name "$TRAIL"
args=(--region "$REGION" --start-time "$START" --end-time "$END" --max-results 50)
[[ -z "$EVENT" ]] || args+=(--lookup-attributes AttributeKey=EventName,AttributeValue="$EVENT")
events=$(aws cloudtrail lookup-events "${args[@]}" --output json)
jq --arg user "$USER" --arg resource "$RESOURCE" --arg rw "$RW" '
 [.Events[] | (.CloudTrailEvent|fromjson) as $e
 | select($user=="" or .Username==$user or ($e.userIdentity.arn//"")|contains($user))
 | select($resource=="" or ([.Resources[].ResourceName//""]|join(" ")|contains($resource)))
 | select($rw=="" or (($e.readOnly//false)|tostring)==$rw)
 | {EventTime,EventName,EventSource,Username,principalArn:$e.userIdentity.arn,sessionIssuer:$e.userIdentity.sessionContext.sessionIssuer.arn,sourceIPAddress:$e.sourceIPAddress,userAgent:$e.userAgent,requestParameters:"REDACTED: inspect authorized raw event only when necessary",Resources}]' <<<"$events"
cat <<EOF
Integrity validation (run only for a small reviewed interval):
aws cloudtrail validate-logs --trail-arn "$(aws cloudtrail get-trail --region "$REGION" --name "$TRAIL" --query Trail.TrailARN --output text)" --start-time "$START" --end-time "$END"
EOF
