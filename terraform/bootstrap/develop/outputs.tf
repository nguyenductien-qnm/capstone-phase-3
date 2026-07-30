output "verified_aws_account_id" {
  description = "AWS account where the bootstrap resources were created"
  value       = data.aws_caller_identity.current.account_id
}

output "terraform_state_bucket" {
  description = "Set this as TF_BACKEND_BUCKET in the GitHub Environment develop"
  value       = aws_s3_bucket.terraform_state.bucket
}

output "github_terraform_role_arn" {
  description = "Set this as TF_AWS_ROLE_ARN in the GitHub Environment develop"
  value       = aws_iam_role.github_terraform.arn
}

output "github_oidc_subject" {
  description = "Only this GitHub OIDC subject can assume the role"
  value       = "repo:${var.github_repository}:environment:${var.github_environment}"
}
