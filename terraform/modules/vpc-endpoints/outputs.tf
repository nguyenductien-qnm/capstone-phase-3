output "s3_gateway_endpoint_id" {
  description = "S3 gateway endpoint ID, or null when disabled"
  value       = try(aws_vpc_endpoint.s3[0].id, null)
}

output "s3_service_name" {
  description = "Regional S3 endpoint service name"
  value       = try(aws_vpc_endpoint.s3[0].service_name, null)
}

output "associated_route_table_ids" {
  description = "Private route tables associated with the S3 gateway endpoint"
  value       = var.enable_s3_gateway_endpoint ? sort(tolist(var.route_table_ids)) : []
}
