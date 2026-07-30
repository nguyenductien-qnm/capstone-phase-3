locals {
  thanos_bucket_name = "${var.project_name}-${var.environment}-thanos-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "thanos" {
  bucket = local.thanos_bucket_name

  tags = {
    Name      = local.thanos_bucket_name
    Component = "observability"
  }
}

resource "aws_s3_bucket_public_access_block" "thanos" {
  bucket                  = aws_s3_bucket.thanos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "thanos" {
  bucket = aws_s3_bucket.thanos.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "thanos" {
  bucket = aws_s3_bucket.thanos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "thanos" {
  bucket = aws_s3_bucket.thanos.id

  depends_on = [aws_s3_bucket_versioning.thanos]

  rule {
    id     = "thanos-metrics-retention"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_iam_role" "thanos" {
  name = "${var.project_name}-${var.environment}-thanos"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "pods.eks.amazonaws.com"
      }
      Action = [
        "sts:AssumeRole",
        "sts:TagSession",
      ]
    }]
  })

  tags = {
    Name      = "${var.project_name}-${var.environment}-thanos"
    Component = "observability"
  }
}

resource "aws_iam_role_policy" "thanos_s3" {
  name = "ThanosObjectStorage"
  role = aws_iam_role.thanos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:ListBucketMultipartUploads"]
        Resource = aws_s3_bucket.thanos.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = "${aws_s3_bucket.thanos.arn}/*"
      },
    ]
  })
}

resource "aws_eks_pod_identity_association" "thanos" {
  for_each = toset([
    "thanos-compactor",
    "thanos-receive",
    "thanos-storegateway",
  ])

  cluster_name    = module.eks.cluster_name
  namespace       = "techx-tf1"
  service_account = each.value
  role_arn        = aws_iam_role.thanos.arn
}

output "thanos_bucket_name" {
  description = "S3 bucket used by Thanos for long-term metric blocks"
  value       = aws_s3_bucket.thanos.bucket
}
