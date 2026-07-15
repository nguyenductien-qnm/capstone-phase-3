# Sandbox demonstration schedule: keep two primary nodes as the baseline,
# pre-scale to three nodes daily, then return to the baseline two hours later.
resource "aws_autoscaling_schedule" "primary_scale_up" {
  scheduled_action_name  = "${var.project_name}-${var.environment}-eks-primary-scale-up"
  autoscaling_group_name = module.eks.primary_autoscaling_group_name

  min_size         = 2
  max_size         = 3
  desired_capacity = 3
  recurrence       = "40 11 * * *"
  time_zone        = "Asia/Ho_Chi_Minh"
}

resource "aws_autoscaling_schedule" "primary_scale_down" {
  scheduled_action_name  = "${var.project_name}-${var.environment}-eks-primary-scale-down"
  autoscaling_group_name = module.eks.primary_autoscaling_group_name

  min_size         = 2
  max_size         = 3
  desired_capacity = 2
  recurrence       = "40 13 * * *"
  time_zone        = "Asia/Ho_Chi_Minh"
}
