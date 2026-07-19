resource "aws_security_group" "msk" {
  name        = "${var.project_name}-${var.environment}-msk-sg"
  vpc_id      = var.vpc_id
  description = "Security Group cho Amazon MSK Cluster"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk-sg"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Rule cho phép EKS connect tới MSK brokers (cổng 9096 cho SASL/SCRAM)
resource "aws_security_group_rule" "msk_ingress_eks" {
  type                     = "ingress"
  from_port                = 9092
  to_port                  = 9096
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.msk.id
  description              = "Allow connection from EKS nodes to MSK cluster"
}

resource "aws_security_group_rule" "msk_ingress_lambda" {
  type = "ingress"
  from_port = 9096
  to_port = 9096
  protocol = "tcp"
  source_security_group_id = var.lambda_security_group_id
  security_group_id = aws_security_group.msk.id 
  description = "Allow Lambda function to push messages over SASL/SCRAM" 
}

# MSK Configuration: bật auto.create.topics.enable để services tự tạo topic
resource "aws_msk_configuration" "this" {
  name              = "${var.project_name}-${var.environment}-msk-config-${replace(var.kafka_version, ".", "-")}"
  kafka_versions    = [var.kafka_version]
  server_properties = <<-EOT
    auto.create.topics.enable=true
    default.replication.factor=2
    min.insync.replicas=1
    num.partitions=1
  EOT

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_msk_cluster" "this" {
  cluster_name           = "${var.project_name}-${var.environment}-msk"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = length(var.mq_subnet_ids)

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.mq_subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.ebs_volume_size
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.this.arn
    revision = aws_msk_configuration.this.latest_revision
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  client_authentication {
    sasl {
      scram = true
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = false
      }
      node_exporter {
        enabled_in_broker = false
      }
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.project_name}-${var.environment}-msk"
  retention_in_days = 3

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# KMS Key cho Secrets Manager để lưu msk credentials (bắt buộc cho MSK SCRAM)
resource "aws_kms_key" "msk" {
  description             = "KMS Key cho MSK Secrets Manager"
  deletion_window_in_days = 7

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk-kms-key"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Sinh mật khẩu ngẫu nhiên cho msk user
resource "random_password" "msk_password" {
  length  = 16
  special = false
}

# AWS Secrets Manager lưu trữ credentials (phải bắt đầu bằng AmazonMSK_)
resource "aws_secretsmanager_secret" "msk_credentials" {
  name                    = "AmazonMSK_${var.project_name}-${var.environment}-msk-secret"
  kms_key_id              = aws_kms_key.msk.key_id
  recovery_window_in_days = 0

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk-secret"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "msk_credentials" {
  secret_id = aws_secretsmanager_secret.msk_credentials.id
  # MSK SCRAM association yêu cầu secret CHỈ chứa username/password -> giữ sạch.
  # Endpoint (brokers) lưu ở secret riêng bên dưới để ESO đọc, tránh làm hỏng
  # aws_msk_scram_secret_association.
  secret_string = jsonencode({
    username = "msk_user"
    password = random_password.msk_password.result
  })
}

# Secret riêng chứa endpoint MSK (brokers) cho External Secrets Operator đồng bộ
# vào cluster. Tách khỏi SCRAM credential secret (không được thêm field ngoài
# username/password vào secret dùng cho scram_secret_association).
resource "aws_secretsmanager_secret" "msk_endpoint" {
  name                    = "${var.project_name}-${var.environment}-msk-endpoint"
  recovery_window_in_days = 0

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk-endpoint"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "msk_endpoint" {
  secret_id = aws_secretsmanager_secret.msk_endpoint.id
  secret_string = jsonencode({
    brokers_sasl_scram = aws_msk_cluster.this.bootstrap_brokers_sasl_scram
  })
}

# Liên kết secrets với MSK cluster
resource "aws_msk_scram_secret_association" "this" {
  cluster_arn     = aws_msk_cluster.this.arn
  secret_arn_list = [aws_secretsmanager_secret.msk_credentials.arn]

  depends_on = [
    aws_secretsmanager_secret_version.msk_credentials
  ]
}

