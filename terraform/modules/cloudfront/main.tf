locals {
  origin_id = "nlb-origin"
}

# CloudFront Distribution trỏ trực tiếp đến NLB
resource "aws_cloudfront_distribution" "this" {
  origin {
    domain_name = var.origin_domain_name
    origin_id   = local.origin_id

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only" # Gọi NLB origin qua HTTP port 80
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled         = true
  is_ipv6_enabled = true
  comment         = "CloudFront Distribution cho ${var.project_name} - ${var.environment}"
  aliases         = var.aliases

  # Cấu hình Default Cache Behavior tối ưu cho Dynamic API (no caching)
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = local.origin_id

    # KHÔNG forward Host: headers = ["*"] giữ nguyên Host của khách
    # (ecommerce.*) khi gọi origin -> ALB không có rule cho tên đó -> 404.
    # Bỏ "*" để CloudFront tự set Host = origin-ecommerce.* -> khớp rule Ingress.
    # Liệt kê tường minh header cần cho app động; Host cố tình vắng mặt.
    forwarded_values {
      query_string = true
      headers = [
        "Authorization",
        "Origin",
        "Accept",
        "Accept-Language",
        "Content-Type",
        "Referer",
        "CloudFront-Forwarded-Proto",
      ]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https" # Chuyển hướng HTTP sang HTTPS
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Cấu hình Certificate (sử dụng ACM nếu được cấp, ngược lại dùng default cloudfront cert)
  viewer_certificate {
    cloudfront_default_certificate = var.acm_certificate_arn == null ? true : false
    acm_certificate_arn            = var.acm_certificate_arn
    ssl_support_method             = var.acm_certificate_arn != null ? "sni-only" : null
    minimum_protocol_version       = var.acm_certificate_arn != null ? "TLSv1.2_2021" : null
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-cloudfront"
    Environment = var.environment
    Project     = var.project_name
  }
}
