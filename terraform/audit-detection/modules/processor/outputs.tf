output "lambda_function_name" {
  description = "Slack audit-alert Lambda name"
  value       = aws_lambda_function.slack_alert.function_name
}

output "lambda_function_arn" {
  description = "Slack audit-alert Lambda ARN"
  value       = aws_lambda_function.slack_alert.arn
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda.arn
}

output "idempotency_table_name" {
  description = "CloudTrail eventID idempotency table name"
  value       = aws_dynamodb_table.idempotency.name
}
