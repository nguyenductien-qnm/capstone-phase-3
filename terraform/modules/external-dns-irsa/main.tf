# IRSA role cho external-dns: cho phép ServiceAccount external-dns (namespace
# external-dns) assume role qua OIDC và ghi record ĐÚNG một hosted zone —
# least-privilege (ChangeResourceRecordSets giới hạn theo zone ID, không phải *).
#
# Mục đích: external-dns tự tạo/cập nhật record trỏ về NLB do AWS LB Controller
# sinh ra, để CloudFront origin dùng tên cố định (origin.<subdomain>) thay vì DNS
# ngẫu nhiên của NLB — bỏ được vòng apply 2-pass.

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

    # Chỉ ServiceAccount external-dns/external-dns được assume.
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
  name               = "${var.project_name}-${var.environment}-external-dns"
  assume_role_policy = data.aws_iam_policy_document.trust.json

  tags = {
    Name        = "${var.project_name}-${var.environment}-external-dns"
    Environment = var.environment
    Project     = var.project_name
  }
}

data "aws_iam_policy_document" "manage_records" {
  # Ghi record: chỉ trong hosted zone được chỉ định.
  statement {
    effect    = "Allow"
    actions   = ["route53:ChangeResourceRecordSets"]
    resources = ["arn:aws:route53:::hostedzone/${var.hosted_zone_id}"]
  }

  # Đọc zone/record để reconcile. Các action này không nhận resource-level
  # permission (AWS bắt buộc "*") — chỉ là read-only nên không mở rộng rủi ro ghi.
  statement {
    effect = "Allow"
    actions = [
      "route53:ListHostedZones",
      "route53:ListResourceRecordSets",
      "route53:ListTagsForResource",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "manage_records" {
  name   = "manage-dns-records"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.manage_records.json
}
