data "aws_partition" "current" {}

locals {
  cost_guard_name = "${var.project_name}-${var.environment}-cost-guard"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Module      = "CostGuardAutomation"
  }
}

# SNS Topics cho Budget Alarms
resource "aws_sns_topic" "budget_alarms_80" {
  name              = "${local.cost_guard_name}-budget-alarms-80"
  kms_master_key_id = "alias/aws/sns"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-topic-80"
    }
  )
}

resource "aws_sns_topic" "budget_alarms_95" {
  name              = "${local.cost_guard_name}-budget-alarms-95"
  kms_master_key_id = "alias/aws/sns"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-topic-95"
    }
  )
}

resource "aws_sns_topic_subscription" "budget_alarms_80_email" {
  topic_arn = aws_sns_topic.budget_alarms_80.arn
  protocol  = "email"
  endpoint  = var.alert_emails.threshold_80
}

resource "aws_sns_topic_subscription" "budget_alarms_95_email" {
  topic_arn = aws_sns_topic.budget_alarms_95.arn
  protocol  = "email"
  endpoint  = var.alert_emails.threshold_95
}

# IAM Role cho Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${local.cost_guard_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

# Inline policy cho Lambda: CloudWatch Logs
resource "aws_iam_role_policy" "lambda_logs_policy" {
  name = "${local.cost_guard_name}-logs-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "arn:${data.aws_partition.current.partition}:logs:*:${var.account_id}:log-group:/aws/lambda/${local.cost_guard_name}*"
    }]
  })
}

# Inline policy cho Lambda: EKS
resource "aws_iam_role_policy" "lambda_eks_policy" {
  name = "${local.cost_guard_name}-eks-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
          "eks:UpdateNodegroupConfig"
        ]
        Resource = var.eks_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "autoscaling:SetDesiredCapacity",
          "autoscaling:DescribeAutoScalingGroups"
        ]
        Resource = "arn:${data.aws_partition.current.partition}:autoscaling:*:${var.account_id}:autoScalingGroup:*:autoScalingGroupName/*"
      }
    ]
  })
}

# Inline policy cho Lambda: RDS
resource "aws_iam_role_policy" "lambda_rds_policy" {
  count = length(var.rds_instance_identifiers) > 0 ? 1 : 0
  name  = "${local.cost_guard_name}-rds-policy"
  role  = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "rds:StopDBInstance",
        "rds:DescribeDBInstances"
      ]
      Resource = "arn:${data.aws_partition.current.partition}:rds:*:${var.account_id}:db:*"
    }]
  })
}

# Inline policy cho Lambda: ElastiCache
resource "aws_iam_role_policy" "lambda_elasticache_policy" {
  count = length(var.elasticache_cluster_ids) > 0 ? 1 : 0
  name  = "${local.cost_guard_name}-elasticache-policy"
  role  = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "elasticache:ModifyReplicationGroup",
        "elasticache:DescribeReplicationGroups",
        "elasticache:DescribeCacheClusters"
      ]
      Resource = "arn:${data.aws_partition.current.partition}:elasticache:*:${var.account_id}:*"
    }]
  })
}

# Inline policy cho Lambda: EC2
resource "aws_iam_role_policy" "lambda_ec2_policy" {
  name = "${local.cost_guard_name}-ec2-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:StopInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeTags"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:ec2:*:${var.account_id}:instance/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Log Group cho Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.cost_guard_name}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-logs"
    }
  )
}

# Archive Lambda function code
data "archive_file" "lambda_code" {
  type        = "zip"
  source_file = "${path.module}/index.py"
  output_path = "${path.module}/lambda_function.zip"
}

