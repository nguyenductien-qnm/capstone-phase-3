# Node subnet /20 cho Karpenter — thay dải /24 app đã cạn khối /28 liền mạch.
#
# Bối cảnh (đo 26-27/07/2026, chi tiết trong PR):
#   - VPC CNI bật prefix delegation (WARM_PREFIX_TARGET=1): mỗi node xin khối
#     /28 liền mạch; /24 chỉ có 16 khối, mỗi node ăn 2-3 khối -> trần ~5 node/AZ.
#   - Khối /28 trống đo thực tế: app-1 (1a) = 12/16, app-2 (1b) = 1/16,
#     app-3 (1c) = 2/16. CloudTrail 26/07: 1250 lỗi InsufficientCidrBlocks,
#     toàn bộ từ node ở 1b/1c; node ip-10-0-12-7 (1b) chết NetworkNotReady.
#   - /20 = 256 khối /28 — trần IP không còn là ràng buộc; trần thực tế chuyển
#     về NodePool limits (cpu 16 + 8 ≈ 12 node large). Cùng cỡ giải pháp TF2.
#
# Dải chọn không đè CIDR nào đang dùng trong 10.0.0.0/16
# (đang dùng: 10.0.1-3, 10.0.11-13, 10.0.21-22, 10.0.31-32).
private_node_subnets = {
  "node-1a" = {
    cidr_block        = "10.0.48.0/20"
    availability_zone = "us-east-1a"
  }
  "node-1b" = {
    cidr_block        = "10.0.64.0/20"
    availability_zone = "us-east-1b"
  }
  "node-1c" = {
    cidr_block        = "10.0.80.0/20"
    availability_zone = "us-east-1c"
  }
}
