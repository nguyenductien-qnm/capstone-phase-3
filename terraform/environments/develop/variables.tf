variable "aws_region" {
  type        = string
  description = "AWS Region triển khai"
  default     = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "AWS account ID dedicated to the Develop environment"
  default     = "458580846647"

  validation {
    condition     = var.aws_account_id == "458580846647"
    error_message = "Develop Terraform may run only in AWS account 458580846647."
  }
}

variable "project_name" {
  type        = string
  description = "Tên dự án sử dụng cho resource tagging"
  default     = "ecommerce-develop"

  validation {
    condition     = var.project_name == "ecommerce-develop"
    error_message = "Develop must use project_name=ecommerce-develop to avoid Product-like name collisions."
  }
}

variable "environment" {
  type        = string
  description = "Môi trường triển khai (dev, staging, prod)"
  default     = "dev"
  validation {
    condition     = var.environment == "dev"
    error_message = "The Develop root must use environment=dev."
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

variable "private_app_subnet_tags" {
  type        = map(string)
  description = "Các tags bổ sung chỉ cho Private Application Subnets"
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
  default     = ["t3.medium"]
}

variable "eks_ops_node_disk_size_gib" {
  type        = number
  description = "Encrypted gp3 root volume size for the observability node"
  default     = 30
}

variable "github_terraform_role_name" {
  type        = string
  description = "IAM role used by GitHub Actions to manage Terraform and bootstrap Kubernetes"
  default     = "GitHubTerraformDevelopRole"
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
  default     = "17.10"
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
  default     = true
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


variable "ecr_pull_principal_arns" {
  type        = list(string)
  description = "Cross-account IAM role ARNs allowed to pull from the shared ECR repositories"
  default     = []
}

variable "route53_zone_id" {
  type        = string
  description = "Route53 hosted zone ID của subdomain — external-dns được cấp quyền ghi record ĐÚNG zone này (least-privilege)"
  default     = ""
}

variable "subdomain" {
  type        = string
  description = "Tên miền phụ được trỏ vào CloudFront (ví dụ: api.yourdomain.com)"
  default     = "develop.invalid"
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN của chứng chỉ ACM SSL tạo thủ công trên AWS Console"
  default     = ""
}

variable "enable_cloudfront" {
  type        = bool
  description = "Tạo CloudFront distribution; sandbox mặc định tắt vì một số account cần AWS verification trước"
  default     = false
}

variable "rds_multi_az" {
  type        = bool
  description = "Bật/Tắt chế độ Multi-AZ cho Primary DB"
  default     = true
}
variable "eks_enabled_cluster_log_types" {
  type        = list(string)
  description = "EKS control-plane log types; api, audit and authenticator are mandatory for auditability"
  default     = ["api", "audit", "authenticator"]

  validation {
    condition     = alltrue([for required in ["api", "audit", "authenticator"] : contains(var.eks_enabled_cluster_log_types, required)])
    error_message = "eks_enabled_cluster_log_types must include api, audit and authenticator."
  }
}

variable "eks_enable_control_plane_log_kms" {
  type        = bool
  description = "Use a customer-managed rotating KMS key for the EKS control-plane log group"
  default     = true
}

variable "cloudtrail_enable_kms_encryption" {
  type        = bool
  default     = true
  description = "Use a customer-managed rotating KMS key for CloudTrail storage"
}

variable "cloudtrail_enable_cloudwatch_logs" {
  type        = bool
  default     = true
  description = "Stream CloudTrail events to CloudWatch Logs for operational queries"
}

variable "cloudtrail_cloudwatch_log_retention_days" {
  type        = number
  default     = 90
  description = "CloudWatch retention for CloudTrail events"
}

variable "cloudtrail_s3_retention_days" {
  type        = number
  default     = 2555
  description = "Days before expiring archived CloudTrail objects"
}

variable "cloudtrail_s3_transition_days" {
  type        = number
  default     = 90
  description = "Days before transitioning CloudTrail objects"
}

variable "cloudtrail_s3_transition_storage_class" {
  type        = string
  default     = "GLACIER_IR"
  description = "Storage class for older CloudTrail objects"
}

variable "cloudtrail_enable_object_lock" {
  type        = bool
  default     = false
  description = "Enable GOVERNANCE Object Lock only for a compatible/new bucket; may require migration"
}

variable "cloudtrail_object_lock_retention_days" {
  type        = number
  default     = 30
  description = "GOVERNANCE retention when Object Lock is explicitly enabled"
}

variable "audit_administrator_principals" {
  type        = list(string)
  default     = []
  description = "IAM principal ARNs exempted from the operator tamper deny policy"
}

variable "audit_break_glass_principals" {
  type        = list(string)
  default     = []
  description = "Break-glass IAM principal ARNs exempted from the operator tamper deny policy"
}

variable "audit_operator_role_names" {
  type        = list(string)
  default     = []
  description = "IAM role names to attach the tamper-deny policy; leave empty for Identity Center manual attachment"
}

variable "rds_enable_rotation" {
  type        = bool
  description = "Bật/Tắt xoay vòng secret tự động cho RDS"
  default     = true
}

variable "rds_rotation_lambda_arn" {
  type        = string
  description = "ARN của Lambda function xoay vòng secret RDS"
  default     = ""
}

variable "rds_rotation_rules_automatically_after_days" {
  type        = number
  description = "Số ngày tự động xoay vòng secret RDS"
  default     = 30
}
