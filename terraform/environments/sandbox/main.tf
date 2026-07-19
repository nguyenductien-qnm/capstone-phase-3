data "aws_iam_role" "github_terraform" {
  name = var.github_terraform_role_name
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  github_terraform_access_entry = {
    github_terraform = {
      principal_arn      = data.aws_iam_role.github_terraform.arn
      access_policy_name = "AmazonEKSClusterAdminPolicy"
      access_scope_type  = "cluster"
      namespaces         = []
      kubernetes_groups  = []
    }
  }

  # Tên CỐ ĐỊNH làm CloudFront origin. ALB (do Ingress frontend-proxy sinh) phục vụ
  # tên này; external-dns tự tạo record trỏ về ALB. Terraform biết giá trị ngay lúc
  # plan -> apply 1 lần, không cần dò ALB runtime, không cần toggle/commit lần 2.
  # PHẢI khớp ingress host trong platform/charts/application/values.yaml.
  # Dùng "origin-" (1 cấp con) để khớp cert wildcard *.nguyenductien.cloud.
  origin_hostname = "origin-${var.subdomain}"
}

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
  private_app_subnet_tags = merge(
    var.private_app_subnet_tags,
    {
      "karpenter.sh/discovery" = "${var.project_name}-${var.environment}-eks"
    }
  )
}

module "eks" {
  source = "../../modules/eks"

  project_name       = var.project_name
  environment        = var.environment
  cluster_version    = var.eks_cluster_version
  private_subnet_ids = values(module.vpc.private_app_subnet_ids)

  endpoint_public_access = var.eks_endpoint_public_access
  public_access_cidrs    = var.eks_public_access_cidrs

  enabled_cluster_log_types        = var.eks_enabled_cluster_log_types
  control_plane_log_retention_days = var.eks_control_plane_log_retention_days
  enable_control_plane_log_kms     = var.eks_enable_control_plane_log_kms

  node_instance_types = var.eks_node_instance_types
  node_capacity_type  = var.eks_node_capacity_type
  node_disk_size_gib  = var.eks_node_disk_size_gib
  node_scaling        = var.eks_node_scaling

  ops_node_subnet_id      = module.vpc.private_app_subnet_ids[var.eks_ops_node_subnet_key]
  ops_node_instance_types = var.eks_ops_node_instance_types
  ops_node_disk_size_gib  = var.eks_ops_node_disk_size_gib

  access_entries = merge(var.eks_access_entries, local.github_terraform_access_entry)
}

module "rds" {
  source = "../../modules/rds"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  database_subnet_ids    = values(module.vpc.private_data_subnet_ids)
  app_subnet_cidr_blocks = [for s in var.private_app_subnets : s.cidr_block]

  db_name                    = var.db_name
  db_username                = var.db_username
  engine_version             = var.rds_engine_version
  instance_class             = var.rds_instance_class
  allocated_storage          = var.rds_allocated_storage
  enable_read_replica        = var.enable_read_replica
  replica_instance_class     = var.replica_instance_class
  enable_rds_proxy           = var.enable_rds_proxy
  multi_az                   = var.rds_multi_az
  eks_node_security_group_id = module.eks.cluster_security_group_id
}

module "elasticache" {
  source = "../../modules/elasticache"

  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  cache_subnet_ids       = values(module.vpc.private_data_subnet_ids)
  app_subnet_cidr_blocks = [for s in var.private_app_subnets : s.cidr_block]

  node_type                  = var.valkey_node_type
  num_cache_clusters         = var.valkey_num_cache_clusters
  eks_node_security_group_id = module.eks.cluster_security_group_id
}

module "ecr" {
  source = "../../modules/ecr"

  project_name     = var.project_name
  environment      = var.environment
  ecr_repositories = var.ecr_repositories
}

# IRSA cho external-dns: quyền ghi record trong ĐÚNG hosted zone của subdomain.
module "external_dns_irsa" {
  source = "../../modules/external-dns-irsa"
  count  = var.enable_cloudfront ? 1 : 0

