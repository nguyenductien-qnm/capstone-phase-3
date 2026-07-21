data "aws_iam_policy_document" "pipeline_health_kms" {
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
    sid    = "AllowCloudWatchAlarmNotifications"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${data.aws_partition.current.partition}:cloudwatch:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:alarm:${var.name_prefix}-*"]
    }
  }

  statement {
    sid    = "AllowSNSTopicEncryption"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:aws:sns:topicArn"
      values   = ["arn:${data.aws_partition.current.partition}:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${var.name_prefix}-pipeline-health"]
    }
  }
}

resource "aws_kms_key" "pipeline_health" {
  description             = "Encrypt Mandate 11 pipeline-health notifications"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.pipeline_health_kms.json

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-pipeline-health"
  })
}

resource "aws_kms_alias" "pipeline_health" {
  name          = "alias/${var.name_prefix}-pipeline-health"
  target_key_id = aws_kms_key.pipeline_health.key_id
}

resource "aws_sns_topic" "pipeline_health" {
  name              = "${var.name_prefix}-pipeline-health"
  kms_master_key_id = aws_kms_key.pipeline_health.arn

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-pipeline-health"
  })
}

resource "aws_sns_topic_subscription" "pipeline_health_email" {
  for_each = var.pipeline_health_email_endpoints

  topic_arn = aws_sns_topic.pipeline_health.arn
  protocol  = "email"
  endpoint  = each.value
}

data "aws_iam_policy_document" "pipeline_health_topic" {
  statement {
    sid    = "AccountAdministration"
    effect = "Allow"
    actions = [
      "sns:AddPermission",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:Publish",
      "sns:RemovePermission",
      "sns:SetTopicAttributes",
      "sns:Subscribe",
    ]

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    resources = [aws_sns_topic.pipeline_health.arn]
  }

  statement {
    sid     = "AllowCloudWatchAlarms"
    effect  = "Allow"
    actions = ["sns:Publish"]

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    resources = [aws_sns_topic.pipeline_health.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${data.aws_partition.current.partition}:cloudwatch:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:alarm:${var.name_prefix}-*"]
    }
  }

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    # SNS topic policies reject the service-wide wildcard as out of scope.
    # Enumerate the complete, long-supported topic-policy action set instead.
    actions = [
      "sns:AddPermission",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:Publish",
      "sns:RemovePermission",
      "sns:SetTopicAttributes",
      "sns:Subscribe",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    resources = [aws_sns_topic.pipeline_health.arn]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sns_topic_policy" "pipeline_health" {
  arn    = aws_sns_topic.pipeline_health.arn
  policy = data.aws_iam_policy_document.pipeline_health_topic.json
}
