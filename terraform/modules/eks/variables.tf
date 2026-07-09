variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the cluster will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for worker nodes (private subnets recommended)"
  type        = list(string)
}

variable "instance_types" {
  description = "List of EC2 instance types for the worker nodes"
  type        = list(string)
}

variable "desired_size" {
  description = "Desired number of worker nodes"
  type        = number
}

variable "min_size" {
  description = "Minimum number of worker nodes"
  type        = number
}

variable "max_size" {
  description = "Maximum number of worker nodes"
  type        = number
}

variable "environment" {
  description = "Environment name"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of [dev, staging, prod]."
  }
}

variable "admin_principal_arns" {
  description = "List of IAM principal ARNs, including IAM Identity Center/SSO role ARNs, to grant admin access to the EKS cluster"
  type        = list(string)
  default     = []
}

variable "admin_user_arns" {
  description = "Deprecated. Use admin_principal_arns instead."
  type        = list(string)
  default     = []
}

variable "view_principal_arns" {
  description = "List of IAM principal ARNs, including IAM Identity Center/SSO role ARNs, to grant view-only access to the EKS cluster"
  type        = list(string)
  default     = []
}
