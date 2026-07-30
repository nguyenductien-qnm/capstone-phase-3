resource "aws_cloudwatch_event_rule" "audit" {
  for_each = local.audit_rules

  name          = substr("${var.name_prefix}-${replace(each.key, "_", "-")}", 0, 64)
  description   = each.value.description
  event_pattern = each.value.event_pattern

  tags = merge(var.tags, {
    Name              = substr("${var.name_prefix}-${replace(each.key, "_", "-")}", 0, 64)
    DetectionCategory = each.value.category
  })
}

resource "aws_cloudwatch_event_target" "processing_queue" {
  for_each = local.audit_rules

  rule      = aws_cloudwatch_event_rule.audit[each.key].name
  target_id = "audit-processing-queue"
  arn       = aws_sqs_queue.main.arn

  input_transformer {
    input_paths = {
      event = "$"
    }
    input_template = <<-EOT
      {"detectionCategory":${jsonencode(each.value.category)},"ruleKey":${jsonencode(each.key)},"event":<event>}
    EOT
  }

  retry_policy {
    maximum_event_age_in_seconds = var.eventbridge_max_event_age_seconds
    maximum_retry_attempts       = var.eventbridge_max_retry_attempts
  }

  dead_letter_config {
    arn = aws_sqs_queue.eventbridge_delivery_dlq.arn
  }

  depends_on = [
    aws_sqs_queue_policy.main,
    aws_sqs_queue_policy.eventbridge_delivery_dlq,
  ]
}

