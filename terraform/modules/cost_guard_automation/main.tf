data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  cost_guard_name = "${var.project_name}-${var.environment}-cost-guard"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Module      = "CostGuardAutomation"
  }
}

# CMK dùng CHUNG cho cả hai topic budget (80% và 95%).
#
# Vì sao một key cho hai topic: cùng một publisher (budgets.amazonaws.com), cùng vòng đời,
# cùng mức nhạy cảm. Tách hai key chỉ tốn thêm $1/tháng mà không thu hẹp được quyền gì.
#
# Vì sao KHÔNG dùng alias/aws/sns (sửa lại quyết định 26/07): AWS Budgets là service
# publisher, cần kms:GenerateDataKey* + kms:Decrypt khai trong KEY POLICY. Key alias/aws/sns
# do AWS quản nên không sửa policy được -> Budgets publish FAIL IM LẶNG. Topic policy bên
# dưới cho budgets.amazonaws.com quyền sns:Publish là chưa đủ: đó là quyền trên TOPIC, còn
# thiếu quyền trên KEY. Docs AWS mục "Enable compatibility between event sources from AWS
# services and encrypted topics" nói bước đầu tiên là "Use a customer managed key".
data "aws_iam_policy_document" "budget_alarms_kms" {
  statement {
    sid     = "AccountKeyAdministration"
    effect  = "Allow"
    actions = ["kms:*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    resources = ["*"]
  }

  statement {
    sid    = "AllowBudgetsPublish"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]

    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }

    resources = ["*"]

    # CỐ Ý KHÔNG siết bằng aws:SourceAccount ở đây. Bản nháp có condition này với lý do
    # "docs chỉ cấm cho EventBridge, Budgets thì thêm được" — nhưng "không bị cấm" KHÁC
    # "đã chứng minh chạy được", và đó đúng là ngộ nhận sinh ra chính sự cố PR này đi sửa.
    #
    # Ba căn cứ để bỏ:
    #
    # 1. Docs AWS KHÔNG xác nhận được theo cả hai chiều. Trang duy nhất có thể trả lời —
    #    cost-management/budgets-sns-policy, mục "To enable compatibility between AWS
    #    Budgets and encrypted Amazon SNS topics" — ghi bước 2 là "Add the following text
    #    to the KMS key policy" nhưng KHỐI JSON PHÍA SAU RỖNG (AWS quên đăng). Không có
    #    mẫu policy chính thức nào để đối chiếu.
    #
    # 2. Bất đối xứng rủi ro. Nếu lời gọi KMS của Budgets không mang aws:SourceAccount thì
    #    StringEquals fail -> deny -> CẢ HAI topic budget chết im lặng. Budget chỉ bắn khi
    #    vượt ngưỡng nên không có traffic thường xuyên để lộ lỗi sớm — có thể câm hàng
    #    tháng mà không ai biết.
    #
    # 3. Giá trị bảo mật thấp hơn tưởng. Cùng trang docs ghi "Amazon SNS topics must be in
    #    the same account as the Budgets you're configuring. Cross-account Amazon SNS isn't
    #    supported" — account khác không trỏ budget của họ vào topic này được, và key policy
    #    cũng không grant account nào khác. Đường confused deputy đã bị chặn ở lớp SNS.
    #
    # Đối chiếu tiền lệ: aws_sns_topic_policy bên dưới cho budgets.amazonaws.com quyền
    # SNS:Publish cũng KHÔNG có condition này, và Budgets vẫn publish được (topic 80 đang
    # sống trên PROD). Tức repo chưa từng chứng minh Budgets truyền context đó.
    #
    # Muốn siết lại: chỉ làm SAU khi có bằng chứng hành vi (test budget bắn thành công qua
    # condition), không siết mù.
  }

  # Statement BẮT BUỘC, không phải tuỳ chọn. Docs KMS (services-sns) nói rõ SNS KHÔNG
  # dùng credential của bên gọi để thao tác với key — chính service principal
  # sns.amazonaws.com phải có kms:GenerateDataKey*/kms:Decrypt trong key policy, nếu
  # không thì SNS không mã hoá nổi message dù Budgets đã được cấp quyền publish.
  #
  # Bản đầu của PR này THIẾU statement này, chỉ có 2 statement trong khi tiền lệ
  # pipeline_health (detection-routing/sns.tf) có 3. Thiếu nó là tái lập đúng lớp lỗi
  # "hỏng im lặng" mà PR đang đi sửa.
  #
  # Liệt kê CẢ HAI topic ARN vì key này dùng chung cho ngưỡng 80% và 95%. Thêm topic mới
  # dùng key này thì phải thêm ARN vào đây, nếu không topic đó publish fail.
  statement {
    sid    = "AllowSNSTopicEncryption"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]

    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:aws:sns:topicArn"
      values = [
        "arn:${data.aws_partition.current.partition}:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.cost_guard_name}-budget-alarms-80",
        "arn:${data.aws_partition.current.partition}:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.cost_guard_name}-budget-alarms-95",
      ]
    }
  }
}

