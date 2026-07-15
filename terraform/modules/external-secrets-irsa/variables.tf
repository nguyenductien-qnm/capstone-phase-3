variable "project_name" {
  type        = string
  description = "Tên project (prefix đặt tên resource)"
}

variable "environment" {
  type        = string
  description = "Môi trường (dev/staging/prod)"
}

variable "oidc_provider_arn" {
  type        = string
  description = "ARN của OIDC provider EKS (module.eks.oidc_provider_arn) cho IRSA trust"
}

variable "oidc_issuer_url" {
  type        = string
  description = "Issuer URL của OIDC provider EKS (https://oidc.eks...) — dùng dựng điều kiện sub/aud"
}

variable "service_account_namespace" {
  type        = string
  description = "Namespace của ServiceAccount External Secrets Operator"
  default     = "external-secrets"
}

variable "service_account_name" {
  type        = string
  description = "Tên ServiceAccount ESO được annotate role ARN"
  default     = "external-secrets"
}

variable "secret_arns" {
  type        = list(string)
  description = "Danh sách ARN Secrets Manager mà ESO được phép đọc (RDS/Valkey/MSK endpoint+cred)"
}
