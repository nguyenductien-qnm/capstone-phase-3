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

variable "vpc_id" {
  type        = string
  description = "ID của VPC nơi đặt ElastiCache"
}

variable "cache_subnet_ids" {
  type        = list(string)
  description = "Danh sách ID của các subnets dành cho Cache"
}

variable "app_subnet_cidr_blocks" {
  type        = list(string)
  description = "Danh sách dải CIDR của tầng Application được truy cập cache"
}

variable "node_type" {
  type        = string
  description = "Loại Instance/Node của ElastiCache (ví dụ: cache.t4g.micro)"
}

variable "num_cache_clusters" {
  type        = number
  description = "Số lượng cache nodes (clusters) trong replication group"
}

variable "eks_node_security_group_id" {
  type        = string
  description = "EKS node security group ID to allow access to Valkey"
}

# --- Mandate 20: DR Backup & Restore ---

variable "snapshot_retention_limit" {
  type        = number
  description = "Số ngày giữ snapshot tự động của Valkey. 0 = tắt snapshot (mặc định, giữ nguyên hành vi cũ). Đặt > 0 để cart có backup."
  default     = 0
}

variable "snapshot_window" {
  type        = string
  description = "Cửa sổ (UTC) ElastiCache tạo snapshot hằng ngày, dạng hh:mm-hh:mm. null = để AWS giữ cửa sổ hiện tại (không rò rỉ diff sang env chưa bật snapshot). Đặt rõ khi bật retention."
  default     = null
}
