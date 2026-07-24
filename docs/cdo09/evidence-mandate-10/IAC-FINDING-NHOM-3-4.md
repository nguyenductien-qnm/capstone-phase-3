# Chi tiết nhóm 3 và 4 — Checkov IaC finding

Nguồn: `checkov 3.3.8 -d terraform --framework terraform`, chạy 23/07/2026.
Tổng 119 fail / 637 pass. Phân nhóm: N1=11 · N2=21 · **N3=30** · **N4=57**

---

# NHÓM 3 — SỬA ĐƯỢC (30 finding)

## 3A. Sửa dễ, rủi ro thấp — làm trước (~1h, 16 finding)

### `CKV_AWS_226` (3x) — RDS chưa bật minor upgrade tự động
```
modules/rds/main.tf   aws_db_instance.this
modules/rds/main.tf   aws_db_instance.replica
modules/rds/main.tf   aws_db_instance.replica[0]
```
Sửa: `auto_minor_version_upgrade = true`
Rủi ro: AWS tự vá bản minor trong maintenance window. Nên bật.

### `CKV2_AWS_60` (3x) — RDS chưa copy tag sang snapshot
```
modules/rds/main.tf   aws_db_instance.this / replica / replica[0]
```
Sửa: `copy_tags_to_snapshot = true`
Rủi ro: không. Chỉ giúp snapshot có tag để truy nguồn.

### `CKV_AWS_293` (3x) — RDS chưa bật deletion protection
```
modules/rds/main.tf   aws_db_instance.this / replica / replica[0]
```
Sửa: `deletion_protection = true`
Rủi ro: sau này `terraform destroy` phải tắt tay trước. Với prod thì đó là tính năng
chứ không phải phiền — chặn xoá nhầm DB.

### `CKV_AWS_26` (3x) — SNS topic chưa mã hoá
```
modules/cloudtrail/main.tf              aws_sns_topic.mandate_12_audit
modules/cost_guard_automation/main.tf   aws_sns_topic.budget_alarms_80
modules/cost_guard_automation/main.tf   aws_sns_topic.budget_alarms_95
```
Sửa: `kms_master_key_id = "alias/aws/sns"` (key mặc định, không tốn thêm tiền)

### `CKV_AWS_7` (1x) — KMS key chưa bật xoay vòng
```
modules/msk/main.tf   aws_kms_key.msk
```
Sửa: `enable_key_rotation = true`

### `CKV2_AWS_12` (1x) — default security group chưa chặn hết
```
modules/vpc/main.tf   aws_vpc.this
```
Sửa: thêm `aws_default_security_group` với ingress/egress rỗng.

### `CKV_AWS_158` (3x) — CloudWatch log group chưa mã hoá KMS
```
audit-detection/modules/processor/lambda.tf   aws_cloudwatch_log_group
modules/cost_guard_automation/main.tf         aws_cloudwatch_log_group
modules/msk/main.tf                            aws_cloudwatch_log_group.msk
```
Sửa: thêm `kms_key_id`. **Tốn thêm tiền KMS** (~$1/key/tháng + phí request).
Cân nhắc: có thể đẩy sang nhóm 2 nếu muốn tiết kiệm.

## 3B. Sửa được nhưng cần cân nhắc (~14 finding)

### `CKV2_AWS_57` (6x) — Secrets Manager chưa xoay vòng tự động
```
audit-detection/modules/processor/secrets.tf   (1)
modules/elasticache/main.tf                    valkey secret
modules/msk/main.tf                            msk_credentials, msk_endpoint
modules/rds/main.tf                            db_credentials, db_endpoint
```
**Lưu ý**: RDS credentials ĐÃ có rotation (`aws_secretsmanager_secret_rotation`),
Checkov vẫn báo vì nó check trên resource `aws_secretsmanager_secret`. Có thể là
false positive — cần verify.
Secret endpoint (db_endpoint, msk_endpoint) chỉ chứa host:port, xoay vòng vô nghĩa.
→ Nhiều khả năng đẩy sang nhóm 1 (bỏ qua có lý do) sau khi xác minh.

