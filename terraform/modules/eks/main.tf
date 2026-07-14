data "aws_partition" "current" {}

locals {
  cluster_name = "${var.project_name}-${var.environment}-eks"
  core_addons = var.enable_core_addons ? toset([
    "coredns",
    "kube-proxy",
    "vpc-cni",
    "eks-pod-identity-agent",
  ]) : toset([])
}

resource "aws_cloudwatch_log_group" "control_plane" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.control_plane_log_retention_days

  tags = {
    Name = "${local.cluster_name}-control-plane"
  }
}

resource "aws_iam_role" "cluster" {
  name = "${local.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${local.cluster_name}-cluster-role"
  }
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  enabled_cluster_log_types = var.enabled_cluster_log_types

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = var.endpoint_public_access
    public_access_cidrs     = var.endpoint_public_access ? var.public_access_cidrs : null
  }

  depends_on = [
    aws_cloudwatch_log_group.control_plane,
    aws_iam_role_policy_attachment.cluster,
  ]

  lifecycle {
    precondition {
      condition     = !var.endpoint_public_access || length(var.public_access_cidrs) > 0
      error_message = "public_access_cidrs must be set when endpoint_public_access is enabled."
    }

    precondition {
      condition = (
        !var.endpoint_public_access ||
        var.environment == "dev" ||
        alltrue([
          for cidr in var.public_access_cidrs :
          !contains(["0.0.0.0/0", "::/0"], cidr)
        ])
      )
      error_message = "World-open EKS API CIDRs are allowed only in the dev environment."
    }
  }

  tags = {
    Name = local.cluster_name
  }
}

# Cluster OIDC provider for IRSA. This is unrelated to the GitHub Actions OIDC
# provider: IRSA maps Kubernetes service accounts to workload IAM roles.
data "tls_certificate" "cluster_oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster_oidc.certificates[0].sha1_fingerprint]

  tags = {
    Name = "${local.cluster_name}-irsa"
  }
}

resource "aws_iam_role" "node" {
  name = "${local.cluster_name}-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${local.cluster_name}-node-role"
  }
}

# Keep the node role limited to node bootstrap, CNI and image pulls. Application,
# telemetry and autoscaler permissions belong to dedicated IRSA roles.
resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryPullOnly",
  ])

  role       = aws_iam_role.node.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.value}"
}

resource "aws_launch_template" "node" {
  name_prefix            = "${local.cluster_name}-node-"
  update_default_version = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      encrypted             = true
      volume_size           = var.node_disk_size_gib
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.cluster_name}-node"
    }
  }

  tags = {
    Name = "${local.cluster_name}-node-template"
  }
}

resource "aws_eks_node_group" "this" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-primary"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.node_instance_types
  capacity_type   = var.node_capacity_type

  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }

  scaling_config {
    min_size     = var.node_scaling.min_size
    max_size     = var.node_scaling.max_size
    desired_size = var.node_scaling.desired_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = var.node_labels

  dynamic "taint" {
    for_each = var.node_taints
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }

  depends_on = [aws_iam_role_policy_attachment.node]

  # MANDATE-02: Cluster Autoscaler LÀ chủ sở hữu desired_size lúc runtime. Bỏ qua drift để
  # terraform apply không "giật" số node CA đang giữ ngược lại. min/max vẫn do terraform quản.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  tags = {
    Name = "${local.cluster_name}-primary"
  }
}

resource "aws_launch_template" "ops" {
  name_prefix            = "${local.cluster_name}-ops-"
  update_default_version = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      encrypted             = true
      volume_size           = var.ops_node_disk_size_gib
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.cluster_name}-ops"
    }
  }

  tags = {
    Name = "${local.cluster_name}-ops-template"
  }
}

resource "aws_eks_node_group" "ops" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-ops"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = [var.ops_node_subnet_id]
  instance_types  = var.ops_node_instance_types
  capacity_type   = "ON_DEMAND"

  launch_template {
    id      = aws_launch_template.ops.id
    version = aws_launch_template.ops.latest_version
  }

  scaling_config {
    min_size     = 1
    max_size     = 1
    desired_size = 1
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    "workload-tier" = "observability"
  }

  taint {
    key    = "dedicated"
    value  = "observability"
    effect = "NO_SCHEDULE"
  }

  depends_on = [aws_iam_role_policy_attachment.node]

  tags = {
    Name = "${local.cluster_name}-ops"
  }
}

data "aws_eks_addon_version" "core" {
  for_each = local.core_addons

  addon_name         = each.value
  kubernetes_version = aws_eks_cluster.this.version
  most_recent        = true
}

resource "aws_eks_addon" "core" {
  for_each = local.core_addons

  cluster_name  = aws_eks_cluster.this.name
  addon_name    = each.value
  addon_version = data.aws_eks_addon_version.core[each.key].version

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "PRESERVE"

  depends_on = [aws_eks_node_group.this, aws_eks_node_group.ops]

  tags = {
    Name = "${local.cluster_name}-${each.value}"
  }
}

# Access Entries are the only human/automation path into the Kubernetes API.
# For AWS IAM Identity Center, principal_arn must be the IAM role ARN under
# AWSReservedSSO_..., never an STS assumed-role session ARN.
resource "aws_eks_access_entry" "this" {
  for_each = var.access_entries

  cluster_name      = aws_eks_cluster.this.name
  principal_arn     = each.value.principal_arn
  type              = "STANDARD"
  kubernetes_groups = each.value.kubernetes_groups

  tags = {
    Name = "${local.cluster_name}-${each.key}"
  }
}

resource "aws_eks_access_policy_association" "this" {
  for_each = var.access_entries

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value.principal_arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/${each.value.access_policy_name}"

  access_scope {
    type       = each.value.access_scope_type
    namespaces = each.value.access_scope_type == "namespace" ? each.value.namespaces : null
  }

  depends_on = [aws_eks_access_entry.this]
}
