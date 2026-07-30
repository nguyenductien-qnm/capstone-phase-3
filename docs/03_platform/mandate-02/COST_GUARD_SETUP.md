# Cost Guard Automation Configuration Guide

## Setup Instructions

### 1. Thêm variables vào tfvars file

Thêm các dòng sau vào file `environments/sandbox/terraform.tfvars` hoặc `environments/sandbox/cost_guard.auto.tfvars`:

```hcl
# ============ Cost Guard Automation ============

enable_cost_guard_automation = true

# Budget configuration
# Mỗi tuần 1 budget với $300 cho giai đoạn 13-19, 20-26, 27-31 tháng 7
budget_limit = 300

# Email cảnh báo
budget_alert_email_80  = "nguyenkhang.28102004@gmail.com"
budget_alert_email_95  = "ndtien317@gmail.com"

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

# Lambda tuning (optional)
cost_guard_lambda_timeout     = 300
cost_guard_lambda_memory      = 512
cost_guard_log_retention_days = 14
```

### 2. Email Subscription Confirmation

Sau khi apply Terraform:
1. Hai email sẽ nhận được AWS SNS subscription confirmation
2. **PHẢI CLICK** link "Confirm subscription" trong email
3. Chỉ sau khi confirm, các cảnh báo mới được gửi

### 3. Validate Terraform

```bash
cd environments/sandbox

# Kiểm tra syntax
terraform validate

# Preview changes
terraform plan -var-file="terraform.tfvars"
```

### 4. Deploy

```bash
cd environments/sandbox

# Apply changes
terraform apply -var-file="terraform.tfvars"

# Capture outputs
terraform output -json > cost_guard_outputs.json
```

## Understanding the Alerts

### 80% Threshold Alert
```
Subject: AWS Budget Alarm: 80% Threshold Exceeded
To: nguyenkhang.28102004@gmail.com

Message:
Your forecasted AWS spending will exceed 80% of your $1000 budget limit.

Actions Taken:
- EKS: Scale down node groups to 50% capacity
- Auto Scaling Groups: Set desired capacity to 50%
```

### 95% Threshold Alert (CRITICAL)
```
Subject: CRITICAL Budget Alert: 95% Threshold Exceeded
To: ndtien317@gmail.com

Message:
Your forecasted AWS spending will exceed 95% of your $1000 budget limit.
Scaling down ALL resources.

Actions Taken:
- EKS: Scale down all node groups to 0
- RDS: Stop all database instances
- ElastiCache: Reduce replica count
- EC2: Stop all instances with AutoStop=true tag
- Auto Scaling Groups: Scale down to 0
```

## Manual Testing

### Test SNS Integration

```bash
# Find SNS topic ARN
SNS_TOPIC_ARN=$(aws sns list-topics | jq -r '.Topics[] | select(.TopicArn | contains("cost-guard")) | .TopicArn')

# Send test message
aws sns publish \
  --topic-arn "$SNS_TOPIC_ARN" \
  --subject "Test Alert - 95% Threshold" \
  --message "CRITICAL Budget Alert: Your forecasted AWS spending will exceed 95% of your budget limit."
```

### Check Lambda Logs

```bash
# View recent logs
aws logs tail /aws/lambda/capstone-sandbox-cost-guard --follow

# View specific time range
aws logs filter-log-events \
  --log-group-name "/aws/lambda/capstone-sandbox-cost-guard" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### Check Budget Alarms

```bash
# List budgets
aws budgets describe-budgets --account-id $(aws sts get-caller-identity --query Account --output text) --budget-type COST

# Get specific budget
aws budgets describe-budget --account-id $(aws sts get-caller-identity --query Account --output text) --budget-name "capstone-sandbox-cost-guard-80-percent"
```

## Troubleshooting

### Emails không được gửi?
1. Confirm SNS subscriptions trên mailbox
2. Check SNS topic policy: `aws sns get-topic-attributes --topic-arn <ARN> --attribute-names Policy`
3. Check Lambda logs: `aws logs tail /aws/lambda/capstone-sandbox-cost-guard --follow`

### Lambda không trigger?
1. Verify SNS -> Lambda permission: `aws sns get-topic-attributes --topic-arn <ARN>`
2. Check Lambda IAM role permissions
3. Test SNS manually (xem "Manual Testing" ở trên)

### Resources không scale down?
1. Check Lambda logs để xem specific error
2. Verify RDS/EKS/EC2 instance names đúng
3. Ensure Lambda IAM role có permissions

## Cost of This Module

| Service | Cost |
|---------|------|
| AWS Budget | Free |
| SNS Notifications | ~$0.50/million messages |
| Lambda | ~$0.20/1M invocations |
| CloudWatch Logs | ~$0.50/GB |
| **Total/month** | **~$1-2 USD** |

## Safety Notes

⚠️ **IMPORTANT**: Module này sẽ **automatically stop/scale down resources** khi budget threshold đạt:
- 80%: Partial scale down (50%)
- 95%: Full shutdown

Để tránh service disruption:
1. Set `enable_cost_guard_automation = false` nếu không muốn
2. Adjust `budget_limit` để phù hợp với expected spending
3. Test trên non-production environment trước

## Next Steps

1. ✅ Terraform apply
2. ✅ Confirm SNS email subscriptions
3. ✅ Test với SNS manual publish
4. ✅ Monitor CloudWatch logs
5. ✅ Setup additional monitors/alerts nếu cần

## References

- [AWS Budget Alarms](https://docs.aws.amazon.com/awsaccountmanagement/latest/userguide/budgets-create-alerts.html)
- [AWS Lambda Cost Optimization](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html)
- [SNS Topics](https://docs.aws.amazon.com/sns/latest/dg/sns-create-topic.html)
