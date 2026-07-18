# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# ------------------------------------------------------------------ #
# IAM Role and Policies for EKS AI Services (shopping-copilot & reviews)
# ------------------------------------------------------------------ #

# IAM Role assumed by EKS Pod Identity Agent for AI services
resource "aws_iam_role" "shopping_copilot_bedrock" {
  name = "shopping-copilot-bedrock-role"

  # Trust policy permitting EKS Pod Identity Service to assume this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name        = "shopping-copilot-bedrock-role"
    Environment = var.environment
  }
}

# Policy allowing the EKS Pod IAM Role to assume the target Bedrock Role in Account B
resource "aws_iam_role_policy" "shopping_copilot_bedrock" {
  name = "ShoppingCopilotBedrockAccess"
  role = aws_iam_role.shopping_copilot_bedrock.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AssumeCrossAccountBedrockRole"
        Effect = "Allow"
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
        Resource = "arn:aws:iam::384511757667:role/techx-bedrock-invoke"
      }
    ]
  })
}

# ------------------------------------------------------------------ #
# EKS Pod Identity Associations
# ------------------------------------------------------------------ #

# EKS Pod Identity Association for shopping-copilot
resource "aws_eks_pod_identity_association" "shopping_copilot" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "techx-tf1"
  service_account = "shopping-copilot"
  role_arn        = aws_iam_role.shopping_copilot_bedrock.arn
}

# EKS Pod Identity Association for product-reviews
resource "aws_eks_pod_identity_association" "product_reviews" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "techx-tf1"
  service_account = "product-reviews"
  role_arn        = aws_iam_role.shopping_copilot_bedrock.arn
}
