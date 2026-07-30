# Raw evidence logs

Lưu output CLI đã redact ở đây với tên tương ứng ảnh, ví dụ:

```text
01-terraform-validate.txt
02-terraform-plan.txt
03-eks-audit-enabled.json
04-cloudwatch-audit-stream.json
05-k8s-forensic-timeline.json
06-cloudtrail-status.json
07-cloudtrail-user-identity.json
08-s3-versioning.json
08-s3-encryption.json
08-s3-public-access-block.json
09-cloudtrail-validation.txt
11-argocd-revision.txt
12-operator-policy-simulation.json
```

Không lưu credential, token, secret hoặc nội dung `terraform.tfvars`. Giữ raw output đủ để mentor đối chiếu ảnh nhưng redact account-sensitive fields không cần thiết.
