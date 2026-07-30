resource "aws_vpc_endpoint" "s3" {
  count = var.enable_s3_gateway_endpoint ? 1 : 0

  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = sort(tolist(var.route_table_ids))
  policy            = var.s3_endpoint_policy

  tags = merge(
    {
      Name        = "${var.project_name}-${var.environment}-s3-gateway-endpoint"
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags
  )
}
