variable "project_name" {
  type        = string
  description = "Tên dự án sử dụng cho resource tagging"
}

variable "environment" {
  type        = string
  description = "Môi trường triển khai (dev, staging, prod)"
}

variable "vpc_id" {
  type        = string
  description = "ID của VPC"
}

variable "mq_subnet_ids" {
  type        = list(string)
  description = "Danh sách ID các subnets để chạy MSK brokers"
}

variable "eks_security_group_id" {
  type        = string
  description = "Security Group ID của cụm EKS để whitelist kết nối"
}

variable "broker_instance_type" {
  type        = string
  description = "EC2 instance class của MSK brokers"
  default     = "kafka.t3.small"
}

variable "ebs_volume_size" {
  type        = number
  description = "Dung lượng ổ gp3 cho mỗi broker node (GB)"
  default     = 10
}

variable "kafka_version" {
  type        = string
  description = "Phiên bản Apache Kafka của cụm MSK"
  default     = "3.9.x"
}
