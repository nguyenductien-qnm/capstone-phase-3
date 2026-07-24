data "aws_secretsmanager_secret_version" "msk_credentials" {
  secret_id = module.msk.msk_secret_arn
}

resource "kafka_topic" "checkout_orders" {
  name               = "domain.checkout.orders"
  replication_factor = 2
  partitions         = 3
}

resource "kafka_topic" "fulfillment_events" {
  name               = "domain.fulfillment.events"
  replication_factor = 2
  partitions         = 3
}