output "vpc_id" {
  description = "ID của VPC được tạo"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block của VPC"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "Danh sách ID của các Public Subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_app_subnet_ids" {
  description = "Danh sách ID của các Private Application Subnets"
  value       = module.vpc.private_app_subnet_ids
}

output "private_data_subnet_ids" {
  description = "Danh sách ID của các Private Data Subnets"
  value       = module.vpc.private_data_subnet_ids
}

output "private_mq_subnet_ids" {
  description = "Danh sách ID của các Private Message Queue Subnets"
  value       = module.vpc.private_mq_subnet_ids
}

output "nat_gateway_ips" {
  description = "IP công cộng của các NAT Gateways"
  value       = module.vpc.nat_gateway_ips
}

output "db_primary_endpoint" {
  description = "Connection endpoint cho Primary Database (host:port)"
  value       = module.rds.db_primary_endpoint
}

output "db_replica_endpoint" {
  description = "Connection endpoint cho Read Replica Database (host:port) nếu bật"
  value       = module.rds.db_replica_endpoint
}

output "db_proxy_endpoint" {
  description = "Endpoint để ứng dụng kết nối qua RDS Proxy"
  value       = module.rds.db_proxy_endpoint
}

output "db_username" {
  description = "Username quản trị database"
  value       = module.rds.db_username
}

output "db_password" {
  description = "Mật khẩu quản trị database (sensitive)"
  value       = module.rds.db_password
  sensitive   = true
}

output "valkey_primary_endpoint" {
  description = "Endpoint address của node Primary Valkey (để ghi/đọc)"
  value       = module.elasticache.primary_endpoint_address
}

output "valkey_reader_endpoint" {
  description = "Endpoint address của node Reader Valkey (để đọc tải cao)"
  value       = module.elasticache.reader_endpoint_address
}

output "valkey_port" {
  description = "Cổng kết nối của Valkey cluster"
  value       = module.elasticache.port
}

output "ecr_repository_urls" {
  description = "Bản đồ chứa URL đẩy ảnh của các ECR repositories"
  value       = module.ecr.repository_urls
}

output "cloudfront_domain_name" {
  description = "Tên miền công cộng của CloudFront Distribution trỏ tới EKS"
  value       = try(module.cloudfront[0].cloudfront_domain_name, null)
}

output "custom_domain_url" {
  description = "Đường dẫn URL của ứng dụng sử dụng tên miền tùy chỉnh"
  value       = var.enable_cloudfront ? "https://${var.subdomain}" : null
}

output "eks_cluster_name" {
  description = "Tên EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_oidc_provider_arn" {
  description = "OIDC provider cho IRSA workload roles"
  value       = module.eks.oidc_provider_arn
}

output "eks_node_group_name" {
  description = "Tên EKS managed node group chính"
  value       = module.eks.node_group_name
}

output "eks_ops_node_group_name" {
  description = "Tên EKS managed node group cho observability"
  value       = module.eks.ops_node_group_name
}

output "eks_ebs_csi_role_arn" {
  description = "Pod Identity IAM role cho EBS CSI controller"
  value       = module.eks.ebs_csi_role_arn
}

output "eks_karpenter_controller_role_arn" {
  description = "Pod Identity IAM role cho Karpenter controller"
  value       = module.eks.karpenter_controller_role_arn
}

output "eks_karpenter_node_role_name" {
  description = "IAM role name cho Karpenter-managed EC2 nodes"
  value       = module.eks.karpenter_node_role_name
}

output "eks_karpenter_node_instance_profile_name" {
  description = "Instance profile name cho Karpenter EC2NodeClass"
  value       = module.eks.karpenter_node_instance_profile_name
}

output "eks_update_kubeconfig_command" {
  description = "Lệnh cấu hình kubectl sau khi đăng nhập AWS SSO"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "msk_bootstrap_brokers_plaintext" {
  description = "Connection string cho Plaintext (port 9092) của MSK"
  value       = module.msk.bootstrap_brokers_plaintext
}

output "msk_bootstrap_brokers_tls" {
  description = "Connection string cho TLS (port 9094) của MSK"
  value       = module.msk.bootstrap_brokers_tls
}

output "msk_bootstrap_brokers_sasl_scram" {
  description = "Connection string cho SASL/SCRAM (port 9096) của MSK"
  value       = module.msk.bootstrap_brokers_sasl_scram
}

output "msk_security_group_id" {
  description = "Security Group ID của MSK cluster"
  value       = module.msk.msk_security_group_id
}

output "msk_secret_arn" {
  description = "ARN của Secret Manager lưu msk credentials"
  value       = module.msk.msk_secret_arn
}






output "external_secrets_irsa_role_arn" {
  description = "ARN IAM role cho External Secrets Operator (annotate SA external-secrets/external-secrets)"
  value       = module.external_secrets_irsa.role_arn
}

output "external_dns_irsa_role_arn" {
  description = "ARN IAM role cho external-dns (annotate SA external-dns/external-dns)"
  value       = var.enable_cloudfront ? module.external_dns_irsa[0].role_arn : null
}

output "cloudfront_origin_hostname" {
  description = "Tên cố định CloudFront dùng làm origin — external-dns tạo record này trỏ về ALB của Ingress frontend-proxy"
  value       = local.origin_hostname
}

output "eks_control_plane_log_group_name" {
  description = "CloudWatch log group containing EKS API/audit/authenticator events"
  value       = module.eks.control_plane_log_group_name
}

output "eks_enabled_cluster_log_types" {
  description = "Enabled EKS control-plane log types"
  value       = module.eks.enabled_cluster_log_types
}

output "eks_control_plane_log_retention_days" {
  description = "EKS control-plane log retention"
  value       = module.eks.control_plane_log_retention_days
}

output "cloudtrail_name" {
  description = "CloudTrail trail name"
  value       = module.cloudtrail.trail_name
}

output "cloudtrail_arn" {
  description = "CloudTrail trail ARN"
  value       = module.cloudtrail.trail_arn
}

output "cloudtrail_s3_bucket_name" {
  description = "S3 bucket containing CloudTrail evidence"
  value       = module.cloudtrail.s3_bucket_name
}

output "cloudtrail_cloudwatch_log_group_name" {
  description = "CloudWatch log group used for CloudTrail queries"
  value       = module.cloudtrail.cloudwatch_log_group_name
}

output "cloudtrail_kms_key_arn" {
  description = "KMS key protecting CloudTrail evidence"
  value       = module.cloudtrail.kms_key_arn
}

output "audit_tamper_protection_policy_arn" {
  description = "Managed policy to attach to routine operator permission sets"
  value       = module.cloudtrail.tamper_protection_policy_arn
}

output "audit_detection_lambda_function_name" {
  description = "Slack audit-alert Lambda name when MANDATE-11 detection is enabled"
  value       = try(module.audit_detection[0].lambda_function_name, null)
}

output "audit_detection_processing_queue_arn" {
  description = "Durable audit processing queue ARN when MANDATE-11 detection is enabled"
  value       = try(module.audit_detection[0].processing_queue_arn, null)
}

output "audit_detection_pipeline_health_topic_arn" {
  description = "SNS pipeline-health topic ARN when MANDATE-11 detection is enabled"
  value       = try(module.audit_detection[0].pipeline_health_topic_arn, null)
}
