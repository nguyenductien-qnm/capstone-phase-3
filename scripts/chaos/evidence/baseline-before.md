# M17 Baseline — BEFORE (evidence)

Thu 2026-07-21T12:18:55Z · cluster `ecommerce-dev-eks` · ns `techx-tf1` · profile Phase3-CDO-PermissionSet-804372444787

## R2 — Multi-AZ (GAP)
Node→AZ: 10-0-12-x = us-east-1b · 10-0-13-x = us-east-1c (hiện 0 node ở 1a; 2×1b, 5×1c).
- cart: 2 pod ĐỀU us-east-1c ❌ (mất 1c = sập cả 2)
- frontend: 2 pod ĐỀU us-east-1c ❌
- checkout: 1b + 1c ✓
- product-catalog: 1b + 1c ✓
- currency / payment / shipping: **1 replica** ❌ SPOF khi mất AZ

## R4 — least-privilege token (GAP)
- frontend / cart / checkout: automountServiceAccountToken = unset (default TRUE) ❌

## R3 — NetworkPolicy (GAP)
- techx-tf1: **0 NetworkPolicy**
- VPC CNI enforcement: aws-eks-nodeagent `--enable-network-policy=false` ❌
  → NetworkPolicy sẽ CHỈ trang trí nếu deploy mà không bật enforcement trước.

## Kết luận
3/3 gap R2/R3/R4 hiện hữu, có bằng chứng. R1 (frontend circuit breaker) chưa deploy (image chưa build).
