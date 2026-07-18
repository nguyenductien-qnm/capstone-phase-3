variable "project_name" {
  type        = string
  description = "Project name used for audit-detection resource naming"

  validation {
    condition     = length(trimspace(var.project_name)) >= 2
    error_message = "project_name must contain at least two non-whitespace characters."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "pipeline_health_email_endpoints" {
  type        = set(string)
  description = "Email addresses subscribed to pipeline-health notifications; audit events are not emailed"

  validation {
    condition = length(var.pipeline_health_email_endpoints) > 0 && alltrue([
      for endpoint in var.pipeline_health_email_endpoints : can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", endpoint))
    ])
    error_message = "Provide at least one valid pipeline-health email address."
  }
}

variable "slack_webhook_parameter_arn" {
  type        = string
  description = "ARN of the existing SSM Parameter Store parameter or Secrets Manager secret containing the Slack webhook"

  validation {
    condition     = can(regex("^arn:[^:]+:(ssm|secretsmanager):[^:]+:[0-9]{12}:", var.slack_webhook_parameter_arn))
    error_message = "slack_webhook_parameter_arn must be an SSM parameter ARN or Secrets Manager secret ARN."
  }
}

variable "slack_webhook_kms_key_arn" {
  type        = string
  description = "Optional customer-managed KMS key ARN used to encrypt the Slack webhook parameter"
  default     = null
  nullable    = true

  validation {
    condition     = var.slack_webhook_kms_key_arn == null || can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/", var.slack_webhook_kms_key_arn))
    error_message = "slack_webhook_kms_key_arn must be null or a KMS key ARN."
  }
}

variable "break_glass_role_arns" {
  type        = set(string)
  description = "Exact role ARNs whose AssumeRole calls must be alerted as break-glass access"
  default     = []

  validation {
    condition = alltrue([
      for arn in var.break_glass_role_arns : can(regex("^arn:[^:]+:iam::[0-9]{12}:role/.+", arn))
    ])
    error_message = "Every break_glass_role_arns value must be an IAM role ARN."
  }
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Lambda timeout in seconds"
  default     = 30

  validation {
    condition     = var.lambda_timeout_seconds >= 3 && var.lambda_timeout_seconds <= 300
    error_message = "lambda_timeout_seconds must be between 3 and 300."
  }
}

variable "lambda_memory_size_mb" {
  type        = number
  description = "Lambda memory allocation in MB"
  default     = 256

  validation {
    condition     = var.lambda_memory_size_mb >= 128 && var.lambda_memory_size_mb <= 10240
    error_message = "lambda_memory_size_mb must be between 128 and 10240."
  }
}

variable "lambda_reserved_concurrency" {
  type        = number
  description = "Reserved concurrency for the Slack delivery Lambda"
  default     = 2

  validation {
    condition     = var.lambda_reserved_concurrency >= 1
    error_message = "lambda_reserved_concurrency must be at least 1."
  }
}

variable "lambda_log_level" {
  type        = string
  description = "Application log level passed to Lambda"
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.lambda_log_level)
    error_message = "lambda_log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL."
  }
}

variable "idempotency_lease_seconds" {
  type        = number
  description = "Lease duration for an in-progress CloudTrail event"
  default     = 300

  validation {
    condition     = var.idempotency_lease_seconds >= 60 && var.idempotency_lease_seconds <= 3600
    error_message = "idempotency_lease_seconds must be between 60 and 3600."
  }
}

variable "idempotency_retention_seconds" {
  type        = number
  description = "TTL retained for completed CloudTrail event IDs"
  default     = 86400

  validation {
    condition     = var.idempotency_retention_seconds >= 3600 && var.idempotency_retention_seconds <= 604800
    error_message = "idempotency_retention_seconds must be between one hour and seven days."
  }
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch Logs retention for Lambda operational logs"
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a CloudWatch Logs supported retention value."
  }
}

variable "main_queue_retention_seconds" {
  type        = number
  description = "Retention period for unprocessed audit events in the main SQS queue"
  default     = 1209600

  validation {
    condition     = var.main_queue_retention_seconds >= 60 && var.main_queue_retention_seconds <= 1209600
    error_message = "main_queue_retention_seconds must be between 60 seconds and 14 days."
  }
}

variable "queue_visibility_timeout_seconds" {
  type        = number
  description = "SQS visibility timeout; must be at least six times the Lambda timeout"
  default     = 180

  validation {
    condition     = var.queue_visibility_timeout_seconds >= 30 && var.queue_visibility_timeout_seconds <= 43200
    error_message = "queue_visibility_timeout_seconds must be between 30 seconds and 12 hours."
  }
}

variable "max_receive_count" {
  type        = number
  description = "Number of processing attempts before SQS moves an event to the processing DLQ"
  default     = 5

  validation {
    condition     = var.max_receive_count >= 5 && var.max_receive_count <= 100
    error_message = "max_receive_count must be between 5 and 100."
  }
}

variable "eventbridge_max_event_age_seconds" {
  type        = number
  description = "Maximum age of an EventBridge delivery retry"
  default     = 86400

  validation {
    condition     = var.eventbridge_max_event_age_seconds >= 60 && var.eventbridge_max_event_age_seconds <= 86400
    error_message = "eventbridge_max_event_age_seconds must be between 60 seconds and 24 hours."
  }
}

variable "eventbridge_max_retry_attempts" {
  type        = number
  description = "Maximum EventBridge target delivery retry attempts"
  default     = 185

  validation {
    condition     = var.eventbridge_max_retry_attempts >= 0 && var.eventbridge_max_retry_attempts <= 185
    error_message = "eventbridge_max_retry_attempts must be between 0 and 185."
  }
}

variable "pipeline_health_threshold_seconds" {
  type        = number
  description = "Oldest main-queue message age that marks the Slack delivery pipeline unhealthy"
  default     = 120

  validation {
    condition     = var.pipeline_health_threshold_seconds >= 60
    error_message = "pipeline_health_threshold_seconds must be at least 60."
  }
}

variable "queue_backlog_threshold" {
  type        = number
  description = "Visible main-queue message count that marks the pipeline unhealthy"
  default     = 10

  validation {
    condition     = var.queue_backlog_threshold >= 1
    error_message = "queue_backlog_threshold must be at least 1."
  }
}

variable "tags" {
  type        = map(string)
  description = "Additional tags; mandatory ownership tags are enforced by the module"
  default     = {}
}
