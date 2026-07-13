# Mật khẩu quản trị ngẫu nhiên
resource "random_password" "db_password" {
  length  = 16
  special = false # Tránh các ký tự đặc biệt gây lỗi chuỗi kết nối
}

# Subnet Group cho Database
resource "aws_db_subnet_group" "this" {
  name        = "${var.project_name}-${var.environment}-rds-subnet-group"
  subnet_ids  = var.database_subnet_ids
  description = "Subnet group cho database RDS PostgreSQL"

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-subnet-group"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Security Group cho Database
resource "aws_security_group" "db" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  vpc_id      = var.vpc_id
  description = "Security Group cho RDS PostgreSQL"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-sg"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_security_group_rule" "db_ingress_app" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = var.eks_node_security_group_id
  security_group_id        = aws_security_group.db.id
  description              = "Allow connection from application subnets to database"
}

# Rule kết nối từ RDS Proxy vào DB (nếu bật Proxy)
resource "aws_security_group_rule" "db_ingress_proxy" {
  count = var.enable_rds_proxy ? 1 : 0

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.proxy[0].id
  security_group_id        = aws_security_group.db.id
  description              = "Allow connection from RDS Proxy to database"
}

# Primary Database Instance
resource "aws_db_instance" "this" {
  identifier           = "${var.project_name}-${var.environment}-postgres"
  engine               = "postgres"
  engine_version       = var.engine_version
  instance_class       = var.instance_class
  allocated_storage    = var.allocated_storage
  db_name              = var.db_name
  username             = var.db_username
  password             = random_password.db_password.result
  db_subnet_group_name = aws_db_subnet_group.this.name
  skip_final_snapshot  = true
  multi_az             = var.multi_az
  storage_encrypted    = true

  # Phải bật backup retention để cho phép tạo Read Replica
  backup_retention_period = 7

  vpc_security_group_ids = [aws_security_group.db.id]

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-primary"
    Environment = var.environment
    Project     = var.project_name
  }

  lifecycle {
    ignore_changes = [password]
  }
}

# Read Replica Database Instance
resource "aws_db_instance" "replica" {
  count = var.enable_read_replica ? 1 : 0

  identifier           = "${var.project_name}-${var.environment}-postgres-replica"
  replicate_source_db  = aws_db_instance.this.identifier
  instance_class       = var.replica_instance_class
  skip_final_snapshot  = true
  db_subnet_group_name = null # replica tự động thừa hưởng subnet group của primary
  storage_encrypted    = true

  vpc_security_group_ids = [aws_security_group.db.id]

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-replica"
    Environment = var.environment
    Project     = var.project_name
  }

  depends_on = [aws_db_instance.this]
}

# -------------------------------------------------------------
# CẤU HÌNH RDS PROXY (Chỉ tạo khi enable_rds_proxy = true)
# -------------------------------------------------------------

# Security Group cho RDS Proxy
resource "aws_security_group" "proxy" {
  count = var.enable_rds_proxy ? 1 : 0

  name        = "${var.project_name}-${var.environment}-rds-proxy-sg"
  vpc_id      = var.vpc_id
  description = "Security Group cho RDS Proxy"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.eks_node_security_group_id]
    description     = "Allow connection from application subnets to RDS Proxy"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-proxy-sg"
    Environment = var.environment
    Project     = var.project_name
  }
}

# AWS Secrets Manager để lưu credentials cho RDS Proxy
resource "aws_secretsmanager_secret" "db_credentials" {
  count = var.enable_rds_proxy ? 1 : 0

  name                    = "${var.project_name}-${var.environment}-rds-secret"
  recovery_window_in_days = 0 # Xóa ngay lập tức khi destroy

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  count = var.enable_rds_proxy ? 1 : 0

  secret_id = aws_secretsmanager_secret.db_credentials[0].id
  secret_string = jsonencode({
    username            = var.db_username
    password            = random_password.db_password.result
    engine              = "postgres"
    host                = aws_db_instance.this.address
    port                = 5432
    dbClusterIdentifier = aws_db_instance.this.identifier
  })
}

# IAM Role để RDS Proxy đọc Secret
resource "aws_iam_role" "rds_proxy" {
  count = var.enable_rds_proxy ? 1 : 0

  name = "${var.project_name}-${var.environment}-rds-proxy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_iam_role_policy" "rds_proxy" {
  count = var.enable_rds_proxy ? 1 : 0

  name = "${var.project_name}-${var.environment}-rds-proxy-policy"
  role = aws_iam_role.rds_proxy[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials[0].arn
        ]
      }
    ]
  })
}

# RDS DB Proxy
resource "aws_db_proxy" "this" {
  count = var.enable_rds_proxy ? 1 : 0

  name                   = "${var.project_name}-${var.environment}-rds-proxy"
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = false # Điều chỉnh theo nhu cầu bảo mật thực tế
  role_arn               = aws_iam_role.rds_proxy[0].arn
  vpc_security_group_ids = [aws_security_group.proxy[0].id]
  vpc_subnet_ids         = var.database_subnet_ids

  auth {
    auth_scheme = "SECRETS"
    description = "Database credentials from Secrets Manager"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.db_credentials[0].arn
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-proxy"
    Environment = var.environment
    Project     = var.project_name
  }

  depends_on = [aws_secretsmanager_secret_version.db_credentials]
}

# Liên kết RDS Proxy với Primary Database
resource "aws_db_proxy_target" "this" {
  count = var.enable_rds_proxy ? 1 : 0

  db_proxy_name          = aws_db_proxy.this[0].name
  target_group_name      = "default"
  db_instance_identifier = aws_db_instance.this.identifier
}
