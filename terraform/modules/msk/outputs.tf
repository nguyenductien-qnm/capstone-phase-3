output "bootstrap_brokers_plaintext" {
  description = "Connection string for Plaintext (port 9092)"
  value       = aws_msk_cluster.this.bootstrap_brokers
}

output "bootstrap_brokers_tls" {
  description = "Connection string for TLS (port 9094)"
  value       = aws_msk_cluster.this.bootstrap_brokers_tls
}

output "bootstrap_brokers_sasl_scram" {
  description = "Connection string for SASL/SCRAM (port 9096)"
  value       = aws_msk_cluster.this.bootstrap_brokers_sasl_scram
}

output "msk_security_group_id" {
  description = "Security Group ID of the MSK cluster"
  value       = aws_security_group.msk.id
}

output "msk_secret_arn" {
  description = "ARN của Secret Manager lưu msk credentials"
  value       = aws_secretsmanager_secret.msk_credentials.arn
}

