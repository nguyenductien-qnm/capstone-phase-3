# Cost Guard Automation Configuration
# Generated based on cost_guard.auto.tfvars.example

# ============ Cost Guard Automation ============

# Hotfix 2026-07-31: disable Cost Guard Automation. Its partial scale-down
# changed the HA primary MNG from 3 nodes to 1 and stranded zonal Thanos PVCs.
enable_cost_guard_automation = false

# Budget configuration
# If budget_periods is set, these weekly periods will be used instead of a monthly budget.
budget_limit = 300

# Email addresses for budget alerts
# 80% threshold: Gửi cảnh báo warning + scale down 50%
# 95% threshold: Gửi cảnh báo CRITICAL + stop/scale down 100%
budget_alert_email_80 = "nguyenkhang.28102004@gmail.com"
budget_alert_email_95 = "ndtien317@gmail.com"

# Custom weekly budget periods
budget_periods = [
  {
    name       = "week-27-31-jul"
    start_date = "2026-07-27_00:00"
    end_date   = "2026-07-31_23:59"
    amount     = 300
  }
]

# Lambda configuration (optional - defaults are usually fine)
lambda_timeout                = 300 # seconds
lambda_memory                 = 512 # MB
cloudwatch_log_retention_days = 14  # days
