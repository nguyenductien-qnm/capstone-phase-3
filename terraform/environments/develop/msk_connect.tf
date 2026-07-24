data "aws_secretsmanager_secret_version" "msk_credentials" {
  secret_id = module.msk.msk_secret_arn
}

# 1. S3 bucket for MSK Connect Plugins
resource "aws_s3_bucket" "msk_plugins" {
  bucket = "${var.project_name}-${var.environment}-msk-plugins"
}

# Upload the Debezium ZIP plugin to S3
resource "aws_s3_object" "debezium_plugin_zip" {
  bucket = aws_s3_bucket.msk_plugins.id
  key    = "debezium-connector-postgres-plugin.zip"
  source = "./plugins/debezium-connector-postgres-plugin.zip"

  # filemd5 calculates MD5 hash of ZIP file so new plugin uploads trigger updates
  etag = filemd5("./plugins/debezium-connector-postgres-plugin.zip")
}

# 2. Security Group for MSK Connect 
resource "aws_security_group" "msk_connect" {
  name        = "${var.project_name}-${var.environment}-msk-connect-sg"
  vpc_id      = module.vpc.vpc_id
  description = "Security Group for MSK Connect Debezium connector"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-msk-connect-sg"
    Environment = var.environment
  }
}

# Ingress rule: Allow MSK Connect to talk to RDS PostgreSQL (port 5432) 
resource "aws_security_group_rule" "rds_ingress_msk_connect" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.msk_connect.id
  security_group_id        = module.rds.rds_security_group_id
  description              = "Allow MSK Connect to connect to RDS PostgreSQL"
}

# Ingress rule: Allow MSK Connect to talk to MSK Brokers
resource "aws_security_group_rule" "msk_ingress_msk_connect" {
  type                     = "ingress"
  from_port                = 9092
  to_port                  = 9098
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.msk_connect.id
  security_group_id        = module.msk.msk_security_group_id
  description              = "Allow MSK Connect to connect to MSK cluster brokers"
}

# 3. IAM Role for MSK Connect 
resource "aws_iam_role" "msk_connect" {
  name = "${var.project_name}-${var.environment}-msk-connect-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "kafkaconnect.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "msk_connect" {
  name = "${var.project_name}-${var.environment}-msk-connect-policy"
  role = aws_iam_role.msk_connect.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.msk_plugins.arn,
          "${aws_s3_bucket.msk_plugins.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [module.msk.msk_secret_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [module.msk.kms_key_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:AlterCluster",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:CreateTopic",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:WriteData",
          "kafka-cluster:ReadData",
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = "*"
      }
    ]
  })
}

# 4. Custom Plugin definition 
resource "aws_mskconnect_custom_plugin" "debezium" {
  name         = "${var.project_name}-${var.environment}-debezium-plugin"
  content_type = "ZIP"

  location {
    s3 {
      bucket_arn = aws_s3_bucket.msk_plugins.arn
      file_key   = aws_s3_object.debezium_plugin_zip.key
    }
  }
}


# 5. Debezium Connector on AWS MSK Connect
resource "aws_mskconnect_connector" "debezium_postgres" {
  name                 = "${var.project_name}-${var.environment}-debezium-postgres"
  kafkaconnect_version = "2.7.1"

  capacity {
    provisioned_capacity {
      mcu_count    = 1
      worker_count = 1
    }
  }

  // AWS MSK Connect runs the Debezium PostgreSQL connector
  // Debezium connects via the native PostgreSQL pgoutput logical decoding plugin
  // listens for change events on dbz_publication
  connector_configuration = {
    "connector.class"                = "io.debezium.connector.postgresql.PostgresConnector"
    "tasks.max"                      = "1"
    "database.hostname"              = module.rds.db_primary_address
    "database.port"                  = "5432"
    "database.user"                  = module.rds.db_username
    "database.password"              = module.rds.db_password
    "database.dbname"                = module.rds.db_name
    "topic.prefix"                   = "fulfillment"
    "table.include.list"             = "checkout.outbox"
    "plugin.name"                    = "pgoutput"
    "publication.name"               = "dbz_publication"
    "publication.autocreate.mode"    = "all_tables"
    "tombstones.on.delete"           = "false"
    "decimal.handling.mode"          = "double"
    "key.converter"                  = "org.apache.kafka.connect.storage.StringConverter"
    "value.converter"                = "org.apache.kafka.connect.json.JsonConverter"
    "value.converter.schemas.enable" = "false"
    "transforms"                     = "reroute"
    "transforms.reroute.type"        = "org.apache.kafka.connect.transforms.RegexRouter"
    "transforms.reroute.regex"       = ".*"
    "transforms.reroute.replacement" = "domain.checkout.orders"
  }

  kafka_cluster {
    apache_kafka_cluster {
      bootstrap_servers = module.msk.bootstrap_brokers_sasl_iam

      vpc {
        subnets         = values(module.vpc.private_mq_subnet_ids)
        security_groups = [aws_security_group.msk_connect.id]
      }
    }
  }

  kafka_cluster_client_authentication {
    authentication_type = "IAM"
  }

  kafka_cluster_encryption_in_transit {
    encryption_type = "TLS"
  }

  plugin {
    custom_plugin {
      arn      = aws_mskconnect_custom_plugin.debezium.arn
      revision = aws_mskconnect_custom_plugin.debezium.latest_revision
    }
  }

  worker_configuration {
    arn      = aws_mskconnect_worker_configuration.debezium.arn
    revision = aws_mskconnect_worker_configuration.debezium.latest_revision
  }

  service_execution_role_arn = aws_iam_role.msk_connect.arn
}

# 6. Worker Configuration for MSK Connect SASL/SCRAM authentication
resource "aws_mskconnect_worker_configuration" "debezium" {
  name = "${var.project_name}-${var.environment}-debezium-worker-config"

  properties_file_content = <<-EOT
    key.converter=org.apache.kafka.connect.storage.StringConverter
    value.converter=org.apache.kafka.connect.json.JsonConverter
    value.converter.schemas.enable=false
  EOT
}