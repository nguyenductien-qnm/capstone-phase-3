# MANDATE-10 P2 — IRSA role cho Kyverno verifyImages.
#
# VÌ SAO BẮT BUỘC (không phải plan B): cả 7 node prod đặt IMDSv2 required với
# hop limit = 1, nên pod KHÔNG mượn được credential của node role qua IMDS (hop
# limit 1 chỉ đủ cho process trên chính host, packet từ network namespace của pod
# bị drop). Node role có AmazonEC2ContainerRegistryReadOnly cũng vô dụng với pod.
# Thiếu IRSA -> verifyImages fail TOÀN BỘ với lỗi ECR auth, và nếu lúc đó
# failurePolicy=Fail thì mọi pod mới trong techx-tf1 bị chặn oan.
#
# Một role dùng chung cho cả 2 controller (admission + reports): quyền y hệt nhau
# (đọc image manifest để verify chữ ký), tách 2 role chỉ thêm bề mặt quản trị mà
# không giảm được quyền nào.

locals {
  # oidc_issuer_url dạng https://oidc.eks.<region>.amazonaws.com/id/XXXX
  # StringEquals condition cần phần sau https:// làm key prefix.
  oidc_provider_url = replace(var.oidc_issuer_url, "https://", "")

  service_account_subs = [
    for sa in var.service_account_names :
    "system:serviceaccount:${var.service_account_namespace}:${sa}"
  ]
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    # StringEquals trên danh sách = khớp BẤT KỲ giá trị nào trong list (OR), nên
    # cả 2 SA dùng chung role mà vẫn khoá đúng tên, không phải wildcard sub.
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = local.service_account_subs
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.project_name}-${var.environment}-kyverno"
  assume_role_policy = data.aws_iam_policy_document.trust.json

  tags = {
    Name        = "${var.project_name}-${var.environment}-kyverno"
    Environment = var.environment
    Project     = var.project_name
  }
}

data "aws_iam_policy_document" "ecr_read" {
  # GetAuthorizationToken KHÔNG nhận resource-level permission (AWS chỉ chấp nhận
  # "*" cho action này) — giới hạn thật nằm ở statement dưới, theo repo ARN.
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Đọc manifest + layer để verify chữ ký. Cosign lấy chữ ký bằng cách pull tag
  # sha256-<digest>.sig như một image thường -> cần đúng bộ 3 quyền read này.
  # KHÔNG có ecr:PutImage/BatchDeleteImage: Kyverno chỉ đọc, không bao giờ ghi.
  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeImages",
    ]
    resources = var.ecr_repository_arns
  }
}

resource "aws_iam_role_policy" "ecr_read" {
  name   = "read-ecr-for-image-verification"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.ecr_read.json
}
