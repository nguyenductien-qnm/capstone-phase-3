data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix          = substr("${var.project_name}-${var.environment}-audit", 0, 32)
  lambda_function_name = substr("${local.name_prefix}-slack-alert", 0, 64)

  common_tags = merge(var.tags, {
    Component   = "audit-detection"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "CDO-05"
    Project     = var.project_name
  })

  webhook_is_ssm = length(regexall(":ssm:", var.slack_webhook_parameter_arn)) > 0
}
