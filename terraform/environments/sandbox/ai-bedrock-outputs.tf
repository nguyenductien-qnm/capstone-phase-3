output "ai_bedrock_irsa_role_arn" {
  description = "ARN IAM role cho AI workloads (product-reviews/shopping-copilot) goi Bedrock runtime"
  value       = module.ai_bedrock_irsa.role_arn
}
