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

variable "image_mutability" {
  type        = string
  description = "Cấu hình ghi đè tag hình ảnh (MUTABLE hoặc IMMUTABLE)"
  # Deployable artifacts must never be overwritten by a later build. Callers
  # may still pass MUTABLE only for an explicitly documented non-deployable
  # repository; application environments use the immutable default.
  default     = "IMMUTABLE"
  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_mutability)
    error_message = "Cấu hình ghi đè phải là MUTABLE hoặc IMMUTABLE."
  }
}
