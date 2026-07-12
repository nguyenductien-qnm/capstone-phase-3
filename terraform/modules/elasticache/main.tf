# Subnet Group cho ElastiCache Valkey
resource "aws_elasticache_subnet_group" "this" {
  name        = "${var.project_name}-${var.environment}-valkey-subnet-group"
  subnet_ids  = var.cache_subnet_ids
  description = "Subnet group cho ElastiCache Valkey"
}

# Security Group cho ElastiCache Valkey
resource "aws_security_group" "valkey" {
  name        = "${var.project_name}-${var.environment}-valkey-sg"
  vpc_id      = var.vpc_id
  description = "Security Group cho ElastiCache Valkey"

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow connection from application subnets to Valkey"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-valkey-sg"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Replication Group cho Valkey
resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.project_name}-${var.environment}-valkey"
  description          = "Valkey replication group cho ${var.project_name}"
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_clusters
  port                 = 6379

  engine         = "valkey"
  engine_version = "7.2"

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.valkey.id]

  automatic_failover_enabled = true
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-valkey"
    Environment = var.environment
    Project     = var.project_name
  }
}
