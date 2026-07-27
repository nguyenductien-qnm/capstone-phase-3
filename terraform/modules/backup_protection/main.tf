data "aws_caller_identity" "current" {}

# CDO-260: Explicit IAM Deny Policy — chặn xoá backup/snapshot từ role vận hành.
# KMS CMK cho vault nằm trong module backup (cùng chỗ với vault) để tránh
# cross-module dependency gây lỗi "count depends on unknown value" lúc plan.
resource "aws_iam_policy" "backup_protection_deny" {
  name        = "${var.project_name}-${var.environment}-dr-backup-protection-deny"
  path        = "/"
  description = "Mandate 20 (CDO-260): Explicit Deny chong xoa backup va snapshot"

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
          "elasticache:DeleteSnapshot",
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

# Attach IAM Deny policy lên các role vận hành được truyền vào
resource "aws_iam_role_policy_attachment" "operator_backup_protection" {
  for_each   = toset(var.operator_role_names)
  role       = each.value
  policy_arn = aws_iam_policy.backup_protection_deny.arn
}
