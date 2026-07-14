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

variable "account_id" {
  type        = string
  description = "AWS Account ID"
}

variable "budget_limit" {
  type        = number
  description = "Giới hạn chi phí hàng tháng (USD) khi không dùng định kỳ tùy chỉnh"
}

variable "budget_time_unit" {
  type        = string
  description = "Thời gian chu kỳ của budget (WEEKLY, MONTHLY, QUARTERLY, ANNUAL)"
  default     = "MONTHLY"
  validation {
    condition     = contains(["WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL"], var.budget_time_unit)
    error_message = "budget_time_unit phải là WEEKLY, MONTHLY, QUARTERLY hoặc ANNUAL."
  }
}

variable "budget_periods" {
  type = list(object({
    name       = string
    start_date = string
    end_date   = string
    amount     = number
  }))
  description = "Danh sách các khoảng budget có ngày bắt đầu/ kết thúc cụ thể và số tiền budget"
  default     = []
}

variable "alert_emails" {
  type = object({
    threshold_80 = string
    threshold_95 = string
  })
  description = "Email để gửi cảnh báo ở 80% và 95%"
}

variable "eks_cluster_name" {
  type        = string
  description = "Tên EKS cluster để scale down"
}

variable "eks_cluster_arn" {
  type        = string
  description = "ARN của EKS cluster"
}

variable "rds_instance_identifiers" {
  type        = list(string)
  description = "Danh sách RDS instance identifiers để stop"
  default     = []
}

variable "elasticache_cluster_ids" {
  type        = list(string)
  description = "Danh sách ElastiCache cluster IDs để reduce"
  default     = []
}

variable "ec2_instance_tags" {
  type = object({
    key   = string
    value = string
  })
  description = "Tag để filter EC2 instances cần stop"
  default = {
    key   = "AutoStop"
    value = "true"
  }
}

variable "auto_scaling_group_names" {
  type        = list(string)
  description = "Danh sách Auto Scaling Group names để set desired capacity"
  default     = []
}

variable "lambda_timeout" {
  type        = number
  description = "Lambda execution timeout (seconds)"
  default     = 300
}

variable "lambda_memory" {
  type        = number
  description = "Lambda memory allocation (MB)"
  default     = 512
}

variable "cloudwatch_log_retention_days" {
  type        = number
  description = "CloudWatch Logs retention (days)"
  default     = 14
}
