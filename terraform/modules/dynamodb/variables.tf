variable "project_name" {
  description = "Project name used for tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "table_name" {
  description = "DynamoDB table name"
  type        = string
}

variable "hash_key" {
  description = "Partition key name"
  type        = string
}

variable "hash_key_type" {
  description = "Partition key type"
  type        = string
  default     = "S"
}

variable "range_key" {
  description = "Optional sort key name"
  type        = string
  default     = null
}

variable "range_key_type" {
  description = "Sort key type"
  type        = string
  default     = "S"
}

variable "billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "read_capacity" {
  description = "Provisioned read capacity when billing_mode is PROVISIONED"
  type        = number
  default     = 5
}

variable "write_capacity" {
  description = "Provisioned write capacity when billing_mode is PROVISIONED"
  type        = number
  default     = 5
}

variable "stream_enabled" {
  description = "Enable DynamoDB Streams"
  type        = bool
  default     = true
}

variable "stream_view_type" {
  description = "View type for DynamoDB Streams"
  type        = string
  default     = "NEW_AND_OLD_IMAGES"
}

variable "ttl_enabled" {
  description = "Enable TTL on the table"
  type        = bool
  default     = true
}

variable "ttl_attribute_name" {
  description = "Attribute name used for TTL"
  type        = string
  default     = "ttl"
}

variable "global_secondary_index_name" {
  description = "Named of Global Secondary Index"
  type = string
}

variable "global_secondary_index_projection_type" {
  description = "Projection Type of Global Secondary Index"
  type = string 
  default = "ALL"
}