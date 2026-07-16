output "primary_endpoint_address" {
  description = "Địa chỉ Endpoint của node Primary (dùng ghi/đọc)"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "Địa chỉ Endpoint của node Reader (chỉ đọc)"
  value       = aws_elasticache_replication_group.this.reader_endpoint_address
}

output "port" {
  description = "Cổng kết nối của Valkey cluster"
  value       = aws_elasticache_replication_group.this.port
}

output "secret_arn" {
  description = "ARN của Secret Manager lưu Valkey credentials"
  value       = aws_secretsmanager_secret.valkey_credentials.arn
}