### `CKV_AWS_149` (4x) — Secrets Manager dùng key mặc định thay vì CMK
```
modules/elasticache/main.tf   valkey secret
modules/msk/main.tf           msk_endpoint
modules/rds/main.tf           db_credentials, db_endpoint
```
Sửa: tạo CMK riêng + `kms_key_id`. Tốn ~$1/key/tháng.
Rủi ro trung bình: secret đang được ESO dùng, đổi key phải cấp thêm `kms:Decrypt`
cho role ESO (module external-secrets-irsa đã có sẵn cơ chế `kms_key_arns`).

### `CKV_AWS_37` (1x) — EKS chưa bật đủ log type
```
modules/eks/main.tf   aws_eks_cluster.this
```
Hiện có `enabled_cluster_log_types` nhưng thiếu vài loại. Bật đủ 5 loại
(api, audit, authenticator, controllerManager, scheduler) → tốn tiền CloudWatch.

### `CKV2_AWS_11` (1x) — VPC chưa bật flow log
```
modules/vpc/main.tf   aws_vpc.this
```
Sửa: thêm `aws_flow_log`. Tốn tiền lưu log, nhưng là bằng chứng tốt cho Auditability.

### `CKV_AWS_58` (1x) — EKS chưa bật secret encryption ⚠️
```
modules/eks/main.tf   aws_eks_cluster.this
```
Sửa: thêm block `encryption_config` với KMS key.
**RỦI RO CAO — đụng cluster prod đang chạy.** Bật encryption_config trên cluster
đã tồn tại là thao tác một chiều (không tắt lại được), và cần cluster hỗ trợ.
Cần cửa sổ bảo trì + backup etcd trước.

---

# NHÓM 4 — CẦN XEM TỪNG CÁI (57 finding)

## 4A. IAM — ưu tiên xem trước (17 finding)

### `CKV_AWS_274` (1x) — role dùng AdministratorAccess ⚠️ ĐÁNG LO NHẤT
```
bootstrap/develop/main.tf   aws_iam_role_policy_attachment.github_terraform_admin
```
Thực tế trong code:
```hcl
resource "aws_iam_role_policy_attachment" "github_terraform_admin" {
  role       = aws_iam_role.github_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
```
Đây là role mà GitHub Actions assume để chạy Terraform. Comment trong code đã giải
thích: Terraform dựng VPC/EKS/IAM/RDS/Valkey/MSK nên cần quyền rộng, và trust policy
giới hạn theo `environment:sandbox` của repo.

**Quyết định cần bạn chốt**: giữ AdministratorAccess (kèm lý do + trust policy hẹp),
hay thu hẹp thành policy liệt kê service? Thu hẹp là việc lớn, dễ vỡ khi thêm resource
mới, nhưng AdministratorAccess trên role CI là điểm mentor dễ chất vấn nhất.

### `CKV_AWS_356` (5x) — IAM policy dùng `*` làm resource
```
audit-detection/modules/detection-routing/sns.tf
audit-detection/modules/detection-routing/sqs.tf
modules/eks/karpenter.tf              karpenter_controller
modules/external-dns-irsa/main.tf     (2x)
```
Karpenter controller cần `*` cho `ec2:Describe*` — AWS không cho resource-level.
external-dns: có thể thu hẹp theo hosted zone ARN (module đã nhận `hosted_zone_id`).
→ Cần xem từng policy, một số thu hẹp được thật.

### `CKV_AWS_111` (3x) + `CKV_AWS_109` (3x) + `CKV_AWS_290` (1x) — write không ràng buộc
```
audit-detection/modules/detection-routing/sns.tf, sqs.tf
modules/eks/karpenter.tf
modules/cost_guard_automation/main.tf
```
Cùng nhóm với trên, xem chung một lượt.

### `CKV_AWS_355` (2x) — `*` cho read
```
ai-guardrails/main.tf                   techx_bedrock_invoke
modules/cost_guard_automation/main.tf
```
Bedrock invoke: model ARN có thể liệt kê được → thu hẹp được.

### `CKV_AWS_108` (1x) — data exfiltration
```
modules/eks/karpenter.tf   karpenter_controller
```

### `CKV_AWS_61` (1x) — assume role mọi service
```
ai-guardrails/main.tf   aws_iam_role.techx_bedrock_invoke
```

## 4B. Lambda — cost_guard + audit-detection (10 finding)

Cả 5 check đều dính đúng 2 lambda (`cost_guard`, `audit_processor`):

