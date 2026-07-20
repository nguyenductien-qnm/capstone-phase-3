output "eventbridge_rules" {
  description = "Audit EventBridge rule names, ARNs, and categories keyed by rule identifier"
  value       = module.detection_routing.eventbridge_rules
}

output "processing_queue_arn" {
  description = "ARN of the durable audit-event processing queue"
  value       = module.detection_routing.processing_queue_arn
}

output "processing_queue_url" {
  description = "URL of the durable audit-event processing queue"
  value       = module.detection_routing.processing_queue_url
}

output "processing_dlq_arn" {
  description = "ARN of the Lambda processing DLQ"
  value       = module.detection_routing.processing_dlq_arn
}

output "eventbridge_delivery_dlq_arn" {
  description = "ARN of the EventBridge target-delivery DLQ"
  value       = module.detection_routing.eventbridge_delivery_dlq_arn
}

output "queue_kms_key_arn" {
  description = "ARN of the customer-managed KMS key used by all audit queues"
  value       = module.detection_routing.queue_kms_key_arn
}

output "pipeline_health_topic_arn" {
  description = "SNS topic ARN used only for pipeline-health email notifications"
  value       = module.detection_routing.pipeline_health_topic_arn
}

output "pipeline_health_kms_key_arn" {
  description = "ARN of the independent KMS key used by the pipeline-health SNS topic"
  value       = module.detection_routing.pipeline_health_kms_key_arn
}

output "lambda_function_name" {
  description = "Name of the Slack audit-alert Lambda function"
  value       = module.processor.lambda_function_name
}

output "lambda_function_arn" {
  description = "ARN of the Slack audit-alert Lambda function"
  value       = module.processor.lambda_function_arn
}

output "lambda_role_arn" {
  description = "ARN of the least-privilege Lambda execution role"
  value       = module.processor.lambda_role_arn
}

output "idempotency_table_name" {
  description = "DynamoDB table used to suppress duplicate Slack delivery by CloudTrail eventID"
  value       = module.processor.idempotency_table_name
}

output "slack_webhook_secret_arn" {
  description = "Secrets Manager ARN read by the Slack alert Lambda"
  value       = module.processor.slack_webhook_secret_arn
}

output "alarm_arns" {
  description = "CloudWatch pipeline-health alarm ARNs keyed by alarm identifier"
  value       = module.monitoring.alarm_arns
}
