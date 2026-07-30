# CloudTrail ghi data event (đọc/ghi object) cho đúng 2 bucket nhạy cảm này.
# 29/07/2026: bucket state đổi tên theo account mới — "terraform-state-phase-3"
# (account 804372444787 đã destroy) -> "terraform-state-phase3-tf1" khớp backend
# khai ở providers.tf. Để tên cũ thì CloudTrail canh một bucket không tồn tại,
# tức mất dấu vết mọi thao tác lên file state — đúng thứ cần canh nhất.
# Bucket cloudtrail-logs giữ nguyên tên vì Terraform tự tạo theo
# "${project_name}-${environment}-cloudtrail-logs" = ecommerce-dev-cloudtrail-logs.
cloudtrail_s3_data_event_bucket_arns = [
  "arn:aws:s3:::ecommerce-dev-cloudtrail-logs/",
  "arn:aws:s3:::terraform-state-phase3-tf1/"
]

enable_mandate_12_alert = true
