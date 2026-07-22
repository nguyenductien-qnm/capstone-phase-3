resource "aws_secretsmanager_secret" "slack_webhook" {
  name                    = "${var.name_prefix}/slack-webhook"
  description             = "Slack incoming webhook used by the audit alert Lambda"
  kms_key_id              = var.slack_webhook_kms_key_arn
  recovery_window_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.name_prefix}/slack-webhook"
  })
}

resource "aws_secretsmanager_secret_version" "slack_webhook" {
  secret_id                = aws_secretsmanager_secret.slack_webhook.id
  secret_string_wo         = var.slack_webhook_url
  secret_string_wo_version = var.slack_webhook_secret_version
}
