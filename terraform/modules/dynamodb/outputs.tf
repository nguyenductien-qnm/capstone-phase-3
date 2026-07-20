output "dynamodb_table_name" {
  description = "DynamoDB table name with Streams Enabled"
  value = aws_dynamodb_table.checkout_orders.name
}

output "dynamodb_table_arn" {
  description = "ARN of DynamoDB table"
  value = aws_dynamodb_table.checkout_orders.arn
}

output "dynamodb_stream_arn" {
	description = "ARN of DynamoDB Streams"
	value = aws_dynamodb_table.checkout_orders.stream_arn
}

output "dynamodb_gsi_reconcile_due_arn" {
  description = "ARN of Global Secondary Index gsi_reconcile_due"
  value = "${aws_dynamodb_table.checkout_orders.arn}/index/${var.global_secondary_index_name}"
}