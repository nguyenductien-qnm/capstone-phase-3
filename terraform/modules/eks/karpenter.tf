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

  # MANDATE-13: cho phep controller poll SQS interruption queue duoi (chi khi
  # enable_karpenter_interruption_queue=true o environment nay).
  dynamic "statement" {
    for_each = var.enable_karpenter_interruption_queue ? [1] : []
    content {
      sid    = "InterruptionQueue"
      effect = "Allow"
      actions = [
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
        "sqs:ReceiveMessage",
      ]
      resources = [aws_sqs_queue.karpenter_interruption[0].arn]
    }
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

resource "aws_ec2_tag" "karpenter_cluster_security_group_discovery" {
  resource_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  key         = "karpenter.sh/discovery"
  value       = local.cluster_name
}

# MANDATE-13: AWS chi bao truoc 2 phut khi thu hoi 1 spot instance (Spot
# Interruption Warning). Khong co gi chu dong doc canh bao nay thi Kubernetes
# chi phat hien node mat qua kubelet heartbeat timeout (~40s) + pod-eviction-
# timeout (~5 phut) -- lau hon nhieu so voi cua so 2 phut that, request tren
# node coi nhu rot. EventBridge day 3 loai canh bao lien quan vao SQS; Karpenter
# (settings.interruptionQueue) poll queue nay de chu dong cordon+drain truoc.
#
# Gate boi enable_karpenter_interruption_queue: shared module nay dung chung
# boi develop + sandbox, resource nay chi can cho environment dang lam
# MANDATE-13 (develop) — khong duoc tao moi trong plan cua environment khac
# (environment-isolation-execution-guide §Case T3).
resource "aws_sqs_queue" "karpenter_interruption" {
  count                     = var.enable_karpenter_interruption_queue ? 1 : 0
  name                      = "${local.cluster_name}-karpenter-interruption"
  message_retention_seconds = 300 # su kien chi con y nghia trong vai phut
  sqs_managed_sse_enabled   = true

  tags = {
    Name = "${local.cluster_name}-karpenter-interruption"
  }
}

data "aws_iam_policy_document" "karpenter_interruption_queue" {
  count = var.enable_karpenter_interruption_queue ? 1 : 0

  statement {
    sid     = "AllowEventBridgeRules"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    resources = [aws_sqs_queue.karpenter_interruption[0].arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.karpenter_interruption[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sqs_queue_policy" "karpenter_interruption" {
  count     = var.enable_karpenter_interruption_queue ? 1 : 0
  queue_url = aws_sqs_queue.karpenter_interruption[0].id
  policy    = data.aws_iam_policy_document.karpenter_interruption_queue[0].json
}

resource "aws_cloudwatch_event_rule" "karpenter_interruption" {
  count       = var.enable_karpenter_interruption_queue ? 1 : 0
  name        = "${local.cluster_name}-karpenter-interruption"
  description = "Karpenter spot interruption: Spot Interruption Warning + Rebalance Recommendation + Instance State-change"
  event_pattern = jsonencode({
    source = ["aws.ec2"]
    detail-type = [
      "EC2 Spot Interruption Warning",
      "EC2 Instance Rebalance Recommendation",
      "EC2 Instance State-change Notification",
    ]
  })

  tags = {
    Name = "${local.cluster_name}-karpenter-interruption"
  }
}

resource "aws_cloudwatch_event_target" "karpenter_interruption" {
  count     = var.enable_karpenter_interruption_queue ? 1 : 0
  rule      = aws_cloudwatch_event_rule.karpenter_interruption[0].name
  target_id = "karpenter-interruption-queue"
  arn       = aws_sqs_queue.karpenter_interruption[0].arn

  depends_on = [aws_sqs_queue_policy.karpenter_interruption]
}
