#!/usr/bin/env bash
set -euo pipefail

REGION="" CLUSTER="" TRAIL="" TF_DIR="terraform/environments/sandbox" OPERATOR_PRINCIPAL=""
failures=0
pass(){ printf 'PASS: %s\n' "$*"; }
warn(){ printf 'WARN: %s\n' "$*"; }
fail(){ printf 'FAIL: %s\n' "$*"; failures=$((failures+1)); }
usage(){ echo "Usage: $0 --region REGION --cluster-name NAME --trail-name NAME [--terraform-dir DIR] [--operator-principal-arn ARN]"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;; --cluster-name) CLUSTER="$2"; shift 2;;
    --trail-name) TRAIL="$2"; shift 2;; --terraform-dir) TF_DIR="$2"; shift 2;;
    --operator-principal-arn) OPERATOR_PRINCIPAL="$2"; shift 2;;
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
[[ "$eks_retention" =~ ^[0-9]+$ && "$eks_retention" -ge 30 ]] && pass "EKS log group retention=${eks_retention}d" || fail "EKS log group retention must be at least 30d"
eks_kms=$(aws logs describe-log-groups --region "$REGION" --log-group-name-prefix "$eks_group" --query "logGroups[?logGroupName=='$eks_group'].kmsKeyId|[0]" --output text 2>/dev/null || true)
[[ "$eks_kms" != "None" && -n "$eks_kms" ]] && pass "EKS log group uses a customer-managed KMS key" || fail "EKS log group KMS key missing"
stream=$(aws logs describe-log-streams --region "$REGION" --log-group-name "$eks_group" --log-stream-name-prefix kube-apiserver-audit- --max-items 1 --query 'logStreams[0].logStreamName' --output text 2>/dev/null || true)
[[ "$stream" != "None" && -n "$stream" ]] && pass "Kubernetes audit stream exists" || fail "No kube-apiserver-audit-* stream found"

status=$(aws cloudtrail get-trail-status --region "$REGION" --name "$TRAIL" --output json 2>/dev/null || true)
[[ $(jq -r '.IsLogging // false' <<<"$status" 2>/dev/null || echo false) == true ]] && pass "CloudTrail is logging" || fail "CloudTrail is not logging"
trail=$(aws cloudtrail get-trail --region "$REGION" --name "$TRAIL" --query Trail --output json 2>/dev/null || true)
[[ $(jq -r '.LogFileValidationEnabled // false' <<<"$trail" 2>/dev/null || echo false) == true ]] && pass "CloudTrail log-file validation enabled" || fail "CloudTrail validation disabled"
[[ $(jq -r '(.IsMultiRegionTrail == true and .IncludeGlobalServiceEvents == true)' <<<"$trail" 2>/dev/null || echo false) == true ]] && pass "CloudTrail is multi-region and includes global services" || fail "CloudTrail multi-region/global coverage incomplete"
[[ -n $(jq -r '.KmsKeyId // empty' <<<"$trail" 2>/dev/null || true) ]] && pass "CloudTrail uses a customer-managed KMS key" || fail "CloudTrail KMS key missing"
selectors=$(aws cloudtrail get-event-selectors --region "$REGION" --trail-name "$TRAIL" --output json 2>/dev/null || true)
[[ $(jq '[.EventSelectors[]? | select(.IncludeManagementEvents == true and .ReadWriteType == "All")] | length' <<<"$selectors" 2>/dev/null || echo 0) -gt 0 ]] && pass "CloudTrail records all management read/write events" || fail "CloudTrail management event selector incomplete"
bucket=$(jq -r '.S3BucketName // empty' <<<"$trail" 2>/dev/null || true)
if [[ -n "$bucket" ]]; then
  [[ $(aws s3api get-bucket-versioning --bucket "$bucket" --query Status --output text 2>/dev/null || true) == Enabled ]] && pass "S3 versioning enabled" || fail "S3 versioning disabled"
  aws s3api get-public-access-block --bucket "$bucket" --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,IgnorePublicAcls,BlockPublicPolicy,RestrictPublicBuckets]' --output text 2>/dev/null | grep -qi '^True[[:space:]]True[[:space:]]True[[:space:]]True' && pass "S3 public access fully blocked" || fail "S3 public access block incomplete"
  aws s3api get-bucket-encryption --bucket "$bucket" --output json >/dev/null 2>&1 && pass "S3 default encryption configured" || fail "S3 encryption missing"
  lock=$(aws s3api get-object-lock-configuration --bucket "$bucket" --query 'ObjectLockConfiguration.ObjectLockEnabled' --output text 2>/dev/null || true)
  [[ "$lock" == Enabled ]] && pass "S3 Object Lock enabled" || warn "S3 Object Lock not enabled; rely on versioning, validation and explicit deny until migration"
else fail "CloudTrail S3 bucket not discoverable"; fi

cw=$(jq -r '.CloudWatchLogsLogGroupArn // empty' <<<"$trail" 2>/dev/null || true)
[[ -n "$cw" ]] && pass "CloudTrail CloudWatch integration configured" || fail "CloudTrail CloudWatch integration absent"
if command -v terraform >/dev/null && [[ -d "$TF_DIR" ]]; then
  terraform -chdir="$TF_DIR" output -json >/dev/null 2>&1 && pass "Terraform outputs readable" || warn "Terraform outputs unavailable (backend/state may not be initialized)"
else warn "Terraform CLI/directory unavailable; output check skipped"; fi
if [[ -n "$OPERATOR_PRINCIPAL" ]]; then
  trail_arn=$(jq -r '.TrailARN' <<<"$trail")
  trail_decisions=$(aws iam simulate-principal-policy --policy-source-arn "$OPERATOR_PRINCIPAL" --action-names cloudtrail:StopLogging cloudtrail:DeleteTrail cloudtrail:PutEventSelectors --resource-arns "$trail_arn" --query 'EvaluationResults[].EvalDecision' --output text 2>/dev/null || true)
  s3_decisions=$(aws iam simulate-principal-policy --policy-source-arn "$OPERATOR_PRINCIPAL" --action-names s3:PutObject s3:DeleteObject s3:DeleteObjectVersion --resource-arns "arn:aws:s3:::$bucket/*" --query 'EvaluationResults[].EvalDecision' --output text 2>/dev/null || true)
  decisions="$trail_decisions $s3_decisions"
  count=$(grep -o 'explicitDeny' <<<"$decisions" | wc -l | tr -d ' ')
  [[ "$count" -ge 6 && ! "$decisions" =~ (allowed|implicitDeny) ]] && pass "Operator tamper simulation returns explicitDeny" || fail "Operator tamper simulation is not explicitDeny for every tested action"
else warn "--operator-principal-arn not supplied; explicit-deny simulation not executed"; fi
(( failures == 0 )) || exit 1
