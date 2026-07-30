output "trail_name" {
  description = "CloudTrail trail name"
  value       = aws_cloudtrail.main_trail.name
}
output "trail_arn" {
  description = "CloudTrail trail ARN"
  value       = aws_cloudtrail.main_trail.arn
}
output "cloudtrail_arn" {
  description = "Backward-compatible CloudTrail trail ARN"
  value       = aws_cloudtrail.main_trail.arn
}
output "s3_bucket_name" {
  description = "S3 bucket storing CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail_logs.id
}
output "cloudwatch_log_group_name" {
  description = "CloudWatch log group, or null when disabled"
  value       = try(aws_cloudwatch_log_group.cloudtrail[0].name, null)
}
output "kms_key_arn" {
  description = "Audit KMS key ARN, or null when disabled"
  value       = try(aws_kms_key.audit[0].arn, null)
}
output "tamper_protection_policy_arn" {
  description = "Attach this managed policy to routine operator permission sets/roles"
  value       = aws_iam_policy.audit_log_tamper_protection.arn
}
output "tamper_protection_policy_json" {
  description = "Policy JSON for administrative review or permission-set integration"
  value       = data.aws_iam_policy_document.audit_log_tamper_protection.json
}

output "mandate_12_alert_rule_name" {
  description = "Mandate-12 EventBridge rule name for audit tamper alerts, or null when disabled"
  value       = try(aws_cloudwatch_event_rule.mandate_12_audit_tamper[0].name, null)
}

output "mandate_12_alert_topic_arn" {
  description = "Mandate-12 SNS topic ARN for audit tamper email alerts, or null when disabled"
  value       = try(aws_sns_topic.mandate_12_audit_tamper[0].arn, null)
}
