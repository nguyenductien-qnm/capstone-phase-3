data "aws_availability_zones" "available" {}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "techx-vpc-${var.environment}"
  cidr = var.vpc_cidr

  # Chọn 3 AZ đầu tiên của region
  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  private_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 1), # 10.0.1.0/24
    cidrsubnet(var.vpc_cidr, 8, 2), # 10.0.2.0/24
    cidrsubnet(var.vpc_cidr, 8, 3)  # 10.0.3.0/24
  ]
  public_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 101), # 10.0.101.0/24
    cidrsubnet(var.vpc_cidr, 8, 102), # 10.0.102.0/24
    cidrsubnet(var.vpc_cidr, 8, 103)  # 10.0.103.0/24
  ]

  enable_nat_gateway = true
  single_nat_gateway = true # Tiết kiệm chi phí: 1 NAT Gateway dùng chung

  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = "1"
  }


}
