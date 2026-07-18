output "eventbridge_rules" {
  description = "Audit EventBridge rule names and ARNs keyed by rule identifier"
  value = {
    for key, rule in aws_cloudwatch_event_rule.audit : key => {
      name = rule.name
      arn  = rule.arn
    }
  }
}

output "processing_queue_arn" {
  description = "ARN of the durable audit-event processing queue"
  value       = aws_sqs_queue.main.arn
}

output "processing_queue_url" {
  description = "URL of the durable audit-event processing queue"
  value       = aws_sqs_queue.main.id
}

output "processing_dlq_arn" {
  description = "ARN of the Lambda processing DLQ"
  value       = aws_sqs_queue.processing_dlq.arn
}

output "eventbridge_delivery_dlq_arn" {
  description = "ARN of the EventBridge target-delivery DLQ"
  value       = aws_sqs_queue.eventbridge_delivery_dlq.arn
}

output "queue_kms_key_arn" {
  description = "ARN of the customer-managed KMS key used by all audit queues"
  value       = aws_kms_key.queue.arn
}

output "pipeline_health_topic_arn" {
  description = "SNS topic ARN used only for pipeline-health email notifications"
  value       = aws_sns_topic.pipeline_health.arn
}

output "pipeline_health_kms_key_arn" {
  description = "ARN of the independent KMS key used by the pipeline-health SNS topic"
  value       = aws_kms_key.pipeline_health.arn
}

output "lambda_function_name" {
  description = "Name of the Slack audit-alert Lambda function"
  value       = aws_lambda_function.slack_alert.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Slack audit-alert Lambda function"
  value       = aws_lambda_function.slack_alert.arn
}

output "lambda_role_arn" {
  description = "ARN of the least-privilege Lambda execution role"
  value       = aws_iam_role.lambda.arn
}

output "alarm_arns" {
  description = "CloudWatch pipeline-health alarm ARNs keyed by alarm identifier"
  value = merge(
    {
      lambda_errors            = aws_cloudwatch_metric_alarm.lambda_errors.arn
      lambda_throttles         = aws_cloudwatch_metric_alarm.lambda_throttles.arn
      main_queue_age           = aws_cloudwatch_metric_alarm.main_queue_age.arn
      main_queue_backlog       = aws_cloudwatch_metric_alarm.main_queue_backlog.arn
      processing_dlq           = aws_cloudwatch_metric_alarm.processing_dlq.arn
      eventbridge_delivery_dlq = aws_cloudwatch_metric_alarm.eventbridge_delivery_dlq.arn
    },
    {
      for key, alarm in aws_cloudwatch_metric_alarm.eventbridge_failed_invocations :
      "eventbridge_failed_${key}" => alarm.arn
    },
    {
      for key, alarm in aws_cloudwatch_metric_alarm.eventbridge_failed_to_dlq :
      "eventbridge_failed_to_dlq_${key}" => alarm.arn
    }
  )
}
