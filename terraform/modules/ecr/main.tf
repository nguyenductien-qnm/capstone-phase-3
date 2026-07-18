# ECR Repositories cho các microservices
resource "aws_ecr_repository" "this" {
  for_each = toset(var.ecr_repositories)

  name                 = "${var.project_name}-${var.environment}-${each.key}"
  image_tag_mutability = var.image_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS" # Sử dụng KMS key mặc định của ECR để mã hóa ảnh
  }

  # Ngăn chặn việc xóa ECR khi chạy lệnh destroy để bảo vệ các docker image đã build
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-${each.key}"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lifecycle Policy cho ECR để dọn dẹp ảnh cũ, tối ưu chi phí lưu trữ.
# CHÚ Ý (incident 2026-07-16): tagStatus="any" + imageCountMoreThan từng xóa cả
# image ĐANG DEPLOY (repo >100 ảnh -> mất 7 tag đang chạy, email/cart/aiops-detector
# chết ImagePullBackOff). Chỉ được expire ảnh UNTAGGED — ảnh có tag là ảnh còn
# được tham chiếu (deploy hoặc cosign .sig), không bao giờ tự xóa theo số lượng.
resource "aws_ecr_lifecycle_policy" "this" {
  for_each = toset(var.ecr_repositories)

  repository = aws_ecr_repository.this[each.key].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire UNTAGGED images only, 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
