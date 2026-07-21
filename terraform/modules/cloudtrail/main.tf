data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  trail_name        = "${var.project_name}-${var.environment}-audit-trail"
  exempt_principals = concat(var.audit_administrator_principals, var.break_glass_principals)
  kms_key_arn       = var.enable_kms_encryption ? aws_kms_key.audit[0].arn : null
  m12_alert_name    = "${var.project_name}-${var.environment}-m12-audit-tamper"
}

resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket              = "${var.project_name}-${var.environment}-cloudtrail-logs"
  object_lock_enabled = var.enable_object_lock
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket                  = aws_s3_bucket.cloudtrail_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.enable_kms_encryption ? "aws:kms" : "AES256"
      kms_master_key_id = local.kms_key_arn
    }
    bucket_key_enabled = var.enable_kms_encryption
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  rule {
    id     = "archive-and-retain-audit-logs"
    status = "Enabled"
    filter {}
    transition {
      days          = var.s3_transition_days
      storage_class = var.s3_transition_storage_class
    }
    expiration { days = var.s3_retention_days }
    noncurrent_version_expiration { noncurrent_days = var.s3_retention_days }
  }
  depends_on = [aws_s3_bucket_versioning.cloudtrail_logs]
}

resource "aws_s3_bucket_object_lock_configuration" "cloudtrail_logs" {
  count  = var.enable_object_lock ? 1 : 0
  bucket = aws_s3_bucket.cloudtrail_logs.id
  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.object_lock_retention_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.cloudtrail_logs]
}

resource "aws_kms_key" "audit" {
  count                   = var.enable_kms_encryption ? 1 : 0
  description             = "CloudTrail audit log encryption for ${local.trail_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountKeyAdministration"
        Effect    = "Allow"
        Principal = { AWS = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudTrailDescribeKey"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "kms:DescribeKey"
        Resource  = "*"
      },
      {
        Sid       = "CloudTrailGenerateDataKey"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "kms:GenerateDataKey*"
        Resource  = "*"
        Condition = {
          StringEquals = { "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/${local.trail_name}" }
          StringLike   = { "kms:EncryptionContext:aws:cloudtrail:arn" = "arn:${data.aws_partition.current.partition}:cloudtrail:*:${data.aws_caller_identity.current.account_id}:trail/*" }
        }
      },
      {
        Sid       = "CloudWatchLogsUse"
        Effect    = "Allow"
        Principal = { Service = "logs.${data.aws_region.current.name}.amazonaws.com" }
        Action    = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
        Resource  = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/cloudtrail/${local.trail_name}"
          }
        }
      }
    ]
  })
  lifecycle { prevent_destroy = true }
  tags = { Name = "${local.trail_name}-logs" }
}

resource "aws_kms_alias" "audit" {
  count         = var.enable_kms_encryption ? 1 : 0
  name          = "alias/${local.trail_name}-logs"
  target_key_id = aws_kms_key.audit[0].key_id
}

resource "aws_s3_bucket_policy" "cloudtrail_bucket_policy" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*",
        Resource  = [aws_s3_bucket.cloudtrail_logs.arn, "${aws_s3_bucket.cloudtrail_logs.arn}/*"],
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "AWSCloudTrailAclCheck", Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" },
        Action    = "s3:GetBucketAcl", Resource = aws_s3_bucket.cloudtrail_logs.arn,
        Condition = { StringEquals = { "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/${local.trail_name}" } }
      },
      {
        Sid    = "AWSCloudTrailWrite", Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" },
        Action = "s3:PutObject", Resource = "${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*",
        Condition = { StringEquals = {
          "s3:x-amz-acl"  = "bucket-owner-full-control",
          "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/${local.trail_name}"
        } }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "cloudtrail" {
  count             = var.enable_cloudwatch_logs ? 1 : 0
  name              = "/aws/cloudtrail/${local.trail_name}"
  retention_in_days = var.cloudwatch_log_retention_days
  kms_key_id        = local.kms_key_arn
  lifecycle { prevent_destroy = true }
}

resource "aws_iam_role" "cloudtrail_cloudwatch" {
  count = var.enable_cloudwatch_logs ? 1 : 0
  name  = "${local.trail_name}-cloudwatch"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}

resource "aws_iam_role_policy" "cloudtrail_cloudwatch" {
  count = var.enable_cloudwatch_logs ? 1 : 0
  role  = aws_iam_role.cloudtrail_cloudwatch[0].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"],
    Resource = "${aws_cloudwatch_log_group.cloudtrail[0].arn}:log-stream:${data.aws_caller_identity.current.account_id}_CloudTrail_${data.aws_region.current.name}*"
  }] })
}

