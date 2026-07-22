terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }

    # Kafka provider
    kafka = {
      source = "Mongey/kafka"
      version = "~> 0.7.0"
    }
  }

  # Backend settings are supplied only by the Develop GitHub Environment.
  # # Keeping this block partial prevents accidental reuse of the Sandbox state.
  backend "s3" {}
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "CDO-09"
    }
  }
}

# Kafka provider needs the MSK brokers and credentials to connect
provider "kafka" {
  bootstrap_servers = split(",", module.msk.bootstrap_brokers_sasl_scram)

  tls_enabled = true
  sasl_username = jsondecode(data.aws_secretmanager_secret_version.msk_credentials_secret_string)["username"]
  sasl_password = jsondecode(data.aws_secretsmanager_secret_version.msk_credentials_secret_string)["password"]
  sasl_mechanism = "scram-sha512"
}