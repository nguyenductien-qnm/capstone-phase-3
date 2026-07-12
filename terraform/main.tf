module "vpc" {
  source = "./module/vpc"

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

module "rds" {
  source = "./module/rds"

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
  source = "./module/elasticache"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  cache_subnet_ids       = values(module.vpc.private_data_subnet_ids)
  app_subnet_cidr_blocks = [for s in var.private_app_subnets : s.cidr_block]

  node_type          = var.valkey_node_type
  num_cache_clusters = var.valkey_num_cache_clusters
}

module "ecr" {
  source = "./module/ecr"

  project_name     = var.project_name
  environment      = var.environment
  ecr_repositories = var.ecr_repositories
}

module "cloudfront" {
  source = "./module/cloudfront"

  project_name        = var.project_name
  environment         = var.environment
  origin_domain_name  = var.nlb_dns_name
  acm_certificate_arn = var.acm_certificate_arn
  aliases             = [var.subdomain]
}

