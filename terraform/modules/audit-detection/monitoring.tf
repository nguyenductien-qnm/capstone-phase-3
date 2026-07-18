resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "Audit Slack delivery Lambda returned one or more errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.slack_alert.function_name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-lambda-errors"
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.name_prefix}-lambda-throttles"
  alarm_description   = "Audit Slack delivery Lambda is being throttled"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.slack_alert.function_name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-lambda-throttles"
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "main_queue_age" {
  alarm_name          = "${local.name_prefix}-queue-age"
  alarm_description   = "Oldest queued audit event exceeded the pipeline-health target"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.main.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = var.pipeline_health_threshold_seconds
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-queue-age"
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "main_queue_backlog" {
  alarm_name          = "${local.name_prefix}-queue-backlog"
  alarm_description   = "Visible audit-event backlog exceeded the operational threshold"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.main.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = var.queue_backlog_threshold
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-queue-backlog"
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "processing_dlq" {
  alarm_name          = "${local.name_prefix}-processing-dlq"
  alarm_description   = "One or more audit events exhausted Lambda processing retries"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.processing_dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-processing-dlq"
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "eventbridge_delivery_dlq" {
  alarm_name          = "${local.name_prefix}-eventbridge-dlq"
  alarm_description   = "EventBridge could not deliver one or more audit events to the processing queue"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.eventbridge_delivery_dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-eventbridge-dlq"
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "eventbridge_failed_invocations" {
  for_each = aws_cloudwatch_event_rule.audit

  alarm_name          = substr("${local.name_prefix}-${each.key}-failed", 0, 255)
  alarm_description   = "EventBridge permanently failed to invoke the SQS target for ${each.value.name}"
  namespace           = "AWS/Events"
  metric_name         = "FailedInvocations"
  dimensions          = { RuleName = each.value.name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = substr("${local.name_prefix}-${each.key}-failed", 0, 255)
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}

resource "aws_cloudwatch_metric_alarm" "eventbridge_failed_to_dlq" {
  for_each = aws_cloudwatch_event_rule.audit

  alarm_name          = substr("${local.name_prefix}-${each.key}-failed-to-dlq", 0, 255)
  alarm_description   = "EventBridge could not place a failed invocation into its delivery DLQ for ${each.value.name}"
  namespace           = "AWS/Events"
  metric_name         = "InvocationsFailedToBeSentToDlq"
  dimensions          = { RuleName = each.value.name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.pipeline_health.arn]

  tags = merge(local.common_tags, {
    Name = substr("${local.name_prefix}-${each.key}-failed-to-dlq", 0, 255)
  })

  depends_on = [aws_sns_topic_policy.pipeline_health]
}
