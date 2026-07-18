variable "name_prefix" {
  type        = string
  description = "Shared prefix for audit-detection resources"
}

variable "tags" {
  type        = map(string)
  description = "Mandatory and additional resource tags"
}

variable "lambda_function_name" {
  type        = string
  description = "Slack processor Lambda function name"
}

variable "processing_queue_name" {
  type        = string
  description = "Main audit processing queue name"
}

variable "processing_dlq_name" {
  type        = string
  description = "Processing DLQ name"
}

variable "eventbridge_delivery_dlq_name" {
  type        = string
  description = "EventBridge target-delivery DLQ name"
}

variable "pipeline_health_topic_arn" {
  type        = string
  description = "SNS topic ARN receiving pipeline-health alarms"
}

variable "eventbridge_rules" {
  type = map(object({
    name     = string
    arn      = string
    category = string
  }))
  description = "EventBridge rule metadata keyed by rule identifier"
}

variable "pipeline_health_threshold_seconds" {
  type        = number
  description = "Oldest queue-message age that marks the pipeline unhealthy"
}

variable "queue_backlog_threshold" {
  type        = number
  description = "Visible queue-message count that marks the pipeline unhealthy"
}
