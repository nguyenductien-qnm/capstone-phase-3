resource "aws_dynamodb_table" "checkout_orders" {
	name = "${var.project_name}-${var.environment}-checkout-orders"
	billing_mode = var.billing_mode
	hash_key = var.hash_key
	range_key = var.range_key

	read_capacity = var.billing_mode == "PROVISIONED" ? var.read_capacity : null
	write_capacity = var.billing_mode == "PROVISIONED" ? var.write_capacity : null

	// Data type of PK
	attribute {
		name = var.hash_key
		type = var.hash_key_type
	}

	// Data type of SK
	// SK is a optional in DynamoDB so this dynamic block makes the code flexible 
	// especially when range_key isn't used
	dynamic "attribute" {
		for_each = var.range_key != null ? [1] : []
		content {
		  name = var.range_key
		  type = var.range_key_type
		}
	}

	// Must-have attributes for GSI
	attribute {
	  name = "reconcile_pk"
	  type = "S"
	}
	attribute {
	  name = "reconcile_at"
	  type = "S"
	}

	// GSI 
	global_secondary_index {
	  name = var.global_secondary_index_name
	  projection_type = var.global_secondary_index_projection_type

	  key_schema {
		attribute_name = "reconcile_pk"
		key_type = "HASH" // Partition key
	  }

	  key_schema {
		attribute_name = "reconcile_at"
		key_type = "RANGE" // Sort key
	  }
	}

	stream_enabled = var.stream_enabled
	stream_view_type = var.stream_enabled ? var.stream_view_type : null

	ttl {
	  enabled = var.ttl_enabled
	  attribute_name = var.ttl_attribute_name
	}

	tags = {
		Name = "${var.project_name}-${var.environment}-${var.table_name}"
		Environment = var.environment
		Project = var.project_name
	}
}