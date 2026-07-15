[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Region,
  [Parameter(Mandatory=$true)][string]$ClusterName,
  [Parameter(Mandatory=$true)][string]$TrailName,
  [string]$TerraformDir = "terraform/environments/sandbox"
)
# AWS CLI uses non-zero exit codes for optional controls such as an S3 bucket
# without Object Lock. Do not let PowerShell 7 convert native stderr into a
# terminating exception; each check below evaluates $LASTEXITCODE explicitly.
$ErrorActionPreference = "Continue"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
  $PSNativeCommandUseErrorActionPreference = $false
}
$failures = 0
function Pass($m){ Write-Host "PASS: $m" -ForegroundColor Green }
function Warn($m){ Write-Host "WARN: $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "FAIL: $m" -ForegroundColor Red; $script:failures++ }
aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json | Out-Null
if($LASTEXITCODE -eq 0){ Pass "AWS caller identity is valid" } else { Fail "AWS caller identity" }
$types = aws eks describe-cluster --region $Region --name $ClusterName --query 'cluster.logging.clusterLogging[0].types' --output text
foreach($t in @('api','audit','authenticator')) { if(($types -split '\s+') -contains $t){ Pass "EKS log type $t enabled" } else { Fail "EKS log type $t missing" } }
$group = "/aws/eks/$ClusterName/cluster"
$retention = aws logs describe-log-groups --region $Region --log-group-name-prefix $group --query "logGroups[?logGroupName=='$group'].retentionInDays|[0]" --output text
if($retention -and $retention -ne 'None' -and [int]$retention -ge 30){
  Pass "EKS log group retention=${retention}d"
} elseif($retention -and $retention -ne 'None') {
  Fail "EKS log group retention=${retention}d; sandbox requires at least 30d"
} else {
  Fail "EKS log group/retention missing"
}
$stream = aws logs describe-log-streams --region $Region --log-group-name $group --log-stream-name-prefix kube-apiserver-audit- --max-items 1 --query 'logStreams[0].logStreamName' --output text
if($stream -and $stream -ne 'None'){ Pass "Kubernetes audit stream exists" } else { Fail "Audit stream missing" }
$status = aws cloudtrail get-trail-status --region $Region --name $TrailName --output json | ConvertFrom-Json
if($status.IsLogging){ Pass "CloudTrail is logging" } else { Fail "CloudTrail is not logging" }
$trail = aws cloudtrail get-trail --region $Region --name $TrailName --query Trail --output json | ConvertFrom-Json
if($trail.LogFileValidationEnabled){ Pass "Log-file validation enabled" } else { Fail "Log-file validation disabled" }
if($trail.CloudWatchLogsLogGroupArn){ Pass "CloudTrail CloudWatch integration configured" } else { Warn "CloudTrail CloudWatch integration absent" }
$version = aws s3api get-bucket-versioning --bucket $trail.S3BucketName --query Status --output text
if($version -eq 'Enabled'){ Pass "S3 versioning enabled" } else { Fail "S3 versioning disabled" }
$public = aws s3api get-public-access-block --bucket $trail.S3BucketName --output json 2>$null | ConvertFrom-Json
if($LASTEXITCODE -eq 0 -and $public.PublicAccessBlockConfiguration.BlockPublicAcls -and $public.PublicAccessBlockConfiguration.IgnorePublicAcls -and $public.PublicAccessBlockConfiguration.BlockPublicPolicy -and $public.PublicAccessBlockConfiguration.RestrictPublicBuckets){ Pass "S3 public access fully blocked" } else { Fail "S3 public access block incomplete" }
aws s3api get-bucket-encryption --bucket $trail.S3BucketName --output json 2>$null | Out-Null
if($LASTEXITCODE -eq 0){ Pass "S3 encryption configured" } else { Fail "S3 encryption missing" }
$lock=aws s3api get-object-lock-configuration --bucket $trail.S3BucketName --query 'ObjectLockConfiguration.ObjectLockEnabled' --output text 2>$null
if($LASTEXITCODE -eq 0 -and $lock -eq 'Enabled'){Pass "Object Lock enabled"}else{Warn "Object Lock disabled; versioning/validation/deny remain controls"}
if(Get-Command terraform -ErrorAction SilentlyContinue){ terraform "-chdir=$TerraformDir" output -json 2>$null | Out-Null; if($LASTEXITCODE -eq 0){Pass "Terraform outputs readable"}else{Warn "Terraform outputs unavailable"} }
if($failures -gt 0){ exit 1 }
