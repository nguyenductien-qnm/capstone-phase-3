# IRSA role cho External Secrets Operator: cho phép ServiceAccount external-secrets
# (namespace external-secrets) assume role qua OIDC và đọc ĐÚNG các Secrets Manager
# secret của RDS/Valkey/MSK — least-privilege (giới hạn theo ARN, không phải *).

locals {
  # oidc_issuer_url dạng https://oidc.eks.<region>.amazonaws.com/id/XXXX
  # StringEquals condition cần phần sau https:// làm key prefix.
  oidc_provider_url = replace(var.oidc_issuer_url, "https://", "")
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    # Chỉ ServiceAccount external-secrets/external-secrets được assume.
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.service_account_namespace}:${var.service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.project_name}-${var.environment}-external-secrets"
  assume_role_policy = data.aws_iam_policy_document.trust.json

  tags = {
    Name        = "${var.project_name}-${var.environment}-external-secrets"
    Environment = var.environment
    Project     = var.project_name
  }
}

data "aws_iam_policy_document" "read_secrets" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    # Giới hạn đúng các secret của RDS/Valkey/MSK. compact() loại null (secret
    # có thể chưa tồn tại khi enable_rds_proxy=false).
    resources = compact(var.secret_arns)
  }
}

resource "aws_iam_role_policy" "read_secrets" {
  name   = "read-platform-secrets"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.read_secrets.json
}
