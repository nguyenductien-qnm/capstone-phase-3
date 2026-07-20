resource "aws_dynamodb_table" "idempotency" {
  name         = "${var.name_prefix}-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"

  attribute {
    name = "event_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-idempotency"
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "/aws/lambda/${local.lambda_function_name}"
  })
}

resource "aws_lambda_function" "slack_alert" {
  function_name = local.lambda_function_name
  description   = "Deliver queued AWS audit events to the security Slack channel"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  architectures = ["arm64"]

  # Keep the deployment artifact in the repository because the reviewed plan
  # and apply run in separate GitHub Actions jobs with separate filesystems.
  filename         = var.lambda_package_file
  source_code_hash = filebase64sha256(var.lambda_package_file)

  memory_size = var.lambda_memory_size_mb
  timeout     = var.lambda_timeout_seconds

  environment {
    variables = {
      LOG_LEVEL                     = var.lambda_log_level
      IDEMPOTENCY_LEASE_SECONDS     = tostring(var.idempotency_lease_seconds)
      IDEMPOTENCY_RETENTION_SECONDS = tostring(var.idempotency_retention_seconds)
      IDEMPOTENCY_TABLE_NAME        = aws_dynamodb_table.idempotency.name
      SLACK_WEBHOOK_PARAMETER_ARN   = aws_secretsmanager_secret.slack_webhook.arn
      SLACK_WEBHOOK_PROVIDER        = "secretsmanager"
    }
  }

  tags = merge(var.tags, {
    Name = local.lambda_function_name
  })

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda,
    aws_secretsmanager_secret_version.slack_webhook,
  ]
}

resource "aws_lambda_event_source_mapping" "processing_queue" {
  event_source_arn = var.processing_queue_arn
  function_name    = aws_lambda_function.slack_alert.arn
  enabled          = true

  batch_size                         = 1
  maximum_batching_window_in_seconds = 0

  scaling_config {
    maximum_concurrency = var.lambda_maximum_concurrency
  }
}
