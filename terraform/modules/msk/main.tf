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
    # AVD-AWS-0179: MSK vốn đã mã hoá at-rest bằng key AWS quản lý kể cả khi không khai,
    # nhưng khai tường minh thì đọc được trong Git và scanner không phải đoán. Dùng
    # alias/aws/kafka (key mặc định của service) nên không phát sinh phí KMS.
    #
    # NHỊP 2 của bootstrap (30/07/2026) — khôi phục sau khi apply lần đầu đã sinh ra
    # alias/aws/kafka. KHÔNG được có diff ở đây: cụm tạo bằng key AWS quản lý, và alias
    # phân giải về đúng key đó. Kiểm bằng số thật trước khi mở PR này:
    #   alias/aws/kafka          -> key 7fbc8503-3021-4b5a-b8d0-303dca3f365d
    #   cụm ecommerce-dev-msk    -> DataVolumeKMSKeyId .../key/7fbc8503-...-303dca3f365d
    # Trùng khít. Nếu lần nào plan đòi ĐỔI dòng này thì DỪNG, đừng apply: thuộc tính này
    # thay đổi là thay thế cụm MSK, mất sạch message.
    encryption_at_rest_kms_key_arn = data.aws_kms_alias.msk_managed.target_key_arn

    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  client_authentication {
    sasl {
      scram = true
      iam   = true
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

# Account hiện tại — dùng để dựng key policy tường minh cho KMS key bên dưới.
data "aws_caller_identity" "current" {}

# Key mặc định AWS cấp sẵn cho MSK. Tham chiếu qua alias để khai encryption at-rest
# tường minh mà không phải tạo CMK riêng (CMK tốn ~$1/key/tháng).
#
# BẪY ĐÃ GẶP (30/07/2026): alias này KHÔNG có sẵn trong account mới. AWS chỉ tạo
# alias/aws/<service> khi account dùng service đó lần đầu — docs MSK:
# "If you don't specify a KMS key, Amazon MSK creates an AWS managed key for you and
# uses it on your behalf" (msk-encryption.html). Nên trên account trắng, data source
# này trả empty và `terraform plan` CHẾT trước khi tạo được gì: muốn có alias phải tạo
# cụm, muốn tạo cụm phải có alias.
# Cách đã dùng để phá vòng: comment cả data source này lẫn encryption_at_rest_kms_key_arn
# ở trên, apply một lần cho MSK tự sinh alias, rồi khôi phục (chính là PR này).
# Ai dựng lại từ số 0 ở account mới sẽ gặp lại y hệt — làm đúng hai nhịp đó.
data "aws_kms_alias" "msk_managed" {
  name = "alias/aws/kafka"
}

# KMS Key cho Secrets Manager để lưu msk credentials (bắt buộc cho MSK SCRAM)
resource "aws_kms_key" "msk" {
  description             = "KMS Key cho MSK Secrets Manager"
  deletion_window_in_days = 7

  # CKV_AWS_7: xoay vòng hằng năm. AWS tự sinh material mới và giữ lại bản cũ để giải mã
  # dữ liệu đã mã hoá trước đó, nên bật là an toàn, không cần thao tác gì thêm.
  enable_key_rotation = true

  # CKV2_AWS_64: khai policy tường minh thay vì để AWS gán policy mặc định ngầm. Nội dung
  # tương đương mặc định (root account toàn quyền, Secrets Manager được dùng key qua
  # grant), nhưng viết ra thì đọc được trong Git và diff được khi ai đó nới quyền.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableIAMUserPermissions"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowSecretsManagerUse"
        Effect    = "Allow"
        Principal = { Service = "secretsmanager.amazonaws.com" }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:CreateGrant",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:CallerAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
    ]
  })

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
