# MANDATE-02 — IRSA role cho Cluster Autoscaler (node-layer autoscaling).
# CA chạy trong kube-system (SA: cluster-autoscaler) cần quyền đọc/đổi ASG desiredCapacity
# để scale node UP/DOWN. Dùng IRSA (OIDC) theo đúng chuẩn module (main.tf:130).
#
# Role name CỐ ĐỊNH "<cluster>-cluster-autoscaler" -> ARN đoán trước, gắn thẳng vào
# ServiceAccount annotation trong platform/gitops/applications/cluster-autoscaler.yaml.

locals {
  # Host của OIDC issuer (bỏ https://) để làm khoá điều kiện trust policy.
  oidc_issuer_host = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}

data "aws_iam_policy_document" "cluster_autoscaler_assume" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.cluster.arn]
    }

    # Chỉ SA kube-system/cluster-autoscaler mới assume được role này.
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer_host}:sub"
      values   = ["system:serviceaccount:kube-system:cluster-autoscaler"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_issuer_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster_autoscaler" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  name               = "${local.cluster_name}-cluster-autoscaler"
  assume_role_policy = data.aws_iam_policy_document.cluster_autoscaler_assume[0].json

  tags = {
    Name = "${local.cluster_name}-cluster-autoscaler"
  }
}

# Least-privilege: quyền đọc là *, quyền GHI (đổi capacity/terminate) chỉ trên ASG
# thuộc cluster này (tag k8s.io/cluster-autoscaler/<cluster> = owned do EKS MNG tự gắn).
data "aws_iam_policy_document" "cluster_autoscaler" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  statement {
    sid    = "Discovery"
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:GetInstanceTypesFromInstanceRequirements",
      "eks:DescribeNodegroup",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ManageOwnedAsg"
    effect = "Allow"
    actions = [
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/${local.cluster_name}"
      values   = ["owned"]
    }
  }
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  name   = "${local.cluster_name}-cluster-autoscaler"
  role   = aws_iam_role.cluster_autoscaler[0].id
  policy = data.aws_iam_policy_document.cluster_autoscaler[0].json
}
