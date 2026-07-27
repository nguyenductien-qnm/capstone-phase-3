variable "project_name" {
  type        = string
  description = "Project name"
  default     = "ecommerce"
}

variable "environment" {
  type        = string
  description = "Environment name (develop, sandbox, prod)"
}

variable "operator_role_names" {
  type        = list(string)
  description = "List of IAM operator role names to attach explicit backup deletion deny policy to"
  default     = []
}