  project_name      = var.project_name
  environment       = var.environment
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_issuer_url   = module.eks.oidc_issuer_url
  hosted_zone_id    = var.route53_zone_id
}

# CloudFront lấy nội dung từ ALB qua tên cố định origin-<subdomain>, không phải DNS
# ngẫu nhiên của ALB. Record do external-dns tự tạo khi Ingress frontend-proxy lên.
# ALB bị thay -> external-dns trỏ lại; origin không đổi, CloudFront không phải sửa.
#
# Lần apply đầu: record chưa tồn tại -> origin lỗi cho tới khi external-dns tạo xong
# (thường <1 phút sau khi ALB ready). Eventual consistency, không blocking.
module "cloudfront" {
  source = "../../modules/cloudfront"
  count  = var.enable_cloudfront ? 1 : 0

  project_name        = var.project_name
  environment         = var.environment
  origin_domain_name  = local.origin_hostname
  acm_certificate_arn = var.acm_certificate_arn
  aliases             = [var.subdomain]
}

# Cửa vào cho người dùng: <subdomain> -> CloudFront. Thiếu record này thì tên miền
# không phân giải được và request không bao giờ tới CloudFront -- aliases ở module
# chỉ dạy CloudFront CHẤP NHẬN Host header, nó không tạo DNS.
# external-dns không tạo hộ: nó chỉ quản host khai trong Ingress (origin-<subdomain>).
resource "aws_route53_record" "cloudfront_alias" {
  count = var.enable_cloudfront ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.subdomain
  type    = "A"

  alias {
    name                   = module.cloudfront[0].cloudfront_domain_name
    zone_id                = module.cloudfront[0].cloudfront_hosted_zone_id
    evaluate_target_health = false
  }
}

module "msk" {
  source = "../../modules/msk"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  mq_subnet_ids         = values(module.vpc.private_mq_subnet_ids)
  eks_security_group_id = module.eks.cluster_security_group_id
  kafka_version         = var.kafka_version
}

module "cloudtrail" {
  source = "../../modules/cloudtrail"

  project_name = var.project_name
  environment  = var.environment

  enable_kms_encryption          = var.cloudtrail_enable_kms_encryption
  enable_cloudwatch_logs         = var.cloudtrail_enable_cloudwatch_logs
  cloudwatch_log_retention_days  = var.cloudtrail_cloudwatch_log_retention_days
  s3_retention_days              = var.cloudtrail_s3_retention_days
  s3_transition_days             = var.cloudtrail_s3_transition_days
  s3_transition_storage_class    = var.cloudtrail_s3_transition_storage_class
  enable_object_lock             = var.cloudtrail_enable_object_lock
  object_lock_retention_days     = var.cloudtrail_object_lock_retention_days
  audit_administrator_principals = var.audit_administrator_principals
  break_glass_principals         = var.audit_break_glass_principals
  operator_role_names            = var.audit_operator_role_names
}

# IRSA role cho External Secrets Operator đọc endpoint/credential từ Secrets Manager
# (RDS/Valkey/MSK) và đồng bộ vào cluster. Least-privilege: chỉ đúng các secret ARN.
module "external_secrets_irsa" {
  source = "../../modules/external-secrets-irsa"

  project_name      = var.project_name
  environment       = var.environment
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_issuer_url   = module.eks.oidc_issuer_url

  secret_arns = [
    module.rds.db_secret_arn,
    module.rds.db_endpoint_secret_arn,
    module.elasticache.secret_arn,
    module.msk.msk_secret_arn,
    module.msk.msk_endpoint_secret_arn,
    "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-bedrock-config-*"
  ]

  # Secret MSK mã hoá bằng KMS key riêng của module msk -> ESO cần kms:Decrypt trên
  # key này, nếu không sẽ lỗi "AccessDeniedException: Access to KMS is not allowed".
  # RDS/Valkey dùng key mặc định aws/secretsmanager nên không cần liệt kê.
  kms_key_arns = [
    module.msk.kms_key_arn,
  ]
}