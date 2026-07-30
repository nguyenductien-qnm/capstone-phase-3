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
  description = "Namespace cài Kyverno"
  default     = "kyverno"
}

variable "service_account_names" {
  type        = list(string)
  description = <<-EOT
    ServiceAccount của Kyverno được phép assume role này. Mặc định 2 controller cần
    đọc ECR: admission-controller (verifyImages lúc admission) và reports-controller
    (sinh PolicyReport ở chế độ Audit/background scan). Tên SA do chart kyverno đặt
    theo fullname — đổi fullnameOverride/nameOverride thì phải sửa danh sách này,
    nếu không trust policy khớp sai và pod rơi về node role (vô dụng: node prod đặt
    IMDSv2 hop limit = 1 nên pod không mượn được credential qua IMDS).
  EOT
  default = [
    "kyverno-admission-controller",
    "kyverno-reports-controller",
  ]
}

variable "ecr_repository_arns" {
  type        = list(string)
  description = <<-EOT
    ARN các ECR repository mà Kyverno được đọc để verify chữ ký. CHỈ repo image chính:
    policy admission chỉ verify chữ ký `.sig` nằm cùng repo với image. KHÔNG cấp repo
    attest (`*-attest`) — admission không verify attestation promoted-develop (gate
    promote đã enforce ở CI), quyền thừa cắt đi cho gọn IAM.
  EOT
}
