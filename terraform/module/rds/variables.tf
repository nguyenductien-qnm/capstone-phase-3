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
  description = "ID của VPC nơi đặt RDS"
}

variable "database_subnet_ids" {
  type        = list(string)
  description = "Danh sách ID của các subnets dành cho Database"
}

variable "app_subnet_cidr_blocks" {
  type        = list(string)
  description = "Danh sách dải CIDR của tầng Application được truy cập database"
}

variable "db_name" {
  type        = string
  description = "Tên database khởi tạo"
}

variable "db_username" {
  type        = string
  description = "Username quản trị (admin) của Database"
  validation {
    condition     = can(regex("^[a-zA-Z_][a-zA-Z0-9_]*$", var.db_username))
    error_message = "Username của DB phải bắt đầu bằng chữ cái hoặc dấu gạch dưới và chỉ chứa ký tự chữ, số, gạch dưới."
  }
}

variable "instance_class" {
  type        = string
  description = "Loại Instance của Primary RDS"
}

variable "allocated_storage" {
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

variable "multi_az" {
  type        = bool
  description = "Bật/Tắt chế độ Multi-AZ cho Primary DB"
  default     = false
}

