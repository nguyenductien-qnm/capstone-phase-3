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

variable "snapshot_retention_limit" {
  type        = number
  description = "So ngay giu ban snapshot ElastiCache Valkey (0 = tat snapshot)"
  default     = 0
}

variable "snapshot_window" {
  type        = string
  description = "Khung gio UTC thuc hien snapshot tu dong hang ngay"
  default     = null
}
