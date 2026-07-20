locals {
  lambda_function_name = substr("${var.name_prefix}-slack-alert", 0, 64)
  webhook_is_ssm       = length(regexall(":ssm:", var.slack_webhook_parameter_arn)) > 0
}
