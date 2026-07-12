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

output "eks_update_kubeconfig_command" {
  description = "Lệnh cấu hình kubectl sau khi đăng nhập AWS SSO"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}




