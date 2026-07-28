data "aws_caller_identity" "current" {}

# ─── CDO-259: KMS CMK cho AWS Backup Vault với guardrail chống xoá/disable ────
# Key nằm ở đây vì nó phục vụ trực tiếp vault bên dưới.
# backup_protection chỉ còn lo IAM Deny (CDO-260) — không còn cross-module dep.
data "aws_iam_policy_document" "vault_kms_policy" {
  statement {
    sid    = "EnableIAMUserPermissions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowAWSServicesToUseKey"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:GenerateDataKey*",
      "kms:ReEncrypt*",
    ]
    resources = ["*"]
  }

  # Guardrail: chặn xoá/disable key — kể cả admin thông thường.
  # Chỉ aws-service-role (managed by AWS) mới được exempt.
  statement {
    sid    = "DenyKeyDeletionAndDisabling"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = [
      "kms:ScheduleKeyDeletion",
      "kms:DisableKey",
    ]
    resources = ["*"]

    condition {
      test     = "StringNotLike"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/*"]
    }
  }
}

resource "aws_kms_key" "vault" {
  description             = "Mandate 20 (CDO-259): KMS CMK cho AWS Backup Vault — co guardrail chong xoa/disable"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.vault_kms_policy.json

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-vault-kms"
    Environment = var.environment
    Project     = var.project_name
    Mandate     = "20"
  }
}

resource "aws_kms_alias" "vault" {
  name          = "alias/${var.project_name}-${var.environment}-backup-vault"
  target_key_id = aws_kms_key.vault.key_id
}

# ─── AWS Backup Vault ──────────────────────────────────────────────────────────
resource "aws_backup_vault" "this" {
  name        = "${var.project_name}-${var.environment}-backup-vault"
  kms_key_arn = aws_kms_key.vault.arn

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-vault"
    Environment = var.environment
    Project     = var.project_name
  }
}

# AWS Backup Vault Lock (Governance Mode — gỡ được, không kẹt vĩnh viễn)
resource "aws_backup_vault_lock_configuration" "this" {
  backup_vault_name  = aws_backup_vault.this.name
  min_retention_days = 7
  max_retention_days = 30
}

# ─── AWS Backup Plan ───────────────────────────────────────────────────────────
resource "aws_backup_plan" "this" {
  name = "${var.project_name}-${var.environment}-backup-plan"

  rule {
    rule_name         = "daily-backup-rule"
    target_vault_name = aws_backup_vault.this.name
    schedule          = "cron(0 3 * * ? *)" # 3:00 AM UTC = 10:00 AM VN

    lifecycle {
      delete_after = 7
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-plan"
    Environment = var.environment
    Project     = var.project_name
  }
}

# ─── AWS Backup Selection (chọn resource theo tag Backup=true) ─────────────────
resource "aws_backup_selection" "this" {
  iam_role_arn = aws_iam_role.backup_service_role.arn
  name         = "${var.project_name}-${var.environment}-backup-selection"
  plan_id      = aws_backup_plan.this.id

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "Backup"
    value = "true"
  }
}

# ─── IAM Service Role cho AWS Backup ──────────────────────────────────────────
resource "aws_iam_role" "backup_service_role" {
  name = "${var.project_name}-${var.environment}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "backup.amazonaws.com" }
    }]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "backup_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
  role       = aws_iam_role.backup_service_role.name
}

resource "aws_iam_role_policy_attachment" "restore_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
  role       = aws_iam_role.backup_service_role.name
}