| Check | Nội dung | Đề xuất |
|---|---|---|
| `CKV_AWS_116` | thiếu Dead Letter Queue | **nên sửa** — mất message khi lambda lỗi |
| `CKV_AWS_173` | env var chưa mã hoá | nên sửa nếu env chứa dữ liệu nhạy cảm |
| `CKV_AWS_115` | chưa giới hạn concurrency | tuỳ — bảo vệ khỏi chạy tràn |
| `CKV_AWS_50` | chưa bật X-Ray | bỏ qua được, tốn tiền |
| `CKV_AWS_272` | chưa validate code signing | bỏ qua — quá mức cho lambda nội bộ |

## 4C. CloudFront (11 finding)

| Check | Nội dung | Đề xuất |
|---|---|---|
| `CKV_AWS_174` | TLS < 1.2 | **nên sửa** — đây là vấn đề thật |
| `CKV_AWS_86` | chưa bật access logging | nên sửa, tốn ít tiền S3 |
| `CKV2_AWS_32` | thiếu response headers policy | nên sửa — thêm security header |
| `CKV_AWS_305` | thiếu default root object | xem — storefront có thể cần |
| `CKV_AWS_374` | chưa giới hạn địa lý | bỏ qua — storefront phải public toàn cầu |
| `CKV_AWS_310` | chưa cấu hình origin failover | bỏ qua — chỉ 1 origin |

## 4D. S3 (7 finding)

| Check | Bucket | Đề xuất |
|---|---|---|
| `CKV_AWS_145` | terraform_state | **nên sửa** — state chứa thông tin nhạy cảm, dùng KMS |
| `CKV_AWS_18` | terraform_state, cloudtrail_logs | nên sửa — access logging |
| `CKV2_AWS_61` | terraform_state | nên sửa — lifecycle dọn version cũ |
| `CKV_AWS_300` | cloudtrail lifecycle | nên sửa — dọn multipart upload dở |
| `CKV2_AWS_62` | cả 2 bucket | bỏ qua — event notification không cần |

## 4E. Còn lại (12 finding)

| Check | Resource | Đề xuất |
|---|---|---|
| `CKV_AWS_129` (3x) | RDS log export | tốn tiền CloudWatch — cân nhắc |
| `CKV2_AWS_30` | RDS query logging | tốn tiền + ảnh hưởng hiệu năng |
| `CKV_AWS_161` | RDS IAM auth | **đụng app** — app đang dùng user/pass qua ESO |
| `CKV_AWS_339` | EKS version không hỗ trợ | **cần xem** — cluster đang 1.36, có thể false positive do Checkov cũ |
| `CKV_AWS_191` | ElastiCache chưa dùng CMK | tốn tiền KMS |
| `CKV_AWS_28` | DynamoDB point-in-time recovery | nên sửa, ít tiền |
| `CKV_AWS_119` | DynamoDB chưa dùng CMK | tốn tiền |
| `CKV2_AWS_64` | KMS key chưa có policy | nên sửa |
| `CKV_AWS_252` | CloudTrail chưa có SNS topic | bỏ qua — đã có EventBridge |
| `CKV2_AWS_10` | CloudTrail chưa tích hợp CloudWatch | **kiểm lại** — module có `cloudwatch_log_group_name`, có thể false positive |

---

# Tổng kết đề xuất

| Nhóm | Số | Hành động |
|---|---|---|
| 3A | 16 | Sửa ngay, rủi ro thấp (~1h) |
| 3B | 14 | Cân nhắc; `CKV2_AWS_57` nhiều khả năng false positive |
| 4A | 17 | Đọc từng policy — ưu tiên `CKV_AWS_274` |
| 4B-E | 40 | Phần lớn bỏ qua có lý do; ~10 cái nên sửa |

**Ước tính**: sửa thật ~25-30 finding, còn lại khai báo bỏ qua có lý do.

# Câu hỏi cần chốt

1. `CKV_AWS_274` — giữ AdministratorAccess cho role Terraform CI hay thu hẹp?
2. `CKV_AWS_58` — có làm EKS secret encryption không? Cần cửa sổ bảo trì.
3. Nhóm tốn tiền KMS (`CKV_AWS_149`, `CKV_AWS_158`, `CKV_AWS_191`, `CKV_AWS_119`)
   — sửa hay khai báo "ngoài ngân sách"?
4. `CKV_AWS_174` (TLS < 1.2 trên CloudFront) — cái này là vấn đề thật, sửa luôn chứ?
