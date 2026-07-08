variable "aws_region" {
  description = "AWS Region to deploy the infrastructure"
  type        = string
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "AWS Region must be a valid format (e.g. us-east-1, ap-southeast-1)."
  }
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of [dev, staging, prod]."
  }
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
}

variable "instance_types" {
  description = "EC2 instance types for the EKS node group"
  type        = list(string)
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid CIDR block (e.g. 10.0.0.0/16)."
  }
}

variable "eks_admin_user_arns" {
  description = "List of IAM User ARNs to grant admin access to the EKS cluster"
  type        = list(string)
  default     = []
}
