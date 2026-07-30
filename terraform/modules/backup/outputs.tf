output "backup_vault_name" {
  value       = aws_backup_vault.this.name
  description = "Name of the AWS Backup Vault"
}

output "backup_vault_arn" {
  value       = aws_backup_vault.this.arn
  description = "ARN of the AWS Backup Vault"
}

output "backup_plan_id" {
  value       = aws_backup_plan.this.id
  description = "ID of the AWS Backup Plan"
}

output "backup_plan_arn" {
  value       = aws_backup_plan.this.arn
  description = "ARN of the AWS Backup Plan"
}

output "vault_kms_key_arn" {
  value       = aws_kms_key.vault.arn
  description = "ARN of KMS CMK dùng mã hoá Backup Vault (CDO-259)"
}
