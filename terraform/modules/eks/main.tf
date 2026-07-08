data "aws_caller_identity" "current" {}

locals {
  # Lọc bỏ AWS User hiện tại đang chạy Terraform để tránh lỗi 409 (đã được tự động gán quyền Admin qua enable_cluster_creator_admin_permissions)
  filtered_admin_user_arns = [
    for arn in var.admin_user_arns : arn if arn != data.aws_caller_identity.current.arn
  ]
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

  access_entries = { for arn in local.filtered_admin_user_arns : basename(arn) => {
    principal_arn = arn
    policy_associations = {
      admin = {
        policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
        access_scope = {
          type = "cluster"
        }
      }
    }
  }}

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
