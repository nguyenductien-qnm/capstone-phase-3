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

# Rule cho phép EKS connect tới MSK brokers (port 9092 cho Plaintext, 9094 cho TLS)
resource "aws_security_group_rule" "msk_ingress_eks" {
  type                     = "ingress"
  from_port                = 9092
  to_port                  = 9094
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.msk.id
  description              = "Allow connection from EKS nodes to MSK cluster"
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

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS_PLAINTEXT"
      in_cluster    = true
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

