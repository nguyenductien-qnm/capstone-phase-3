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

variable "origin_domain_name" {
  type        = string
  description = "Tên miền (DNS Name) của Network Load Balancer (NLB) làm Origin"
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN của chứng chỉ ACM SSL cấp cho tên miền tùy chỉnh"
  default     = null
}

variable "aliases" {
  type        = list(string)
  description = "Danh sách tên miền tùy chỉnh (aliases) cho CloudFront"
  default     = []
}

