variable "aws_region" {
  type        = string
  description = "AWS Region for the Develop bootstrap resources"
  default     = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "Dedicated AWS account for Develop"
  default     = "458580846647"

  validation {
    condition     = var.aws_account_id == "458580846647"
    error_message = "Develop bootstrap may run only in AWS account 458580846647."
  }
}

variable "github_repository" {
  type        = string
  description = "GitHub owner/repository allowed to assume the Terraform role"
  default     = "nguyenductien-qnm/capstone-phase-3"

  validation {
    condition     = var.github_repository == "nguyenductien-qnm/capstone-phase-3"
    error_message = "The Develop role is restricted to nguyenductien-qnm/capstone-phase-3."
  }
}

variable "github_environment" {
  type        = string
  description = "GitHub Environment whose OIDC subject may assume the role"
  default     = "develop"

  validation {
    condition     = var.github_environment == "develop"
    error_message = "The Develop role is restricted to the GitHub Environment named develop."
  }
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket for Develop Terraform state"
  default     = "capstone-phase-3-terraform-state-458580846647"
}
