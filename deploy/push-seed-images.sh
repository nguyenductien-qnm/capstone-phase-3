#!/usr/bin/env bash
# Script tự động login và đẩy 18 images seed của BTC lên ECR của TF.
set -euo pipefail

REG="265808836805.dkr.ecr.us-east-1.amazonaws.com/techx-corp"
REGION="us-east-1"

echo "1. Đăng nhập Docker vào ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REG"

echo "2. Bắt đầu kéo, đổi tag và đẩy 18 images lên ECR..."
services=(
  accounting
  ad
  cart
  checkout
  currency
  email
  fraud-detection
  frontend
  frontend-proxy
  image-provider
  kafka
  llm
  load-generator
  payment
  product-catalog
  product-reviews
  quote
  recommendation
  shipping
)

for s in "${services[@]}"; do
  echo "----------------------------------------"
  echo "Processing service: $s"
  echo "Pulling nghiadaulau/techx-corp:1.0-$s (amd64)..."
  docker pull --platform linux/amd64 "nghiadaulau/techx-corp:1.0-$s"
  
  echo "Tagging as $REG:1.0-$s..."
  docker tag "nghiadaulau/techx-corp:1.0-$s" "$REG:1.0-$s"
  
  echo "Pushing to ECR..."
  docker push "$REG:1.0-$s"
done

if [ -d "techx-corp-platform/src/shipping" ]; then
  echo "----------------------------------------"
  echo "Phát hiện mã nguồn shipping (Rust). Tiến hành biên dịch amd64 chuẩn từ nguồn..."
  docker buildx build --platform linux/amd64 -t "$REG:1.0-shipping" -f techx-corp-platform/src/shipping/Dockerfile --push techx-corp-platform
fi

echo "----------------------------------------"
echo "Đã đẩy thành công tất cả 18 images lên ECR!"