resource "aws_kms_key" "budget_alarms" {
  description             = "Encrypt cost-guard budget alarm notifications for ${local.cost_guard_name}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.budget_alarms_kms.json

  tags = merge(local.common_tags, { Name = "${local.cost_guard_name}-budget-alarms" })
}

resource "aws_kms_alias" "budget_alarms" {
  name          = "alias/${local.cost_guard_name}-budget-alarms"
  target_key_id = aws_kms_key.budget_alarms.key_id
}

# SNS Topics cho Budget Alarms
resource "aws_sns_topic" "budget_alarms_80" {
  name = "${local.cost_guard_name}-budget-alarms-80"

  # CKV_AWS_26: CMK riêng, không phải alias/aws/sns — lý do ở khối aws_kms_key trên.
  kms_master_key_id = aws_kms_key.budget_alarms.arn

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-topic-80"
    }
  )
}

resource "aws_sns_topic" "budget_alarms_95" {
  name = "${local.cost_guard_name}-budget-alarms-95"

  # CKV_AWS_26: dùng chung CMK với topic 80 — xem chú thích ở aws_kms_key.budget_alarms.
  kms_master_key_id = aws_kms_key.budget_alarms.arn

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
          "eks:DescribeCluster",
          "eks:UpdateClusterConfig",
          "eks:AccessKubernetesApi",
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
          "eks:UpdateNodegroupConfig"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "autoscaling:SetDesiredCapacity",
          "autoscaling:DescribeAutoScalingGroups"
        ]
        Resource = "*"
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
        "elasticache:DecreaseReplicaCount",
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

# Lambda function
resource "aws_lambda_function" "cost_guard" {
  filename         = "${path.module}/lambda_function.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_function.zip")
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
      EC2_INSTANCE_TAG_NAME    = var.ec2_instance_tags.tag_name
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

# SNS Topic Policies to allow AWS Budgets to publish alerts
resource "aws_sns_topic_policy" "budget_alarms_80_policy" {
  arn = aws_sns_topic.budget_alarms_80.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowBudgetsToPublish"
        Effect = "Allow"
        Principal = {
          Service = "budgets.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.budget_alarms_80.arn
      }
    ]
  })
}

resource "aws_sns_topic_policy" "budget_alarms_95_policy" {
  arn = aws_sns_topic.budget_alarms_95.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowBudgetsToPublish"
        Effect = "Allow"
        Principal = {
          Service = "budgets.amazonaws.com"
        }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.budget_alarms_95.arn
      }
    ]
  })
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



  notification {
    comparison_operator       = "GREATER_THAN"
    notification_type         = "FORECASTED"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alarms_80.arn]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    notification_type         = "FORECASTED"
    threshold                 = 95
    threshold_type            = "PERCENTAGE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alarms_95.arn]
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
  time_period_start = "2026-07-01_00:00"
  time_period_end   = "2087-12-31_23:59"
  time_unit         = var.budget_time_unit

  notification {
    comparison_operator       = "GREATER_THAN"
    notification_type         = "FORECASTED"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alarms_80.arn]
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
  time_period_start = "2026-07-01_00:00"
  time_period_end   = "2087-12-31_23:59"
  time_unit         = var.budget_time_unit

  notification {
    comparison_operator       = "GREATER_THAN"
    notification_type         = "FORECASTED"
    threshold                 = 95
    threshold_type            = "PERCENTAGE"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alarms_95.arn]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.cost_guard_name}-budget-95"
    }
  )
}
