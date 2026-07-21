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
