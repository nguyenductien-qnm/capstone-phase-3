output "role_arn" {
  description = "ARN IAM role IRSA để annotate ServiceAccount External Secrets Operator"
  value       = aws_iam_role.this.arn
}
