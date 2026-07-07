variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid CIDR block (e.g. 10.0.0.0/16)."
  }
}

variable "environment" {
  description = "Environment tag (e.g. dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of [dev, staging, prod]."
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster to tag subnets"
  type        = string
}
