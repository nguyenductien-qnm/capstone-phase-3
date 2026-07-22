# Cost Guard Automation Configuration
# Generated based on cost_guard.auto.tfvars.example

# ============ Cost Guard Automation ============

# Enable the Cost Guard Automation module
enable_cost_guard_automation = true

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
    name       = "week-13-19-jul"
    start_date = "2026-07-13_00:00"
    end_date   = "2026-07-19_23:59"
    amount     = 300
  },
  {
    name       = "week-20-26-jul"
    start_date = "2026-07-20_00:00"
    end_date   = "2026-07-26_23:59"
    amount     = 300
  },
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
