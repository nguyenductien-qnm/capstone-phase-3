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

variable "kms_key_arns" {
  type        = list(string)
  description = "ARN các KMS key (customer-managed) đã mã hoá secret ở trên. Đọc secret cần CẢ HAI quyền: secretsmanager:GetSecretValue để lấy dữ liệu VÀ kms:Decrypt để giải mã. Secret dùng KMS key mặc định của AWS (aws/secretsmanager) thì không cần liệt kê ở đây — key mặc định cho phép mọi principal trong account giải mã."
  default     = []
}
