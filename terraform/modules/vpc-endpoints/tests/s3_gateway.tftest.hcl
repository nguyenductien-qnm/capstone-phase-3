mock_provider "aws" {
}

run "s3_gateway_plan" {
  command = plan

  variables {
    project_name    = "ecommerce"
    environment     = "dev"
    aws_region      = "us-east-1"
    vpc_id          = "vpc-0123456789abcdef0"
    route_table_ids = ["rtb-0123456789abcdef0"]
  }

  assert {
    condition     = length(aws_vpc_endpoint.s3) == 1
    error_message = "Exactly one S3 gateway endpoint must be planned."
  }

  assert {
    condition     = aws_vpc_endpoint.s3[0].vpc_endpoint_type == "Gateway"
    error_message = "S3 must use a gateway endpoint, not a fixed-hourly interface endpoint."
  }

  assert {
    condition     = aws_vpc_endpoint.s3[0].service_name == "com.amazonaws.us-east-1.s3"
    error_message = "The endpoint must use the regional S3 service name."
  }

  assert {
    condition     = toset(aws_vpc_endpoint.s3[0].route_table_ids) == toset(["rtb-0123456789abcdef0"])
    error_message = "Only the supplied private egress route tables may be associated."
  }
}
