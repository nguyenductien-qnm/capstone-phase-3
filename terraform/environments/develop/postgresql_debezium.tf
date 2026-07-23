# Generate a random, secure password for Debezium user
resource "random_password" "debezium_password" {
  length  = 16
  special = false
}

# 1. Create a dedicated user for Debezium inside PostgreSQL instance
resource "postgresql_role" "debezium_user" {
  name        = "debezium_user"
  login       = true
  password    = random_password.debezium_password.result
  replication = true
}

# 2. Grant the AWS-specific rds_replication role 
resource "postgresql_grant_role" "debezium_rds_replication" {
  role       = postgresql_role.debezium_user.name
  grant_role = "rds_replication" # so Debezium can successfully request logical replication streams (WAL)
}

# 3. Grant access to the specific schema 
resource "postgresql_grant" "debezium_schema_usage" {
  role        = postgresql_role.debezium_user.name
  database    = module.rds.db_name
  schema      = "checkout"
  object_type = "schema"
  privileges  = ["USAGE"]
}

# 4. Grant access to the specific table 
resource "postgresql_grant" "debezium_table_select" {
  role        = postgresql_role.debezium_user.name
  database    = module.rds.db_name
  schema      = "checkout"
  object_type = "table"
  objects     = ["outbox"]
  # In the initial running, Debezium implements 'Initial Snapshot' which scan the whole table
  # If it doesnt have SELECT permission, this operation will fail
  privileges = ["SELECT"]
}

# 5. Create the Publication for Debezium to hook into
# which means, Debezium will use this publication to register to receive changes
resource "postgresql_publication" "dbz_publication" {
  name   = "dbz_publication"
  tables = ["checkout.outbox"]
}

# 6. Store Debezium credentials in AWS Secrets Manager for MSK Connect to use
resource "aws_secretsmanager_secret" "debezium_credentials" {
  name                    = "${var.project_name}-${var.environment}-debezium-secret"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "debezium_credentials" {
  secret_id = aws_secretsmanager_secret.debezium_credentials.id
  secret_string = jsonencode({
    username = postgresql_role.debezium_user.name
    password = random_password.debezium_password.result
  })
}