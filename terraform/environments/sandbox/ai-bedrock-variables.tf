variable "ai_bedrock_service_account_namespace" {
  type        = string
  description = "Namespace cua ServiceAccount duoc gan IRSA role goi Bedrock runtime."
  default     = "techx-tf1"
}

variable "ai_bedrock_service_account_name" {
  type        = string
  description = "Ten ServiceAccount duoc gan IRSA role goi Bedrock runtime."
  default     = "techx-corp"
}

variable "ai_bedrock_foundation_model_ids" {
  type        = list(string)
  description = "Danh sach Bedrock foundation model ID cho AI workloads."
  default = [
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
    "amazon.nova-pro-v1:0",
  ]
}
