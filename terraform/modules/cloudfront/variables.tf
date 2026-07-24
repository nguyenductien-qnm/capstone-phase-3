variable "project_name" {
  type        = string
  description = "Tên dự án sử dụng cho resource tagging"
}

variable "environment" {
  type        = string
  description = "Môi trường triển khai (dev, staging, prod)"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Môi trường phải thuộc tập [dev, staging, prod]."
  }
}

variable "origin_domain_name" {
  type        = string
  description = "Tên miền (DNS Name) của Network Load Balancer (NLB) làm Origin"
}

variable "acm_certificate_arn" {
  type        = string
  description = "ARN chứng chỉ ACM cho tên miền tùy chỉnh. BẮT BUỘC — xem validation."

  # Không còn default = null: chứng chỉ mặc định của CloudFront KHÔNG cho đặt
  # minimum_protocol_version, AWS ép về TLSv1 (bản 2006, đã lỗi thời). Ai dựng môi
  # trường mới mà quên truyền ARN sẽ vô tình chạy TLSv1 — Checkov CKV_AWS_174 bắt
  # đúng bẫy này. Bắt buộc truyền ARM để mọi distribution đều đi nhánh TLSv1.2_2021.
  validation {
    condition     = can(regex("^arn:aws:acm:us-east-1:[0-9]{12}:certificate/", var.acm_certificate_arn))
    error_message = "acm_certificate_arn phải là ARN chứng chỉ ACM ở us-east-1 (CloudFront chỉ nhận cert từ region này). Chứng chỉ mặc định của CloudFront bị khoá ở TLSv1 nên không dùng được."
  }
}

variable "aliases" {
  type        = list(string)
  description = "Danh sách tên miền tùy chỉnh (aliases) cho CloudFront"
  default     = []
}

