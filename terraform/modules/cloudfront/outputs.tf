output "cloudfront_domain_name" {
  description = "Tên miền mặc định của CloudFront Distribution (ví dụ: *.cloudfront.net)"
  value       = aws_cloudfront_distribution.this.domain_name
}

output "cloudfront_arn" {
  description = "ARN của CloudFront Distribution"
  value       = aws_cloudfront_distribution.this.arn
}

output "cloudfront_hosted_zone_id" {
  description = "Hosted zone ID của CloudFront — dùng cho Route53 alias record trỏ về distribution"
  value       = aws_cloudfront_distribution.this.hosted_zone_id
}