resource "aws_cloudtrail" "main_trail" {
  name                          = local.trail_name
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  kms_key_id                    = local.kms_key_arn
  cloud_watch_logs_group_arn    = var.enable_cloudwatch_logs ? "${aws_cloudwatch_log_group.cloudtrail[0].arn}:*" : null
  cloud_watch_logs_role_arn     = var.enable_cloudwatch_logs ? aws_iam_role.cloudtrail_cloudwatch[0].arn : null

  advanced_event_selector {
    name = "ManagementEvents"

    field_selector {
      field  = "eventCategory"
      equals = ["Management"]
    }
  }

  dynamic "advanced_event_selector" {
    for_each = length(var.cloudtrail_s3_data_event_bucket_arns) > 0 ? [1] : []

    content {
      name = "S3ReadDataEvents"

      field_selector {
        field  = "eventCategory"
        equals = ["Data"]
      }

      field_selector {
        field  = "resources.type"
        equals = ["AWS::S3::Object"]
      }

      field_selector {
        field       = "resources.ARN"
        starts_with = var.cloudtrail_s3_data_event_bucket_arns
      }

      field_selector {
        field  = "readOnly"
        equals = ["true"]
      }
    }
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail_bucket_policy, aws_iam_role_policy.cloudtrail_cloudwatch]
  lifecycle { prevent_destroy = true }
}

resource "aws_sns_topic" "mandate_12_audit_tamper" {
  count = var.enable_mandate_12_alert ? 1 : 0

  name = local.m12_alert_name

  lifecycle {
    precondition {
      condition     = trimspace(var.mandate_12_alert_email) != ""
      error_message = "mandate_12_alert_email must be set when enable_mandate_12_alert is true."
    }
  }
}

resource "aws_cloudwatch_event_rule" "mandate_12_audit_tamper" {
  count = var.enable_mandate_12_alert ? 1 : 0

  name        = local.m12_alert_name
  description = "MANDATE-12 alert for CloudTrail and audit guardrail tamper attempts"

  event_pattern = jsonencode({
    "detail-type" = ["AWS API Call via CloudTrail"]
    "$or" = [
      {
        detail = {
          eventSource = ["cloudtrail.amazonaws.com"]
          eventName = [
            "StopLogging",
            "DeleteTrail",
            "UpdateTrail",
            "PutEventSelectors",
            "PutInsightSelectors",
          ]
        }
      },
      {
        detail = {
          eventSource = ["iam.amazonaws.com"]
          eventName = [
            "DetachRolePolicy",
            "DeletePolicy",
            "DeletePolicyVersion",
            "CreatePolicyVersion",
            "SetDefaultPolicyVersion",
          ]
          requestParameters = {
            policyArn = [aws_iam_policy.audit_log_tamper_protection.arn]
          }
        }
      },
      {
        detail = {
          eventSource = ["sso.amazonaws.com"]
          eventName   = ["DetachCustomerManagedPolicyReferenceFromPermissionSet"]
          requestParameters = {
            customerManagedPolicyReference = {
              name = [aws_iam_policy.audit_log_tamper_protection.name]
              path = ["/"]
            }
          }
        }
      },
    ]
  })
}

data "aws_iam_policy_document" "mandate_12_audit_tamper_sns" {
  count = var.enable_mandate_12_alert ? 1 : 0

  statement {
    sid    = "AllowEventBridgePublishMandate12AuditTamper"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.mandate_12_audit_tamper[0].arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.mandate_12_audit_tamper[0].arn]
    }
  }
}

