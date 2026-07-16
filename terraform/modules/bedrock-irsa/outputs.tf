output "role_arn" {
  description = "IAM role ARN to annotate the AI workload ServiceAccount."
  value       = aws_iam_role.this.arn
}
