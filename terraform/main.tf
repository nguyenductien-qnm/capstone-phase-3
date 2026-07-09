terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "terraform-state-phase-3-bucket"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "TechX-Corp"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "AIO-03"
    }
  }
}

# 1. Gọi Module khởi tạo mạng VPC
module "vpc" {
  source       = "./modules/vpc"
  environment  = var.environment
  cluster_name = var.cluster_name
  vpc_cidr     = var.vpc_cidr
}

# 2. Gọi Module tạo Registry ECR lưu Docker Images
module "ecr" {
  source          = "./modules/ecr"
  repository_name = var.repository_name
  environment     = var.environment
}

# 3. Gọi Module tạo cụm EKS Cluster & Worker Nodes
module "eks" {
  source       = "./modules/eks"
  cluster_name = var.cluster_name
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.private_subnets
  environment  = var.environment

  instance_types       = var.instance_types
  desired_size         = var.node_desired_size
  min_size             = var.node_min_size
  max_size             = var.node_max_size
  admin_principal_arns = distinct(concat(var.eks_admin_principal_arns, var.eks_admin_user_arns))
  view_principal_arns  = var.eks_view_principal_arns
}
