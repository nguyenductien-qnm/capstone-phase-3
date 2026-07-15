variable "aws_region" {
  type        = string
  description = "AWS Region triển khai"
}

variable "project_name" {
  type        = string
  description = "Tên dự án sử dụng cho resource tagging"
}

variable "environment" {
  type        = string
  description = "Môi trường triển khai (dev, staging, prod)"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Môi trường phải thuộc tập [dev, staging, prod]."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block cho VPC"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR phải là một dải CIDR hợp lệ (vd: 10.0.0.0/16)."
  }
}

variable "public_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Public Subnets"
}

variable "private_app_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Private Application Subnets"
}

variable "private_data_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Private Data Subnets"
}

variable "private_mq_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Private Message Queue Subnets"
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Có bật NAT Gateway hay không"
}

variable "single_nat_gateway" {
  type        = bool
  description = "Có sử dụng single NAT Gateway hay tạo ở mỗi AZ để tiết kiệm chi phí"
}

variable "public_subnet_tags" {
  type        = map(string)
  description = "Các tags bổ sung cho Public Subnets"
  default     = {}
}

variable "private_subnet_tags" {
  type        = map(string)
  description = "Các tags bổ sung cho Private Subnets (App, Data, MQ)"
  default     = {}
}

variable "eks_cluster_version" {
  type        = string
  description = "Phiên bản Kubernetes được review cho EKS; không tự động chạy theo latest"
}

variable "eks_endpoint_public_access" {
  type        = bool
  description = "Bật public Kubernetes API endpoint cho operator ngoài VPC"
  default     = false
}

variable "eks_public_access_cidrs" {
  type        = list(string)
  description = "CIDR tin cậy được phép truy cập public Kubernetes API endpoint"
  default     = []
}

variable "eks_control_plane_log_retention_days" {
  type        = number
  description = "Retention CloudWatch cho EKS API/audit/authenticator logs"
  default     = 30
}

variable "eks_node_instance_types" {
  type        = list(string)
  description = "Các EC2 instance type cho EKS managed node group"
  default     = ["t3.medium"]
}

variable "eks_node_capacity_type" {
  type        = string
  description = "ON_DEMAND hoặc SPOT cho managed node group chính"
  default     = "ON_DEMAND"
}

variable "eks_node_disk_size_gib" {
  type        = number
  description = "Dung lượng encrypted gp3 root volume của mỗi EKS node"
  default     = 50
}

variable "eks_node_scaling" {
  description = "Scaling bounds của EKS managed node group"
  type = object({
    min_size     = number
    max_size     = number
    desired_size = number
  })
  default = {
    min_size     = 2
    max_size     = 3
    desired_size = 2
  }
}

variable "eks_ops_node_subnet_key" {
  type        = string
  description = "Private application subnet key for the single-AZ observability node group"
  default     = "app-2"
}

variable "eks_ops_node_instance_types" {
  type        = list(string)
  description = "EC2 instance types for the observability node group"
  default     = ["m6a.large"]
}

variable "eks_ops_node_disk_size_gib" {
  type        = number
  description = "Encrypted gp3 root volume size for the observability node"
  default     = 30
}

variable "eks_access_entries" {
  description = "EKS Access Entries cho SSO/operator/automation; dùng IAM role ARN, không dùng STS assumed-role ARN"
  type = map(object({
    principal_arn      = string
    access_policy_name = string
    access_scope_type  = optional(string, "cluster")
    namespaces         = optional(list(string), [])
    kubernetes_groups  = optional(list(string), [])
  }))
}

variable "db_name" {
  type        = string
  description = "Tên database khởi tạo"
}

variable "db_username" {
  type        = string
  description = "Username quản trị (admin) của Database"
}

variable "rds_engine_version" {
  type        = string
  description = "PostgreSQL engine version supported by the target AWS region"
  default     = "16.14"
}

variable "rds_instance_class" {
  type        = string
  description = "Loại Instance của Primary RDS"
}

variable "rds_allocated_storage" {
  type        = number
  description = "Dung lượng lưu trữ allocated (GB)"
}

variable "enable_read_replica" {
  type        = bool
  description = "Bật/Tắt tạo Read Replica cho PostgreSQL"
}

variable "replica_instance_class" {
  type        = string
  description = "Loại Instance của Read Replica (nếu bật)"
}

variable "enable_rds_proxy" {
  type        = bool
  description = "Bật/Tắt tạo RDS Proxy cho PostgreSQL"
}

variable "valkey_node_type" {
  type        = string
  description = "Loại Node của ElastiCache Valkey (ví dụ: cache.t4g.micro)"
}

variable "kafka_version" {
  type        = string
  description = "Phiên bản Apache Kafka của cụm MSK"
  default     = "3.9.x"
}

variable "valkey_num_cache_clusters" {
  type        = number
  description = "Số lượng node trong Valkey replication group"
}

variable "ecr_repositories" {
  type        = list(string)
  description = "Danh sách tên các repositories cần khởi tạo trên ECR"
}

variable "nlb_dns_name" {
  type        = string
  description = "Tên miền công cộng (DNS Name) của Network Load Balancer (NLB) để làm origin"
}

variable "subdomain" {
  type        = string
  description = "Tên miền phụ được trỏ vào CloudFront (ví dụ: api.yourdomain.com)"
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN của chứng chỉ ACM SSL tạo thủ công trên AWS Console"
}

variable "enable_cloudfront" {
  type        = bool
  description = "Tạo CloudFront distribution; sandbox mặc định tắt vì một số account cần AWS verification trước"
  default     = false
}

variable "rds_multi_az" {
  type        = bool
  description = "Bật/Tắt chế độ Multi-AZ cho Primary DB"
}


