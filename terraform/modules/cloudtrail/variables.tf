variable "project_name" {
  type        = string
  description = "Project name used for resource naming"
}
variable "environment" {
  type        = string
  description = "Deployment environment"
}
variable "enable_kms_encryption" {
  type        = bool
  default     = true
  description = "Encrypt S3 and CloudWatch audit logs with a customer-managed rotating KMS key"
}
variable "enable_cloudwatch_logs" {
  type        = bool
  default     = true
  description = "Stream CloudTrail to CloudWatch Logs for near-real-time queries"
}
variable "cloudwatch_log_retention_days" {
  type        = number
  default     = 90
  description = "CloudWatch Logs retention for CloudTrail"
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.cloudwatch_log_retention_days)
    error_message = "Use a CloudWatch Logs supported retention value."
  }
}
variable "s3_retention_days" {
  type        = number
  default     = 2555
  description = "Days to retain current and noncurrent CloudTrail objects"
  validation {
    condition     = var.s3_retention_days >= 365
    error_message = "CloudTrail evidence must be retained for at least 365 days."
  }
}
variable "s3_transition_days" {
  type        = number
  default     = 90
  description = "Days before moving CloudTrail objects to a lower-cost storage class"
  validation {
    condition     = var.s3_transition_days >= 30 && var.s3_transition_days < var.s3_retention_days
    error_message = "Transition must be at least 30 days and earlier than expiration."
  }
}
variable "s3_transition_storage_class" {
  type        = string
  default     = "GLACIER_IR"
  description = "S3 lifecycle transition storage class"
  validation {
    condition     = contains(["STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING", "GLACIER_IR", "GLACIER", "DEEP_ARCHIVE"], var.s3_transition_storage_class)
    error_message = "Unsupported lifecycle transition storage class."
  }
}
variable "enable_object_lock" {
  type        = bool
  default     = false
  description = "Enable GOVERNANCE Object Lock only on a compatible/new bucket; enabling can require replacement"
}
variable "object_lock_retention_days" {
  type        = number
  default     = 30
  description = "Default GOVERNANCE Object Lock retention"
  validation {
    condition     = var.object_lock_retention_days >= 1
    error_message = "Object Lock retention must be at least one day."
  }
}
variable "audit_administrator_principals" {
  type        = list(string)
  default     = []
  description = "Audit administrator IAM principal ARN patterns exempt from the operator deny"
}
variable "break_glass_principals" {
  type        = list(string)
  default     = []
  description = "Break-glass IAM principal ARN patterns exempt from the operator deny"
}
variable "operator_role_names" {
  type        = list(string)
  default     = []
  description = "IAM role names to attach the tamper-deny policy; keep empty for manual Identity Center attachment"
}
