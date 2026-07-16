variable "project_name" {
  type        = string
  description = "Project name used as the IAM role prefix."
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
}

variable "aws_region" {
  type        = string
  description = "AWS region where Bedrock runtime is invoked."
}

variable "oidc_provider_arn" {
  type        = string
  description = "EKS OIDC provider ARN used by IRSA trust."
}

variable "oidc_issuer_url" {
  type        = string
  description = "EKS OIDC issuer URL used by IRSA trust conditions."
}

variable "service_account_namespace" {
  type        = string
  description = "Kubernetes namespace of the ServiceAccount allowed to assume this role."
}

variable "service_account_name" {
  type        = string
  description = "Kubernetes ServiceAccount name allowed to assume this role."
}

variable "foundation_model_ids" {
  type        = list(string)
  description = "Bedrock foundation model IDs the AI workloads may invoke."
}
