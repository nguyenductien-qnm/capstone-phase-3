output "guardrail_id" {
  description = "Set as BEDROCK_GUARDRAIL_ID in values-aio-llm.yaml."
  value       = aws_bedrock_guardrail.aio.guardrail_id
}

output "guardrail_arn" {
  value = aws_bedrock_guardrail.aio.guardrail_arn
}

output "guardrail_version" {
  description = "Set as BEDROCK_GUARDRAIL_VERSION. Pin this — never DRAFT."
  value       = aws_bedrock_guardrail_version.aio.version
}
