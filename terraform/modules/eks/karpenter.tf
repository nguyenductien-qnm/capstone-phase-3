data "aws_iam_policy_document" "karpenter_controller_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "karpenter_controller" {
  name               = "${local.cluster_name}-karpenter-controller"
  assume_role_policy = data.aws_iam_policy_document.karpenter_controller_assume.json

  tags = {
    Name = "${local.cluster_name}-karpenter-controller"
  }
}

data "aws_iam_policy_document" "karpenter_node_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "karpenter_node" {
  name               = "${local.cluster_name}-karpenter-node"
  assume_role_policy = data.aws_iam_policy_document.karpenter_node_assume.json

  tags = {
    Name = "${local.cluster_name}-karpenter-node"
  }
}

resource "aws_iam_role_policy_attachment" "karpenter_node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryPullOnly",
    "AmazonSSMManagedInstanceCore",
  ])

  role       = aws_iam_role.karpenter_node.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.value}"
}

resource "aws_iam_instance_profile" "karpenter_node" {
  name = "${local.cluster_name}-karpenter-node"
  role = aws_iam_role.karpenter_node.name

  tags = {
    Name = "${local.cluster_name}-karpenter-node"
  }
}

resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = aws_iam_role.karpenter_node.arn
  type          = "EC2_LINUX"

  tags = {
    Name = "${local.cluster_name}-karpenter-node"
  }
}

data "aws_iam_policy_document" "karpenter_controller" {
  statement {
    sid       = "DescribeCluster"
    effect    = "Allow"
    actions   = ["eks:DescribeCluster"]
    resources = [aws_eks_cluster.this.arn]
  }

  statement {
    sid    = "ReadInfrastructure"
    effect = "Allow"
    actions = [
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeCapacityReservations",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeInstances",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribePlacementGroups",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSpotPriceHistory",
      "ec2:DescribeSubnets",
      "iam:ListInstanceProfiles",
      "pricing:GetProducts",
      "ssm:GetParameter",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "LaunchInstances"
    effect = "Allow"
    actions = [
      "ec2:CreateFleet",
      "ec2:CreateLaunchTemplate",
      "ec2:CreateTags",
      "ec2:RunInstances",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "InstanceProfileOrchestration"
    effect = "Allow"
    actions = [
      "iam:CreateInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:GetInstanceProfile",
      "iam:TagInstanceProfile",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "TerminateOwnedInstances"
    effect = "Allow"
    actions = [
      "ec2:DeleteLaunchTemplate",
      "ec2:TerminateInstances",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/kubernetes.io/cluster/${local.cluster_name}"
      values   = ["owned"]
    }

    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/karpenter.sh/nodepool"
      values   = ["*"]
    }
  }

  statement {
    sid       = "PassKarpenterNodeRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.karpenter_node.arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  statement {
    sid       = "AllowInterruptionQueueActions"
    effect    = "Allow"
    resources = [aws_sqs_queue.karpenter_interruption.arn]
    actions = [
      "sqs:DeleteMessage",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
  }
}

resource "aws_iam_role_policy" "karpenter_controller" {
  name   = "${local.cluster_name}-karpenter-controller"
  role   = aws_iam_role.karpenter_controller.id
  policy = data.aws_iam_policy_document.karpenter_controller.json
}

resource "aws_eks_pod_identity_association" "karpenter_controller" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "kube-system"
  service_account = "karpenter"
  role_arn        = aws_iam_role.karpenter_controller.arn
}

# Spot capacity: AWS account cần AWSServiceRoleForEC2Spot tồn tại trước khi
# CreateFleet với capacity-type=spot chạy được. Controller không tự tạo được
# (thiếu iam:CreateServiceLinkedRole trong policy), nên khai báo tường minh ở đây.
resource "aws_iam_service_linked_role" "spot" {
  aws_service_name = "spot.amazonaws.com"
}

resource "aws_ec2_tag" "karpenter_cluster_security_group_discovery" {
  resource_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  key         = "karpenter.sh/discovery"
  value       = local.cluster_name
}

# Spot capacity: Karpenter cần nhận cảnh báo interruption (spot reclaim, rebalance
# recommendation, instance state change...) trước khi AWS thu hồi instance, để kịp
# drain pod graceful thay vì mất đột ngột. Không có queue này thì NodePool dùng
# capacity-type=spot vẫn launch được nhưng mất khả năng graceful shutdown.
resource "aws_sqs_queue" "karpenter_interruption" {
  name                      = "${local.cluster_name}-karpenter"
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true

  tags = {
    Name = "${local.cluster_name}-karpenter"
  }

  lifecycle {
    ignore_changes = [tags["karpenter.sh/discovery"]]
  }
}

data "aws_iam_policy_document" "karpenter_interruption_queue" {
  statement {
    sid       = "AllowEventBridgeToSendMessages"
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.karpenter_interruption.arn]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "sqs.amazonaws.com"]
    }
  }

  statement {
    sid       = "DenyHTTP"
    effect    = "Deny"
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.karpenter_interruption.arn]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  queue_url = aws_sqs_queue.karpenter_interruption.id
  policy    = data.aws_iam_policy_document.karpenter_interruption_queue.json
}

resource "aws_cloudwatch_event_rule" "karpenter_interruption" {
  for_each = {
    scheduled_change = {
      source      = ["aws.health"]
      detail-type = ["AWS Health Event"]
    }
    spot_interruption = {
      source      = ["aws.ec2"]
      detail-type = ["EC2 Spot Instance Interruption Warning"]
    }
    rebalance = {
      source      = ["aws.ec2"]
      detail-type = ["EC2 Instance Rebalance Recommendation"]
    }
    instance_state_change = {
      source      = ["aws.ec2"]
      detail-type = ["EC2 Instance State-change Notification"]
    }
    capacity_reservation = {
      source      = ["aws.ec2"]
      detail-type = ["EC2 Capacity Reservation Instance Interruption Warning"]
    }
  }

  # substr() giới hạn 64 ký tự (CloudWatch Events rule name limit) — cluster_name
  # dài hơn ở một số environment (vd "ecommerce-develop-dev-eks") có thể vượt nếu
  # không cắt, dù each.key đã rút gọn.
  name          = substr("${local.cluster_name}-karpenter-${each.key}", 0, 64)
  event_pattern = jsonencode(each.value)
}

resource "aws_cloudwatch_event_target" "karpenter_interruption" {
  for_each = aws_cloudwatch_event_rule.karpenter_interruption

  rule = each.value.name
  arn  = aws_sqs_queue.karpenter_interruption.arn
}
