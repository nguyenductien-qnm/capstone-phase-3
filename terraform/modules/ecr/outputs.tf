output "repository_urls" {
  description = "Bản đồ chứa URL đẩy ảnh của các ECR repositories"
  value       = { for k, v in aws_ecr_repository.this : k => v.repository_url }
}

output "repository_arns" {
  description = "Bản đồ chứa ARN của các ECR repositories"
  value       = { for k, v in aws_ecr_repository.this : k => v.arn }
}
