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
  validation {
    condition     = alltrue([for k, v in var.public_subnets : can(cidrhost(v.cidr_block, 0))])
    error_message = "Tất cả Public Subnet CIDR phải hợp lệ."
  }
}

variable "private_app_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Private Application Subnets"
  validation {
    condition     = alltrue([for k, v in var.private_app_subnets : can(cidrhost(v.cidr_block, 0))])
    error_message = "Tất cả Private App Subnet CIDR phải hợp lệ."
  }
}

variable "private_data_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Private Data Subnets"
  validation {
    condition     = alltrue([for k, v in var.private_data_subnets : can(cidrhost(v.cidr_block, 0))])
    error_message = "Tất cả Private Data Subnet CIDR phải hợp lệ."
  }
}

variable "private_mq_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Cấu hình Private Message Queue Subnets"
  validation {
    condition     = alltrue([for k, v in var.private_mq_subnets : can(cidrhost(v.cidr_block, 0))])
    error_message = "Tất cả Private MQ Subnet CIDR phải hợp lệ."
  }
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

