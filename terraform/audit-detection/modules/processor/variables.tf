variable "name_prefix" {
  type        = string
  description = "Shared prefix for audit-detection resources"
}

variable "tags" {
  type        = map(string)
  description = "Mandatory and additional resource tags"
}

variable "lambda_source_file" {
  type        = string
  description = "Absolute path to the Lambda handler source file"
}

variable "processing_queue_arn" {
  type        = string
  description = "ARN of the SQS processing queue consumed by Lambda"
}

variable "queue_kms_key_arn" {
  type        = string
  description = "KMS key ARN used to encrypt SQS messages"
}

variable "slack_webhook_parameter_arn" {
  type        = string
  description = "SSM parameter or Secrets Manager secret ARN containing the Slack webhook"
}

variable "slack_webhook_kms_key_arn" {
  type        = string
  description = "Optional customer-managed key ARN for the webhook secret"
  default     = null
  nullable    = true
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Lambda timeout"
}

variable "lambda_memory_size_mb" {
  type        = number
  description = "Lambda memory allocation"
}

variable "lambda_maximum_concurrency" {
  type        = number
  description = "Maximum SQS event-source concurrency"
}

variable "lambda_log_level" {
  type        = string
  description = "Lambda application log level"
}

variable "log_retention_days" {
  type        = number
  description = "Lambda operational-log retention"
}

variable "idempotency_lease_seconds" {
  type        = number
  description = "In-progress event lease duration"
}

variable "idempotency_retention_seconds" {
  type        = number
  description = "Completed eventID retention duration"
}
