output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded Kubernetes API certificate authority data"
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}

output "cluster_security_group_id" {
  description = "EKS-created cluster security group ID"
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  description = "EKS workload OIDC provider ARN for IRSA roles"
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_issuer_url" {
  description = "EKS workload OIDC issuer URL"
  value       = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

output "node_group_name" {
  description = "Primary managed node group name"
  value       = aws_eks_node_group.this.node_group_name
}

output "primary_autoscaling_group_name" {
  description = "Auto Scaling group backing the primary managed node group"
  value       = aws_eks_node_group.this.resources[0].autoscaling_groups[0].name
}

output "ops_node_group_name" {
  description = "Dedicated observability managed node group name"
  value       = aws_eks_node_group.ops.node_group_name
}

output "node_role_arn" {
  description = "Managed node group IAM role ARN"
  value       = aws_iam_role.node.arn
}

output "ebs_csi_role_arn" {
  description = "Pod Identity IAM role ARN for the EBS CSI controller"
  value       = aws_iam_role.ebs_csi.arn
}

output "karpenter_controller_role_arn" {
  description = "Pod Identity IAM role ARN for the Karpenter controller"
  value       = aws_iam_role.karpenter_controller.arn
}

output "karpenter_node_role_name" {
  description = "IAM role name used by Karpenter-managed EC2 nodes"
  value       = aws_iam_role.karpenter_node.name
}

output "karpenter_node_instance_profile_name" {
  description = "IAM instance profile name used by the Karpenter EC2NodeClass"
  value       = aws_iam_instance_profile.karpenter_node.name
}
