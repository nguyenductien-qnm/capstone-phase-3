data "aws_iam_policy_document" "queue_kms" {
  statement {
    sid     = "AccountAdministration"
    effect  = "Allow"
    actions = ["kms:*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    resources = ["*"]
  }

  statement {
    sid    = "AllowEventBridgeDelivery"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_kms_key" "queue" {
  description             = "Encrypt Mandate 11 audit processing queues"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.queue_kms.json

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-queue"
  })
}

resource "aws_kms_alias" "queue" {
  name          = "alias/${local.name_prefix}-queue"
  target_key_id = aws_kms_key.queue.key_id
}

resource "aws_sqs_queue" "processing_dlq" {
  name                      = "${local.name_prefix}-processing-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = aws_kms_key.queue.arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-processing-dlq"
  })
}

resource "aws_sqs_queue" "main" {
  name                       = "${local.name_prefix}-processing"
  message_retention_seconds  = var.main_queue_retention_seconds
  visibility_timeout_seconds = var.queue_visibility_timeout_seconds
  kms_master_key_id          = aws_kms_key.queue.arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.processing_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  lifecycle {
    precondition {
      condition     = var.queue_visibility_timeout_seconds >= var.lambda_timeout_seconds * 6
      error_message = "queue_visibility_timeout_seconds must be at least six times lambda_timeout_seconds."
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-processing"
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "processing_dlq" {
  queue_url = aws_sqs_queue.processing_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.main.arn]
  })
}

resource "aws_sqs_queue" "eventbridge_delivery_dlq" {
  name                      = "${local.name_prefix}-eventbridge-dlq"
  message_retention_seconds = 1209600
  kms_master_key_id         = aws_kms_key.queue.arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-eventbridge-dlq"
  })
}

data "aws_iam_policy_document" "main_queue" {
  statement {
    sid     = "AllowEventBridgeRules"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    resources = [aws_sqs_queue.main.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [for rule in aws_cloudwatch_event_rule.audit : rule.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["sqs:*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    resources = [aws_sqs_queue.main.arn]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "main" {
  queue_url = aws_sqs_queue.main.id
  policy    = data.aws_iam_policy_document.main_queue.json
}

data "aws_iam_policy_document" "eventbridge_delivery_dlq" {
  statement {
    sid     = "AllowEventBridgeRules"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    resources = [aws_sqs_queue.eventbridge_delivery_dlq.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [for rule in aws_cloudwatch_event_rule.audit : rule.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["sqs:*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    resources = [aws_sqs_queue.eventbridge_delivery_dlq.arn]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "eventbridge_delivery_dlq" {
  queue_url = aws_sqs_queue.eventbridge_delivery_dlq.id
  policy    = data.aws_iam_policy_document.eventbridge_delivery_dlq.json
}
