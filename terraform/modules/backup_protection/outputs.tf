output "policy_arn" {
  value       = aws_iam_policy.backup_protection_deny.arn
  description = "ARN của IAM Deny policy bảo vệ backup (CDO-260)"
}

output "policy_name" {
  value       = aws_iam_policy.backup_protection_deny.name
  description = "Name của IAM Deny policy"
}
