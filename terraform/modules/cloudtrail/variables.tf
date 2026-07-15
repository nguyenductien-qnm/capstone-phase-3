variable "project_name" {
  type        = string
  description = "Tên dự án sử dụng cho resource tagging"
}

variable "environment" {
  type        = string
  description = "Môi trường triển khai (dev, staging, prod)"
}
