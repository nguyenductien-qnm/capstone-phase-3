#!/usr/bin/env bash
set -euo pipefail

REGION="" CLUSTER="" TRAIL="" TF_DIR="terraform/environments/sandbox"
failures=0
pass(){ printf 'PASS: %s\n' "$*"; }
warn(){ printf 'WARN: %s\n' "$*"; }
fail(){ printf 'FAIL: %s\n' "$*"; failures=$((failures+1)); }
usage(){ echo "Usage: $0 --region REGION --cluster-name NAME --trail-name NAME [--terraform-dir DIR]"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;; --cluster-name) CLUSTER="$2"; shift 2;;
    --trail-name) TRAIL="$2"; shift 2;; --terraform-dir) TF_DIR="$2"; shift 2;;
    -h|--help) usage; exit 0;; *) echo "Unknown argument: $1"; usage; exit 2;;
  esac
done
[[ -n "$REGION" && -n "$CLUSTER" && -n "$TRAIL" ]] || { usage; exit 2; }
command -v aws >/dev/null || { echo "FAIL: aws CLI is required"; exit 2; }
command -v jq >/dev/null || { echo "FAIL: jq is required"; exit 2; }

aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json >/dev/null && pass "AWS caller identity is valid" || fail "AWS caller identity"
types=$(aws eks describe-cluster --region "$REGION" --name "$CLUSTER" --query 'cluster.logging.clusterLogging[0].types' --output text 2>/dev/null || true)
for t in api audit authenticator; do [[ " $types " == *" $t "* ]] && pass "EKS log type $t enabled" || fail "EKS log type $t missing"; done

eks_group="/aws/eks/$CLUSTER/cluster"
eks_retention=$(aws logs describe-log-groups --region "$REGION" --log-group-name-prefix "$eks_group" --query "logGroups[?logGroupName=='$eks_group'].retentionInDays|[0]" --output text 2>/dev/null || true)
[[ "$eks_retention" != "None" && -n "$eks_retention" ]] && pass "EKS log group exists; retention=${eks_retention}d" || fail "EKS log group or explicit retention missing"
stream=$(aws logs describe-log-streams --region "$REGION" --log-group-name "$eks_group" --log-stream-name-prefix kube-apiserver-audit- --max-items 1 --query 'logStreams[0].logStreamName' --output text 2>/dev/null || true)
[[ "$stream" != "None" && -n "$stream" ]] && pass "Kubernetes audit stream exists" || fail "No kube-apiserver-audit-* stream found"

status=$(aws cloudtrail get-trail-status --region "$REGION" --name "$TRAIL" --output json 2>/dev/null || true)
[[ $(jq -r '.IsLogging // false' <<<"$status" 2>/dev/null || echo false) == true ]] && pass "CloudTrail is logging" || fail "CloudTrail is not logging"
trail=$(aws cloudtrail get-trail --region "$REGION" --name "$TRAIL" --query Trail --output json 2>/dev/null || true)
[[ $(jq -r '.LogFileValidationEnabled // false' <<<"$trail" 2>/dev/null || echo false) == true ]] && pass "CloudTrail log-file validation enabled" || fail "CloudTrail validation disabled"
bucket=$(jq -r '.S3BucketName // empty' <<<"$trail" 2>/dev/null || true)
if [[ -n "$bucket" ]]; then
  [[ $(aws s3api get-bucket-versioning --bucket "$bucket" --query Status --output text 2>/dev/null || true) == Enabled ]] && pass "S3 versioning enabled" || fail "S3 versioning disabled"
  aws s3api get-public-access-block --bucket "$bucket" --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,IgnorePublicAcls,BlockPublicPolicy,RestrictPublicBuckets]' --output text 2>/dev/null | grep -qi '^True[[:space:]]True[[:space:]]True[[:space:]]True' && pass "S3 public access fully blocked" || fail "S3 public access block incomplete"
  aws s3api get-bucket-encryption --bucket "$bucket" --output json >/dev/null 2>&1 && pass "S3 default encryption configured" || fail "S3 encryption missing"
  lock=$(aws s3api get-object-lock-configuration --bucket "$bucket" --query 'ObjectLockConfiguration.ObjectLockEnabled' --output text 2>/dev/null || true)
  [[ "$lock" == Enabled ]] && pass "S3 Object Lock enabled" || warn "S3 Object Lock not enabled; rely on versioning, validation and explicit deny until migration"
else fail "CloudTrail S3 bucket not discoverable"; fi

cw=$(jq -r '.CloudWatchLogsLogGroupArn // empty' <<<"$trail" 2>/dev/null || true)
[[ -n "$cw" ]] && pass "CloudTrail CloudWatch integration configured" || warn "CloudTrail CloudWatch integration absent"
if command -v terraform >/dev/null && [[ -d "$TF_DIR" ]]; then
  terraform -chdir="$TF_DIR" output -json >/dev/null 2>&1 && pass "Terraform outputs readable" || warn "Terraform outputs unavailable (backend/state may not be initialized)"
else warn "Terraform CLI/directory unavailable; output check skipped"; fi
(( failures == 0 )) || exit 1
