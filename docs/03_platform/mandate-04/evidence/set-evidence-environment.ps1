# Dot-source this file from the repository root:
# . .\docs\cdo09\evidence-mandate-04\set-evidence-environment.ps1

$env:AWS_PROFILE = "phase3-cdo"
$env:AWS_REGION = "us-east-1"
$Region = "us-east-1"

$EvidenceRoot = "docs/cdo09/evidence-mandate-04"
$LogDir = "$EvidenceRoot/logs"
$ScreenshotDir = "$EvidenceRoot/screenshots"

$Cluster = terraform -chdir=terraform/environments/sandbox output -raw eks_cluster_name
$Trail = terraform -chdir=terraform/environments/sandbox output -raw cloudtrail_name
$TrailArn = terraform -chdir=terraform/environments/sandbox output -raw cloudtrail_arn
$Bucket = terraform -chdir=terraform/environments/sandbox output -raw cloudtrail_s3_bucket_name
$LogGroup = "/aws/eks/$Cluster/cluster"

Write-Host "AWS evidence environment loaded:" -ForegroundColor Green
[PSCustomObject]@{
  Profile  = $env:AWS_PROFILE
  Region   = $Region
  Cluster  = $Cluster
  Trail    = $Trail
  Bucket   = $Bucket
  LogGroup = $LogGroup
} | Format-List