# Lambda function
resource "aws_lambda_function" "cost_guard" {
  filename         = data.archive_file.lambda_code.output_path
  source_code_hash = data.archive_file.lambda_code.output_base64sha256
  function_name    = local.cost_guard_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "index.handler"
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory

  environment {
    variables = {
      EKS_CLUSTER_NAME         = var.eks_cluster_name
      RDS_INSTANCE_IDENTIFIERS = jsonencode(var.rds_instance_identifiers)
      ELASTICACHE_CLUSTER_IDS  = jsonencode(var.elasticache_cluster_ids)
      EC2_INSTANCE_TAG_KEY     = var.ec2_instance_tags.key
      EC2_INSTANCE_TAG_VALUE   = var.ec2_instance_tags.value
      AUTO_SCALING_GROUP_NAMES = jsonencode(var.auto_scaling_group_names)
      ALERT_EMAIL_80           = var.alert_emails.threshold_80
      ALERT_EMAIL_95           = var.alert_emails.threshold_95
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy.lambda_logs_policy,
    aws_iam_role_policy.lambda_eks_policy
  ]

  tags = merge(
    local.common_tags,
    {
      Name = local.cost_guard_name
    }
  )
}

# SNS -> Lambda Permissions
resource "aws_lambda_permission" "sns_invoke_80" {
  statement_id  = "AllowExecutionFromSNS80"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_guard.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.budget_alarms_80.arn
}

resource "aws_lambda_permission" "sns_invoke_95" {
  statement_id  = "AllowExecutionFromSNS95"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_guard.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.budget_alarms_95.arn
}

# Lambda -> SNS Subscriptions
resource "aws_sns_topic_subscription" "lambda_cost_guard_80" {
  topic_arn = aws_sns_topic.budget_alarms_80.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.cost_guard.arn
}

resource "aws_sns_topic_subscription" "lambda_cost_guard_95" {
  topic_arn = aws_sns_topic.budget_alarms_95.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.cost_guard.arn
}

# Custom budget periods
resource "aws_budgets_budget" "custom_period" {
  for_each = { for period in var.budget_periods : period.name => period }

  name              = "${local.cost_guard_name}-${each.key}"
  budget_type       = "COST"
  limit_unit        = "USD"
  limit_amount      = each.value.amount
  time_period_start = each.value.start_date
  time_period_end   = each.value.end_date
  time_unit         = var.budget_time_unit

  cost_filter {
    name   = "Service"
    values = ["*"]
  }

  notification {
    comparison_operator   = "GREATER_THAN"
    notification_type     = "FORECASTED"
    threshold             = 80
    threshold_type        = "PERCENTAGE"
    notification_channels = [aws_sns_topic.budget_alarms_80.arn]
    messages = {
      en = "Budget Alert: Your forecasted AWS spending will exceed 80% of your ${each.value.amount} budget for ${each.key}."
    }
  }

  notification {
    comparison_operator   = "GREATER_THAN"
    notification_type     = "FORECASTED"
    threshold             = 95
    threshold_type        = "PERCENTAGE"
    notification_channels = [aws_sns_topic.budget_alarms_95.arn]
    messages = {
      en = "CRITICAL Budget Alert: Your forecasted AWS spending will exceed 95% of your ${each.value.amount} budget for ${each.key}. Scaling down resources."
    }
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-${each.key}-budget"
    }
  )
}

# Monthly fallback budgets when no custom periods are set
resource "aws_budgets_budget" "monthly_80_percent" {
  count             = length(var.budget_periods) == 0 ? 1 : 0
  name              = "${local.cost_guard_name}-80-percent"
  budget_type       = "COST"
  limit_unit        = "USD"
  limit_amount      = var.budget_limit
  time_period_start = "2024-01-01_00:00"
  time_period_end   = "2087-12-31_23:59"
  time_unit         = var.budget_time_unit

  cost_filter {
    name   = "Service"
    values = ["*"]
  }

  notification {
    comparison_operator   = "GREATER_THAN"
    notification_type     = "FORECASTED"
    threshold             = 80
    threshold_type        = "PERCENTAGE"
    notification_channels = [aws_sns_topic.budget_alarms_80.arn]
    messages = {
      en = "Budget Alert: Your forecasted AWS spending will exceed 80% of your $${var.budget_limit} budget limit."
    }
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-budget-80"
    }
  )
}

resource "aws_budgets_budget" "monthly_95_percent" {
  count             = length(var.budget_periods) == 0 ? 1 : 0
  name              = "${local.cost_guard_name}-95-percent"
  budget_type       = "COST"
  limit_unit        = "USD"
  limit_amount      = var.budget_limit
  time_period_start = "2024-01-01_00:00"
  time_period_end   = "2087-12-31_23:59"
  time_unit         = var.budget_time_unit

  cost_filter {
    name   = "Service"
    values = ["*"]
  }

  notification {
    comparison_operator   = "GREATER_THAN"
    notification_type     = "FORECASTED"
    threshold             = 95
    threshold_type        = "PERCENTAGE"
    notification_channels = [aws_sns_topic.budget_alarms_95.arn]
    messages = {
      en = "CRITICAL Budget Alert: Your forecasted AWS spending will exceed 95% of your $${var.budget_limit} budget limit. Scaling down resources."
    }
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-budget-95"
    }
  )
}
