data "aws_caller_identity" "current" {}


# 1. Dedicated KMS Key for DR Backup Encryption with Anti-Deletion Guardrail (CDO-259)
data "aws_iam_policy_document" "kms_backup_policy" {
  count = var.enable_kms_key ? 1 : 0

  statement {
    sid    = "Enable IAM User Permissions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "Allow AWS Services to use KMS for Encryption/Decryption"
    effect = "Allow"

    principals {
      type = "Service"
      identifiers = [
        "backup.amazonaws.com",
        "rds.amazonaws.com",
        "elasticache.amazonaws.com"
      ]
    }

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:GenerateDataKey*",
      "kms:ReEncrypt*"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "Deny KMS Key Deletion and Disabling by Standard Roles"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = [
      "kms:ScheduleKeyDeletion",
      "kms:DisableKey"
    ]
    resources = ["*"]

    condition {
      test     = "StringNotLike"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/*"]
    }
  }
}

resource "aws_kms_key" "dr_backup" {
  count = var.enable_kms_key ? 1 : 0

  description             = "Mandate 20: KMS Customer Managed Key for DR backup encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms_backup_policy[0].json

  tags = {
    Name        = "${var.project_name}-${var.environment}-dr-backup-kms"
    Environment = var.environment
    Project     = var.project_name
    Mandate     = "20"
  }
}

resource "aws_kms_alias" "dr_backup" {
  count = var.enable_kms_key ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-dr-backup"
  target_key_id = aws_kms_key.dr_backup[0].key_id
}

# 2. Explicit IAM Deny Policy to Prevent Backup & Snapshot Deletion (CDO-260)
resource "aws_iam_policy" "backup_protection_deny" {
  name        = "${var.project_name}-${var.environment}-dr-backup-protection-deny"
  path        = "/"
  description = "Mandate 20: Explicit Deny policy to protect backups and snapshots from unauthorized deletion"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyBackupDeletion"
        Effect = "Deny"
        Action = [
          "rds:DeleteDBSnapshot",
          "rds:DeleteDBClusterSnapshot",
          "backup:DeleteRecoveryPoint",
          "backup:DeleteBackupVault",
          "backup:DeleteBackupVaultAccessPolicy",
          "backup:DeleteBackupPlan",
          "ec2:DeleteSnapshot",
          "elasticache:DeleteSnapshot"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-dr-backup-protection-deny"
    Environment = var.environment
    Project     = var.project_name
    Mandate     = "20"
  }
}

# Attach IAM Deny policy to configured operator role names
resource "aws_iam_role_policy_attachment" "operator_backup_protection" {
  for_each   = toset(var.operator_role_names)
  role       = each.value
  policy_arn = aws_iam_policy.backup_protection_deny.arn
}
