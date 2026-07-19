variable "project_name" {
  description = "Project name used for tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "lambda_subnet_ids" {
	description = "List of subnet ids in which lambda functions will be placed"
	type = list(string)
}

variable "vpc_id" {
	description = "VPC id of the project"
	type = "string"
}

variable "dynamodb_table_arn" {
	description = "ARN of Dynamodb table"
	type = "string"
}

variable "dynamodb_stream_arn" {
	description = "ARN of Dynamodb Streams"
	type = "string"
}

variable "msk_secret_arn" {
	description = "ARN of MSK Secret"
	type = "string"
}

variable "msk_endpoint_secret_arn" {
	description = "ARN of MSK Endpoint Secret"
	type = "string"
}

variable "kms_key_arn" {
	description = "KMS Decrypt"
	type = "string"
}