output "role_arn" {
  description = "ARN của IAM role cho external-dns (dùng annotate ServiceAccount)"
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Tên IAM role cho external-dns"
  value       = aws_iam_role.this.name
}
