# ADR-001 (docs/05_adr/ADR-log-cdo05.md): Tailscale Kubernetes Operator cần
# OAuth client để đăng ký với tailnet. Secret lưu ở Secrets Manager, ESO đọc
# vào cluster qua ExternalSecret (platform/gitops/tailscale/) — không bao giờ
# đi qua Helm values / git.
variable "tailscale_oauth_client_id" {
  type        = string
  sensitive   = true
  description = "Tailscale OAuth client ID (tag:k8s-operator scope) — truyền qua TF_VAR_tailscale_oauth_client_id, không commit."
}

variable "tailscale_oauth_client_secret" {
  type        = string
  sensitive   = true
  description = "Tailscale OAuth client secret — truyền qua TF_VAR_tailscale_oauth_client_secret, không commit."
}

resource "aws_secretsmanager_secret" "tailscale_oauth" {
  name = "${var.project_name}-${var.environment}-tailscale-oauth"
}

resource "aws_secretsmanager_secret_version" "tailscale_oauth" {
  secret_id = aws_secretsmanager_secret.tailscale_oauth.id
  secret_string = jsonencode({
    client_id     = var.tailscale_oauth_client_id
    client_secret = var.tailscale_oauth_client_secret
  })
}
