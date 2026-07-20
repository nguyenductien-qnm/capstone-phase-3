output "lambda_security_group_id" {
  description = "Security Group ID of the Lambda function"
  value       = aws_security_group.lambda_sg.id
}
