locals {
  name_prefix = substr("${var.project_name}-${var.environment}-audit", 0, 32)
  common_tags = merge(var.tags, {
    Component   = "audit-detection"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = "CDO-05"
    Project     = var.project_name
  })
}

module "detection_routing" {
  source = "./modules/detection-routing"

  name_prefix                       = local.name_prefix
  tags                              = local.common_tags
  pipeline_health_email_endpoints   = var.pipeline_health_email_endpoints
  break_glass_role_arns             = var.break_glass_role_arns
  main_queue_retention_seconds      = var.main_queue_retention_seconds
  queue_visibility_timeout_seconds  = var.queue_visibility_timeout_seconds
  lambda_timeout_seconds            = var.lambda_timeout_seconds
  max_receive_count                 = var.max_receive_count
  eventbridge_max_event_age_seconds = var.eventbridge_max_event_age_seconds
  eventbridge_max_retry_attempts    = var.eventbridge_max_retry_attempts
}

module "processor" {
  source = "./modules/processor"

  name_prefix                   = local.name_prefix
  tags                          = local.common_tags
  lambda_source_file            = "${path.module}/lambda/handler.py"
  processing_queue_arn          = module.detection_routing.processing_queue_arn
  queue_kms_key_arn             = module.detection_routing.queue_kms_key_arn
  slack_webhook_url             = var.slack_webhook_url
  slack_webhook_secret_version  = var.slack_webhook_secret_version
  slack_webhook_kms_key_arn     = var.slack_webhook_kms_key_arn
  lambda_timeout_seconds        = var.lambda_timeout_seconds
  lambda_memory_size_mb         = var.lambda_memory_size_mb
  lambda_maximum_concurrency    = var.lambda_maximum_concurrency
  lambda_log_level              = var.lambda_log_level
  log_retention_days            = var.log_retention_days
  idempotency_lease_seconds     = var.idempotency_lease_seconds
  idempotency_retention_seconds = var.idempotency_retention_seconds
}

module "monitoring" {
  source = "./modules/monitoring"

  name_prefix                       = local.name_prefix
  tags                              = local.common_tags
  lambda_function_name              = module.processor.lambda_function_name
  processing_queue_name             = module.detection_routing.processing_queue_name
  processing_dlq_name               = module.detection_routing.processing_dlq_name
  eventbridge_delivery_dlq_name     = module.detection_routing.eventbridge_delivery_dlq_name
  pipeline_health_topic_arn         = module.detection_routing.pipeline_health_topic_arn
  eventbridge_rules                 = module.detection_routing.eventbridge_rules
  pipeline_health_threshold_seconds = var.pipeline_health_threshold_seconds
  queue_backlog_threshold           = var.queue_backlog_threshold

  depends_on = [module.detection_routing]
}
