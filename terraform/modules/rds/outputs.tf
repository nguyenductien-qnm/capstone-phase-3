output "db_primary_endpoint" {
  description = "Connection endpoint cho Primary Database (host:port)"
  value       = aws_db_instance.this.endpoint
}

output "db_primary_address" {
  description = "Địa chỉ host của Primary Database"
  value       = aws_db_instance.this.address
}

output "db_replica_endpoint" {
  description = "Connection endpoint cho Read Replica Database (host:port) nếu bật"
  value       = var.enable_read_replica ? aws_db_instance.replica[0].endpoint : null
}

output "db_proxy_endpoint" {
  description = "Endpoint để ứng dụng kết nối qua RDS Proxy"
  value       = var.enable_rds_proxy ? aws_db_proxy.this[0].endpoint : null
}

output "db_secret_arn" {
  description = "ARN Secret credentials DB (dùng cho RDS Proxy auth)"
  value       = var.enable_rds_proxy ? aws_secretsmanager_secret.db_credentials[0].arn : null
}

output "db_endpoint_secret_arn" {
  description = "ARN Secret chứa endpoint DB (host+proxy) cho ESO"
  value       = aws_secretsmanager_secret.db_endpoint[0].arn
}

output "db_password" {
  description = "Mật khẩu quản trị database (sensitive)"
  value       = random_password.db_password.result
  sensitive   = true
}

output "db_username" {
  description = "Username quản trị database"
  value       = var.db_username
}
