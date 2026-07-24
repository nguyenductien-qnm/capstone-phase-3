data "aws_caller_identity" "current" {}

# KMS CMK cho AWS Backup Vault
resource "aws_kms_key" "backup_key" {
  description             = "KMS Key ma hoa cho AWS Backup Vault"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLocalAdministration"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowAWSBackupToUseKey"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-kms-key"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_kms_alias" "backup_key_alias" {
  name          = "alias/${var.project_name}-${var.environment}-backup-key"
  target_key_id = aws_kms_key.backup_key.key_id
}

# AWS Backup Vault
resource "aws_backup_vault" "this" {
  name        = "${var.project_name}-${var.environment}-backup-vault"
  kms_key_arn = aws_kms_key.backup_key.arn

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-vault"
    Environment = var.environment
    Project     = var.project_name
  }
}

# AWS Backup Vault Lock (Governance Mode)
resource "aws_backup_vault_lock_configuration" "this" {
  backup_vault_name   = aws_backup_vault.this.name
  changeable_for_days = 3
  min_retention_days  = 7
  max_retention_days  = 30
}

# AWS Backup Plan
resource "aws_backup_plan" "this" {
  name = "${var.project_name}-${var.environment}-backup-plan"

  rule {
    rule_name         = "daily-backup-rule"
    target_vault_name = aws_backup_vault.this.name
    schedule          = "cron(0 3 * * ? *)" # Chạy lúc 3:00 AM UTC hàng ngày (10:00 AM VN)

    lifecycle {
      delete_after = 7 # Lưu giữ bản snapshot trong 7 ngày
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-backup-plan"
    Environment = var.environment
    Project     = var.project_name
  }
}

# AWS Backup Selection
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

# IAM Service Role cho AWS Backup
resource "aws_iam_role" "backup_service_role" {
  name = "${var.project_name}-${var.environment}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
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
