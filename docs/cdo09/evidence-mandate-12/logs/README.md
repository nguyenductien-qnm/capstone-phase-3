# MANDATE-12 raw evidence logs

Lưu output CLI/GitHub Actions thật đã redact tại đây:

```text
01-terraform-ci-plan.txt
02-cloudtrail-baseline.json
03-iam-policy-attachments.json
04-iam-explicit-deny.json
05-cloudtrail-advanced-selectors.json
06-s3-getobject-event.json
07-m12-eventbridge-sns.json
08-sns-subscription.txt
09-cloudtrail-validation.txt
10-pr-jira-ci.txt
```

Không lưu credential, token, email cá nhân, GitHub secret hoặc nội dung `terraform.tfvars`. Giữ action name, role/policy name, decision, resource, timestamp và event ID cần để mentor kiểm tra.

Không tự viết output mẫu vào file raw evidence. Chỉ lưu kết quả được capture từ CLI, AWS Console hoặc workflow thật.
