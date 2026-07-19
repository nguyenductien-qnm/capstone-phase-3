data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = substr("${var.name_prefix}-slack-alert-role", 0, 64)
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = merge(var.tags, {
    Name = substr("${var.name_prefix}-slack-alert-role", 0, 64)
  })
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid    = "ConsumeAuditQueue"
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ReceiveMessage",
    ]
    resources = [var.processing_queue_arn]
  }

  statement {
    sid    = "WriteOperationalLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  statement {
    sid       = "DecryptAuditQueueMessages"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.queue_kms_key_arn]
  }

  statement {
    sid    = "ManageEventIdempotency"
    effect = "Allow"
    actions = [
      "dynamodb:DeleteItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.idempotency.arn]
  }

  statement {
    sid       = "ReadSlackWebhook"
    effect    = "Allow"
    actions   = local.webhook_is_ssm ? ["ssm:GetParameter"] : ["secretsmanager:GetSecretValue"]
    resources = [var.slack_webhook_parameter_arn]
  }

  dynamic "statement" {
    for_each = var.slack_webhook_kms_key_arn == null ? [] : [var.slack_webhook_kms_key_arn]

    content {
      sid       = "DecryptSlackWebhook"
      effect    = "Allow"
      actions   = ["kms:Decrypt"]
      resources = [statement.value]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${var.name_prefix}-slack-alert"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}
