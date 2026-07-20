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