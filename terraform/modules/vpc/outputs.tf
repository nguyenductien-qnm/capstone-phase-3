output "vpc_id" {
  description = "ID của VPC"
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "CIDR block của VPC"
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Map ID của Public Subnets"
  value       = { for k, v in aws_subnet.public : k => v.id }
}

output "private_app_subnet_ids" {
  description = "Map ID của Private Application Subnets"
  value       = { for k, v in aws_subnet.private_app : k => v.id }
}

output "private_data_subnet_ids" {
  description = "Map ID của Private Data Subnets"
  value       = { for k, v in aws_subnet.private_data : k => v.id }
}

output "private_mq_subnet_ids" {
  description = "Map ID của Private Message Queue Subnets"
  value       = { for k, v in aws_subnet.private_mq : k => v.id }
}

output "nat_gateway_ips" {
  description = "Map public IP của các NAT Gateways"
  value       = { for k, v in aws_eip.nat : k => v.public_ip }
}