resource "aws_sns_topic_policy" "mandate_12_audit_tamper" {
  count = var.enable_mandate_12_alert ? 1 : 0

  arn    = aws_sns_topic.mandate_12_audit_tamper[0].arn
  policy = data.aws_iam_policy_document.mandate_12_audit_tamper_sns[0].json
}

resource "aws_sns_topic_subscription" "mandate_12_email" {
  count = var.enable_mandate_12_alert ? 1 : 0

  topic_arn = aws_sns_topic.mandate_12_audit_tamper[0].arn
  protocol  = "email"
  endpoint  = var.mandate_12_alert_email
}

resource "aws_cloudwatch_event_target" "mandate_12_audit_tamper_email" {
  count = var.enable_mandate_12_alert ? 1 : 0

  rule      = aws_cloudwatch_event_rule.mandate_12_audit_tamper[0].name
  target_id = "m12-audit-tamper-email"
  arn       = aws_sns_topic.mandate_12_audit_tamper[0].arn

  depends_on = [aws_sns_topic_policy.mandate_12_audit_tamper]
}

data "aws_iam_policy_document" "audit_log_tamper_protection" {
  statement {
    sid    = "DenyCloudTrailTampering"
    effect = "Deny"
    actions = [
      "cloudtrail:StopLogging",
      "cloudtrail:DeleteTrail",
      "cloudtrail:UpdateTrail",
      "cloudtrail:PutEventSelectors",
      "cloudtrail:PutInsightSelectors",
    ]
    resources = ["arn:${data.aws_partition.current.partition}:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/${local.trail_name}"]
    dynamic "condition" {
      for_each = length(local.exempt_principals) > 0 ? [1] : []
      content {
        test     = "ArnNotLike"
        variable = "aws:PrincipalArn"
        values   = local.exempt_principals
      }
    }
  }

  dynamic "statement" {
    for_each = var.enable_cloudwatch_logs ? [1] : []
    content {
      sid    = "DenyAuditLogDeletionAndRetentionWeakening"
      effect = "Deny"
      actions = [
        "logs:DeleteLogGroup",
        "logs:DeleteLogStream",
        "logs:DeleteRetentionPolicy",
        "logs:PutRetentionPolicy",
        "logs:AssociateKmsKey",
        "logs:DisassociateKmsKey",
      ]
      resources = [aws_cloudwatch_log_group.cloudtrail[0].arn, "${aws_cloudwatch_log_group.cloudtrail[0].arn}:*"]
    }
  }

  statement {
    sid    = "DenyAuditBucketTampering"
    effect = "Deny"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
      "s3:DeleteBucket",
      "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration",
      "s3:DeleteBucketEncryption",
      "s3:PutLifecycleConfiguration",
      "s3:DeleteBucketLifecycle",
      "s3:PutBucketPublicAccessBlock",
      "s3:DeletePublicAccessBlock",
      "s3:PutBucketObjectLockConfiguration",
      "s3:BypassGovernanceRetention",
    ]
    resources = [aws_s3_bucket.cloudtrail_logs.arn, "${aws_s3_bucket.cloudtrail_logs.arn}/*"]
  }

  dynamic "statement" {
    for_each = var.enable_kms_encryption ? [1] : []
    content {
      sid    = "DenyAuditKeyTampering"
      effect = "Deny"
      actions = [
        "kms:ScheduleKeyDeletion",
        "kms:DisableKey",
        "kms:DisableKeyRotation",
        "kms:PutKeyPolicy",
        "kms:RevokeGrant",
      ]
      resources = [aws_kms_key.audit[0].arn]
    }
  }
}

resource "aws_iam_policy" "audit_log_tamper_protection" {
  name        = "${var.project_name}-${var.environment}-audit-log-tamper-deny"
  description = "Explicitly deny routine operators from weakening or deleting audit evidence"
  policy      = data.aws_iam_policy_document.audit_log_tamper_protection.json
}

resource "aws_iam_role_policy_attachment" "operator_tamper_protection" {
  for_each   = toset(var.operator_role_names)
  role       = each.value
  policy_arn = aws_iam_policy.audit_log_tamper_protection.arn
}
