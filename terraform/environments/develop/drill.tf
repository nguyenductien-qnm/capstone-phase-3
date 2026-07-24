# Security Group cách ly chỉ phục vụ cho việc verify DR Drill (CDO-269)
# Không kế thừa inbound rules từ EKS Node Group để tránh Pod nghiệp vụ kết nối nhầm
resource "aws_security_group" "db_drill" {
  name        = "${var.project_name}-${var.environment}-rds-drill-sg"
  vpc_id      = module.vpc.vpc_id
  description = "Security Group co lap chi phuc vu verify DR Drill"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["${var.bastion_or_runner_ip}/32"]
    description = "Allow connection only from Admin Bastion or Runner host for verification"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-drill-sg"
    Environment = var.environment
    Project     = var.project_name
  }
}

output "db_drill_security_group_id" {
  description = "Security Group ID dung cho RDS Drill Temp Instance"
  value       = aws_security_group.db_drill.id
}
