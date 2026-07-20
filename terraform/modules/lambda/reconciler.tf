resource "aws_iam_role" "reconciler_lambda_role" {
  name = "${var.project_name}-${var.environment}-reconciler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "reconciler_lambda_vpc_access" {
  role       = aws_iam_role.reconciler_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "reconciler_dynamodb_policy" {
  name = "ReconcilerDynamoDBPolicy"
  role = aws_iam_role.reconciler_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        
		// Access to GSI
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_lambda_function" "reconciler_processor" {
  filename      = "lambda_reconciler_processor.zip"
  function_name = "${var.project_name}-${var.environment}-reconciler"
  role          = aws_iam_role.reconciler_lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 60

  vpc_config {
    subnet_ids         = var.lambda_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id] # SG from shared.tf
  }

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = split("/", var.dynamodb_table_arn)[1]
      PAYMENT_SVC_ADDR    = "payment:50051"
    }
  }
}

resource "aws_cloudwatch_event_rule" "reconciler_schedule" {
  name                = "${var.project_name}-${var.environment}-reconciler-schedule"
  description         = "Trigger reconciler Lambda every 5 minutes to process PENDING orders"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "reconciler_target" {
  rule      = aws_cloudwatch_event_rule.reconciler_schedule.name
  target_id = "ReconcilerLambda"
  arn       = aws_lambda_function.reconciler_processor.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reconciler_processor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reconciler_schedule.arn
}