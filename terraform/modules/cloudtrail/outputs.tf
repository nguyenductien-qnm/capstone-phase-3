output "cloudtrail_arn" {
  description = "ARN của AWS CloudTrail"
  value       = aws_cloudtrail.main_trail.arn
}

output "s3_bucket_name" {
  description = "Tên S3 Bucket lưu trữ log CloudTrail"
  value       = aws_s3_bucket.cloudtrail_logs.id
}
