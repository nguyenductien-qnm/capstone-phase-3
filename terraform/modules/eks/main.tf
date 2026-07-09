data "aws_caller_identity" "current" {}

locals {
  # Lọc bỏ AWS User hiện tại đang chạy Terraform để tránh lỗi 409 (đã được tự động gán quyền Admin qua enable_cluster_creator_admin_permissions)
  admin_principal_arns = distinct(concat(var.admin_principal_arns, var.admin_user_arns))
  view_principal_arns  = distinct(var.view_principal_arns)

  filtered_admin_principal_arns = [
    for arn in local.admin_principal_arns : arn if arn != data.aws_caller_identity.current.arn
  ]

  filtered_view_principal_arns = [
    for arn in local.view_principal_arns : arn
    if arn != data.aws_caller_identity.current.arn && !contains(local.admin_principal_arns, arn)
  ]

  admin_access_entries = {
    for index, arn in local.filtered_admin_principal_arns : "admin-${index}" => {
      principal_arn = arn
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  view_access_entries = {
    for index, arn in local.filtered_view_principal_arns : "view-${index}" => {
      principal_arn = arn
      policy_associations = {
        view = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.36"

  cluster_endpoint_public_access = true

  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids

  enable_cluster_creator_admin_permissions = true

  access_entries = merge(local.admin_access_entries, local.view_access_entries)

  eks_managed_node_groups = {
    techx_nodes = {
      name = "techx-node-group-${var.environment}"

      min_size     = var.min_size
      max_size     = var.max_size
      desired_size = var.desired_size

      instance_types = var.instance_types
      capacity_type  = "ON_DEMAND" # Có thể đổi sang SPOT để tiết kiệm chi phí

      iam_role_additional_policies = {
        AmazonEC2ContainerRegistryReadOnly = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
      }
    }
  }
}
