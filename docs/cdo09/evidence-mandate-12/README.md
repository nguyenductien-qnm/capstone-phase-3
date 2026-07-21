# MANDATE-12 evidence workspace

Thư mục này chứa evidence thực tế cho Mandate-12 Audit Anti-Defeat. Không tạo ảnh giả, không sửa output để biến `PENDING`/`FAIL` thành `PASS`, và không lưu access key, token, secret, email cá nhân hoặc nội dung `terraform.tfvars`.

## Cấu trúc

```text
evidence-mandate-12/
├── README.md                 # Quy tắc capture evidence
├── mandate-12.md             # Evidence pack nộp mentor
├── EVIDENCE-INDEX.md         # Acceptance → evidence path
├── RUN-RESULTS.md            # Kết quả runtime và blocker
├── logs/                     # Raw CLI/workflow output đã redact
└── screenshots/              # Ảnh do owner tự chụp và redact
```

## Quy tắc trạng thái

- `PASS`: control đã deploy, runtime check thành công và raw evidence thật đã được lưu.
- `PARTIAL`: một phần control đã verify hoặc chỉ có evidence lịch sử/chưa capture đủ.
- `PENDING`: code đã có nhưng chưa merge/apply hoặc chưa chạy runtime check.
- `BLOCKED`: không thể tiếp tục nếu thiếu quyền, approval, secret hoặc external action.
- File evidence tồn tại không tự động làm acceptance thành `PASS`.

## Quy tắc đặt tên

Raw output:

```text
logs/01-terraform-ci-plan.txt
logs/02-cloudtrail-baseline.json
logs/03-iam-policy-attachments.json
logs/04-iam-explicit-deny.json
logs/05-cloudtrail-advanced-selectors.json
logs/06-s3-getobject-event.json
logs/07-m12-eventbridge-sns.json
logs/08-sns-subscription.txt
logs/09-cloudtrail-validation.txt
logs/10-pr-jira-ci.txt
```

Screenshot dùng cùng prefix, ví dụ `screenshots/04-iam-explicit-deny.png`.

## Redaction

- Che AWS account ID đầy đủ khi mentor không yêu cầu.
- Không che role name, policy name, action, `EvalDecision`, resource name, timestamp hoặc event ID cần cho attribution.
- Không commit email receiver, GitHub secret, AWS credential, session token hoặc nội dung tfvars.
- Ảnh IAM role chỉ chứng minh effective attachment trên generated role. Bằng chứng Permission Set ownership phải đến từ IAM Identity Center/adminHolder.

## Điều kiện hoàn thành

- IAM CDO và Mentor đều có policy và simulator trả `explicitDeny`.
- CloudTrail có management selector và S3 read data selector đúng hai bucket.
- Một lần đọc S3 thật tạo `GetObject` data event.
- EventBridge rule/SNS topic tồn tại, subscription đã confirm và đường email đã kiểm tra an toàn.
- `validate-logs` thành công trên interval được ghi rõ.
- PR, reviewer, workflow plan/apply và Jira được liên kết.
