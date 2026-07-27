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

variable "create_kms_key" {
  type        = bool
  description = "Tạo KMS key nội bộ hay không. Set false khi truyền kms_key_arn từ ngoài vào (ví dụ từ module backup_protection). Phải là giá trị tĩnh để count không phụ thuộc vào known-after-apply."
  default     = true
}
