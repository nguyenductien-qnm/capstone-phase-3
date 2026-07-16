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

# Lifecycle Policy cho ECR để dọn dẹp ảnh cũ, tối ưu chi phí lưu trữ
resource "aws_ecr_lifecycle_policy" "this" {
  for_each = toset(var.ecr_repositories)

  repository = aws_ecr_repository.this[each.key].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Chi giu lai toi da 100 images de tiet kiem chi phi"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 100
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
