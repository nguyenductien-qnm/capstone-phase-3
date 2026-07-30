output "eventbridge_rules" {
  description = "Audit EventBridge rule metadata keyed by rule identifier"
  value = {
    for key, rule in aws_cloudwatch_event_rule.audit : key => {
      name     = rule.name
      arn      = rule.arn
      category = local.audit_rules[key].category
    }
  }
}

output "processing_queue_arn" {
  description = "Main audit processing queue ARN"
  value       = aws_sqs_queue.main.arn
}

output "processing_queue_url" {
  description = "Main audit processing queue URL"
  value       = aws_sqs_queue.main.id
}

output "processing_queue_name" {
  description = "Main audit processing queue name"
  value       = aws_sqs_queue.main.name
}

output "processing_dlq_arn" {
  description = "Processing DLQ ARN"
  value       = aws_sqs_queue.processing_dlq.arn
}

output "processing_dlq_name" {
  description = "Processing DLQ name"
  value       = aws_sqs_queue.processing_dlq.name
}

output "eventbridge_delivery_dlq_arn" {
  description = "EventBridge target-delivery DLQ ARN"
  value       = aws_sqs_queue.eventbridge_delivery_dlq.arn
}

output "eventbridge_delivery_dlq_name" {
  description = "EventBridge target-delivery DLQ name"
  value       = aws_sqs_queue.eventbridge_delivery_dlq.name
}

output "queue_kms_key_arn" {
  description = "KMS key ARN used by audit queues"
  value       = aws_kms_key.queue.arn
}

output "pipeline_health_topic_arn" {
  description = "Pipeline-health SNS topic ARN"
  value       = aws_sns_topic.pipeline_health.arn
}

output "pipeline_health_kms_key_arn" {
  description = "KMS key ARN used by the pipeline-health topic"
  value       = aws_kms_key.pipeline_health.arn
}
