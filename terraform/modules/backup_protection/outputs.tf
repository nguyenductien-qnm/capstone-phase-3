output "kms_key_arn" {
  value       = var.enable_kms_key ? aws_kms_key.dr_backup[0].arn : null
  description = "ARN of the DR backup KMS key"
}

output "kms_key_id" {
  value       = var.enable_kms_key ? aws_kms_key.dr_backup[0].key_id : null
  description = "ID of the DR backup KMS key"
}

output "policy_arn" {
  value       = aws_iam_policy.backup_protection_deny.arn
  description = "ARN of the explicit IAM Deny policy for backup deletion protection"
}

output "policy_name" {
  value       = aws_iam_policy.backup_protection_deny.name
  description = "Name of the explicit IAM Deny policy"
}
