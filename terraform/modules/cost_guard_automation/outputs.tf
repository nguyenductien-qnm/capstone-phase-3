output "sns_topic_80_arn" {
  description = "ARN của SNS topic cho Budget Alarms 80%"
  value       = aws_sns_topic.budget_alarms_80.arn
}

output "sns_topic_95_arn" {
  description = "ARN của SNS topic cho Budget Alarms 95%"
  value       = aws_sns_topic.budget_alarms_95.arn
}

output "lambda_function_arn" {
  description = "ARN của Lambda function"
  value       = aws_lambda_function.cost_guard.arn
}

output "lambda_function_name" {
  description = "Tên của Lambda function"
  value       = aws_lambda_function.cost_guard.function_name
}

output "lambda_role_arn" {
  description = "ARN của IAM role cho Lambda"
  value       = aws_iam_role.lambda_role.arn
}

output "custom_budget_names" {
  description = "Danh sách tên các custom budget period"
  value       = [for budget in values(aws_budgets_budget.custom_period) : budget.name]
}

output "monthly_budget_80_name" {
  description = "Tên budget alarm 80% cho fallback monthly"
  value       = try(aws_budgets_budget.monthly_80_percent[0].name, null)
}

output "monthly_budget_95_name" {
  description = "Tên budget alarm 95% cho fallback monthly"
  value       = try(aws_budgets_budget.monthly_95_percent[0].name, null)
}

output "cloudwatch_log_group_name" {
  description = "Tên CloudWatch Log Group cho Lambda"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}
