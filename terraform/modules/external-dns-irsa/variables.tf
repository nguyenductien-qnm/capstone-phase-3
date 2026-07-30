variable "project_name" {
  type        = string
  description = "Tên dự án sử dụng cho resource tagging"
}

variable "environment" {
  type        = string
  description = "Môi trường triển khai (dev, staging, prod)"
}

variable "oidc_provider_arn" {
  type        = string
  description = "ARN của OIDC provider gắn với EKS cluster (output từ module eks)"
}

variable "oidc_issuer_url" {
  type        = string
  description = "OIDC issuer URL của EKS cluster (output từ module eks)"
}

variable "hosted_zone_id" {
  type        = string
  description = "Route53 hosted zone ID mà external-dns được phép ghi record (giới hạn least-privilege)"
}

variable "service_account_namespace" {
  type        = string
  description = "Namespace của ServiceAccount external-dns"
  default     = "external-dns"
}

variable "service_account_name" {
  type        = string
  description = "Tên ServiceAccount external-dns"
  default     = "external-dns"
}
