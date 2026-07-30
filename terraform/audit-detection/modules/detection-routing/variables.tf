variable "name_prefix" {
  type        = string
  description = "Shared prefix for audit-detection resources"
}

variable "tags" {
  type        = map(string)
  description = "Mandatory and additional resource tags"
}

variable "pipeline_health_email_endpoints" {
  type        = set(string)
  description = "Email endpoints subscribed to pipeline-health notifications"
}

variable "break_glass_role_arns" {
  type        = set(string)
  description = "Exact break-glass role ARNs detected by the AssumeRole rule"
}

variable "main_queue_retention_seconds" {
  type        = number
  description = "Main audit-event queue retention"
}

variable "queue_visibility_timeout_seconds" {
  type        = number
  description = "Main audit-event queue visibility timeout"
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Processor timeout used to validate queue visibility"
}

variable "max_receive_count" {
  type        = number
  description = "Processing attempts before moving a message to the processing DLQ"
}

variable "eventbridge_max_event_age_seconds" {
  type        = number
  description = "Maximum EventBridge target-delivery event age"
}

variable "eventbridge_max_retry_attempts" {
  type        = number
  description = "Maximum EventBridge target-delivery retries"
}
