output "role_arn" {
  description = "ARN IAM role IRSA để annotate ServiceAccount admission/reports controller của Kyverno (values chart: <controller>.serviceAccount.annotations)"
  value       = aws_iam_role.this.arn
}
