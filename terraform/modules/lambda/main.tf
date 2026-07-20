# Security Group for the Outbox Lambda Function
resource "aws_security_group" "lambda_sg" {
	name = "${var.project_name}-${var.environment}-outbox-lambda-sg"
	vpc_id = var.vpc_id
	description = "Security Group for DynamoDB Stream to MSK Lambda"

	// Outbound: communicate with DynamoDB, MSK, Secrets Manager
	egress {
		from_port   = 0
	    to_port     = 0
	    protocol    = "-1"
	    cidr_blocks = ["0.0.0.0/0"]
	}
}

# IAM Role for Lambda 
resource "aws_iam_role" "outbox_lambda_role" {
	name = "${var.project_name}-${var.environment}-outbox-lambda-role"
	
	// Lambda runs Python code
	assume_role_policy = jsonencode({
		Version = "2012-10-17"
		Statement = [{
			Action = "sts:AssumeRole"
			Effect = "Allow"
			Principal = {Service = "lambda.amazonaws.com"}
		}]
	})
}

# Attach basic VPC execution policies (Allows Lambda to write ENIs for private subnet access)
resource "aws_iam_role_policy_attachment" "outbox_lambda_vpc_access" {
	role = aws_iam_role.outbox_lambda_role.name
	policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Fine-grained Execution Policy 
resource "aws_iam_role_policy" "outbox_lambda_custome_policy" {
	name = "OutboxLambdaCustomPolicy"
	role = aws_iam_role.outbox_lambda_role.id

	policy = jsonencode({
		Version = "2012-10-17"
		Statement = [
			# Lambda needs these permissions to interact with DynamoDB
			{
				Effect = "Allow"
				Action = [
					"dynamodb:GetRecords",
					"dynamodb:GetSharedIterator",
					"dynamodb:DescribeStream",
					"dynamodb:ListStreams"
				]
				Resource = "${var.dynamodb_table_arn}/stream/*"
			},

			# Lambda needs to access to MSK authen credentials & endpoint locations
			{
				Effect = "Allow"
				Action = ["secretsmanager:GetSecretValue"]
				Resource = [
					var.msk_secret_arn,
					var.msk_endpoint_secret_arn
				]
			},

			# Lambda needs KMS to decrypt credentials get in Secrets Manager
			{
				Effect = "Allow"
				Action = ["kms:Decrypt"]
				Resource = [var.kms_key_arn]
			}
		]
	})
}

# Packaging Lambda
resource "null_resource" "pip_install" {
  triggers = {
    requirements = filemd5("${path.root}/../../../techx-corp-platform/src/outbox-lambda/requirements.txt")
  }

  provisioner "local-exec" {
    command = "pip install -r ${path.root}/../../../techx-corp-platform/src/outbox-lambda/requirements.txt -t ${path.root}/../../../techx-corp-platform/src/outbox-lambda"
  }
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../../../techx-corp-platform/src/outbox-lambda"
  output_path = "${path.module}/lambda_outbox_processor.zip"
  depends_on  = [null_resource.pip_install]
}


# Lambda Function Definition 
resource "aws_lambda_function" "outbox_processor" {
	filename = data.archive_file.lambda_zip.output_path
	source_code_hash = data.archive_file.lambda_zip.output_base64sha256
	function_name = "${var.project_name}-${var.environment}-outbox-to-msk"
	role = aws_iam_role.outbox_lambda_role.arn
	handler = "index.handler"
	runtime = "python3.11"
	timeout = 30 

	vpc_config {
	  subnet_ids = var.lambda_subnet_ids // private_msq_subnets
	  security_group_ids = [ aws_security_group.lambda_sg.id ]
	}

	environment {
	  variables = {
	    MSK_CREDENTIALS_SECRET_ARN = var.msk_secret_arn
	    MSK_ENDPOINT_SECRET_ARN    = var.msk_endpoint_secret_arn
	    KAFKA_TOPIC                = "orders"
	    }
	}
}

resource "aws_lambda_event_source_mapping" "dynamodb_stream_trigger" {
	event_source_arn = var.dynamodb_stream_arn
	function_name = aws_lambda_function.outbox_processor.arn
	starting_position = "LATEST"
	batch_size = 100

	# Filter Pattern matching: order_status == COMPLETED
	filter_criteria {
	  	filter {
			pattern = jsonencode({
				eventName = ["INSERT", "MODIFY"]
				dynamodb = {
					NewImage = {
						order_status = {S = ["COMPLETED"]}
					}
				}
			})
		}
	}
}