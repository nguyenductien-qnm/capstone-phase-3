variable "project_name" {
  type        = string
  description = "Project name used for endpoint tags"

  validation {
    condition     = length(trimspace(var.project_name)) > 0
    error_message = "project_name must not be empty."
  }
}

variable "environment" {
  type        = string
  description = "Environment name used for endpoint tags"

  validation {
    condition     = length(trimspace(var.environment)) > 0
    error_message = "environment must not be empty."
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region used to build the regional S3 service name"

  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be a valid AWS region name."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC where endpoints are created"

  validation {
    condition     = can(regex("^vpc-[0-9a-f]+$", var.vpc_id))
    error_message = "vpc_id must be a valid VPC ID."
  }
}

variable "route_table_ids" {
  type        = set(string)
  description = "Private workload route tables associated with the S3 gateway endpoint"

  validation {
    condition = length(var.route_table_ids) > 0 && alltrue([
      for route_table_id in var.route_table_ids : can(regex("^rtb-[0-9a-f]+$", route_table_id))
    ])
    error_message = "route_table_ids must contain at least one valid route table ID."
  }
}

variable "enable_s3_gateway_endpoint" {
  type        = bool
  description = "Create the no-fixed-hourly-cost S3 gateway endpoint"
  default     = true
}

variable "s3_endpoint_policy" {
  type        = string
  description = "Optional JSON endpoint policy. Null preserves normal IAM and bucket-policy authorization."
  default     = null

  validation {
    condition     = var.s3_endpoint_policy == null || can(jsondecode(var.s3_endpoint_policy))
    error_message = "s3_endpoint_policy must be null or valid JSON."
  }
}

variable "tags" {
  type        = map(string)
  description = "Additional endpoint tags"
  default     = {}
}
