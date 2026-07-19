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

variable "ecr_repositories" {
  type        = list(string)
  description = "Danh sách tên các repositories cần khởi tạo trên ECR"
}

variable "pull_principal_arns" {
  type        = list(string)
  description = "IAM role ARN (cross-account) được phép PULL image — vd node role của cluster develop. Rỗng = không tạo repository policy."
  default     = []
}

variable "image_mutability" {
  type        = string
  description = "Cấu hình ghi đè tag hình ảnh (MUTABLE hoặc IMMUTABLE)"
  default     = "MUTABLE"
  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_mutability)
    error_message = "Cấu hình ghi đè phải là MUTABLE hoặc IMMUTABLE."
  }
}
