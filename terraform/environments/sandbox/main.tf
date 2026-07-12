module "vpc" {
  source = "../../modules/vpc"

  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  public_subnets       = var.public_subnets
  private_app_subnets  = var.private_app_subnets
  private_data_subnets = var.private_data_subnets
  private_mq_subnets   = var.private_mq_subnets
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  public_subnet_tags   = var.public_subnet_tags
  private_subnet_tags  = var.private_subnet_tags
}

module "eks" {
  source = "../../modules/eks"

  project_name       = var.project_name
  environment        = var.environment
  cluster_version    = var.eks_cluster_version
  private_subnet_ids = values(module.vpc.private_app_subnet_ids)

  endpoint_public_access = var.eks_endpoint_public_access
  public_access_cidrs    = var.eks_public_access_cidrs

  control_plane_log_retention_days = var.eks_control_plane_log_retention_days

  node_instance_types = var.eks_node_instance_types
  node_capacity_type  = var.eks_node_capacity_type
  node_disk_size_gib  = var.eks_node_disk_size_gib
  node_scaling        = var.eks_node_scaling

  access_entries = var.eks_access_entries
}

module "rds" {
  source = "../../modules/rds"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  database_subnet_ids    = values(module.vpc.private_data_subnet_ids)
  app_subnet_cidr_blocks = [for s in var.private_app_subnets : s.cidr_block]

  db_name                = var.db_name
  db_username            = var.db_username
  instance_class         = var.rds_instance_class
  allocated_storage      = var.rds_allocated_storage
  enable_read_replica    = var.enable_read_replica
  replica_instance_class = var.replica_instance_class
  enable_rds_proxy       = var.enable_rds_proxy
  multi_az               = var.rds_multi_az
}

module "elasticache" {
  source = "../../modules/elasticache"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  cache_subnet_ids       = values(module.vpc.private_data_subnet_ids)
  app_subnet_cidr_blocks = [for s in var.private_app_subnets : s.cidr_block]

  node_type          = var.valkey_node_type
  num_cache_clusters = var.valkey_num_cache_clusters
}

module "ecr" {
  source = "../../modules/ecr"

  project_name     = var.project_name
  environment      = var.environment
  ecr_repositories = var.ecr_repositories
}

module "cloudfront" {
  source = "../../modules/cloudfront"

  project_name        = var.project_name
  environment         = var.environment
  origin_domain_name  = var.nlb_dns_name
  acm_certificate_arn = var.acm_certificate_arn
  aliases             = [var.subdomain]
}
