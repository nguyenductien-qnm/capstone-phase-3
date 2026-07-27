variable "project_name" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. develop)"
}

variable "kms_key_arn" {
  type        = string
  description = "ARN KMS key dùng mã hoá Backup Vault. Null = module tự tạo key riêng. Truyền key của backup_protection để vault dùng key có guardrail chống xoá/disable."
  default     = null
}


