locals {
  lambda_function_name = substr("${var.name_prefix}-slack-alert", 0, 64)
}
