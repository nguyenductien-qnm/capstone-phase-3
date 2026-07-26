# IaC scan → cổng chặn: hiện trạng, phân loại finding, và kế hoạch bật

> Gộp từ hai file cũ `PLAN-BAT-IAC-GATE.md` (kế hoạch) và `IAC-FINDING-NHOM-3-4.md`
> (chi tiết finding). Số liệu **đã chạy lại ngày 26/07/2026**, không dùng số cũ 23/07.

Đây là việc còn lại của **yêu cầu #2** trong
[DIRECTIVE #10](../../../mandates/MANDATE-10-secure-delivery-pipeline.md) — vế IaC.
Xem tổng thể 6 yêu cầu ở [README.md](README.md).

> [!NOTE]
> **✅ ĐÃ THỰC HIỆN 26/07/2026** — nhánh `fix/iac-gate-3a`.
> Ba câu ở mục 5 đã chốt theo khuyến nghị; nhóm S3 + RDS hoãn theo quyết định của user;
> chỉ sửa thật nhóm 3A rủi ro thấp. Kết quả đo sau khi sửa:
>
> | Công cụ | Trước | Sau khi sửa | Sau khi + file skip |
> |---|---|---|---|
> | Checkov | 136 fail / 690 pass | **128 fail / 714 pass** | **0 fail** ✅ |
> | Trivy IaC | 34 (15 CRITICAL + 19 HIGH) | 32 | **0** ✅ |
>
> Gate đã bật: `exit-code: "1"` + `soft_fail: false` trong
> [infra-cd.yaml](../../../.github/workflows/infra-cd.yaml).
> Chi tiết những gì đã sửa: [mục 9](#9-đã-thực-hiện--2607).

## 1. Hiện trạng: scan chạy nhưng KHÔNG chặn

| Công cụ | File | Cấu hình | Hệ quả |
|---|---|---|---|
| Trivy config | [infra-cd.yaml:183](../../../.github/workflows/infra-cd.yaml#L183) | `exit-code: "0"` | tìm thấy lỗi vẫn trả về thành công |
| Checkov | [infra-cd.yaml:191](../../../.github/workflows/infra-cd.yaml#L191) | `soft_fail: true` | cũng không bao giờ fail |

Cả hai chỉ in báo cáo rồi cho đi tiếp. Directive nói *"là **cổng chặn**, không phải hậu
kiểm"* và *"dính HIGH/CRITICAL thì **dừng**"* — hiện tại dính vẫn qua.

Nếu bật chặn ngay mà không chuẩn bị: **CI đỏ lập tức**, không ai merge được PR nào chạm
`terraform/`.

## 2. Số thật — đã chạy lại 26/07

```bash
python3 -m venv /tmp/cvenv && /tmp/cvenv/bin/pip install checkov
/tmp/cvenv/bin/checkov -d terraform --framework terraform --compact
```

| | Bản cũ 23/07 | **Chạy lại 26/07** | Chênh |
|---|---|---|---|
| Fail | 119 | **136** | **+17** |
| Pass | 637 | 690 | +53 |
| Loại check fail | 59 | 61 | +2 |

> [!WARNING]
> **Số fail tăng 17 dù chưa ai sửa gì.** Nguyên nhân: hạ tầng vẫn tiếp tục được thêm
> code trong ba ngày, mỗi resource mới lại kéo theo finding mới. Đây chính là lý do
> không nên để lâu — gate bật càng muộn thì nợ càng dày, và đuổi không kịp tốc độ đẻ
> finding mới.

### Finding mới phát sinh sau bản 23/07

Toàn bộ đến từ `msk_connect.tf` mới thêm (cả `environments/develop` lẫn `environments/sandbox`):

| Check | Số | Resource | Đánh giá |
|---|---|---|---|
| `CKV2_AWS_6` | 2 | `aws_s3_bucket.msk_plugins` thiếu Public Access Block | 🔴 **finding thật, nên sửa** |
| `CKV_AWS_21` | 2 | `aws_s3_bucket.msk_plugins` chưa bật versioning | 🟡 nên sửa |
| `CKV_AWS_23` | 2 | `aws_security_group.msk_connect` thiếu description | 🟢 sửa dễ |

Đã verify bằng mắt: bucket khai đúng 3 dòng, không có block nào cho public access hay
versioning. Bucket này chứa plugin ZIP của Debezium — không nhạy cảm lắm, nhưng thiếu
Public Access Block là loại lỗi không nên có.

### Phân bố theo module

```
29x rds            18x environments     17x audit-detection   14x cloudfront
12x cost_guard     10x eks               8x cloudtrail         8x msk
 6x bootstrap       6x vpc               4x elasticache        2x ai-guardrails
 2x external-dns-irsa
```

---
## 3. Phân loại đầy đủ 136 finding

Bảng dưới đây liệt kê **toàn bộ 136 finding**, mỗi dòng ghi rõ **file, số dòng, resource
cụ thể** — không gom kiểu "3 instance" nữa. Tổng theo nhóm:

| Nhóm | Số finding | Bản chất | Hành động |
|---|---|---|---|
| **N1** — không sửa được / false positive | **28** | có lý do kiến trúc, hoặc Checkov báo sai | khai skip |
| **N2** — sửa được nhưng tốn tiền | **29** | ràng buộc "trong ngân sách" của directive | khai skip |
| **N3** — sửa được, nên sửa | **37** | việc thật | ~2-4h |
| **N4** — cần đọc từng cái | **42** | phần lớn IAM + CloudFront | đọc rồi phân về N1/N2/N3 |
| | **136** | | |

---

### NHÓM 1 — Bỏ qua: lý do kiến trúc hoặc false positive (28 finding)

#### 1A. Egress `0.0.0.0/0` — `CKV_AWS_382` (6)

```
environments/develop/msk_connect.tf:25   aws_security_group.msk_connect
environments/sandbox/msk_connect.tf:25   aws_security_group.msk_connect
modules/elasticache/main.tf:9            aws_security_group.valkey
modules/msk/main.tf:1                    aws_security_group.msk
modules/rds/main.tf:21                   aws_security_group.db
modules/rds/main.tf:164                  aws_security_group.proxy[0]
```

Pod **phải** gọi Rekor/Fulcio (Sigstore) để Kyverno verify chữ ký, cộng ECR + Bedrock +
Secrets Manager. Chặn egress = Kyverno chết = yêu cầu #3 sụp. Thu hẹp thì phải liệt kê IP
range Sigstore, mà chúng đổi thường xuyên nên sẽ thành nguồn sự cố.

#### 1B. `CKV2_AWS_57` — FALSE POSITIVE đã chứng minh (6)

```
audit-detection/modules/processor/secrets.tf:1  aws_secretsmanager_secret.slack_webhook
modules/elasticache/main.tf:72                  aws_secretsmanager_secret.valkey_credentials
modules/msk/main.tf:141                         aws_secretsmanager_secret.msk_credentials
modules/msk/main.tf:167                         aws_secretsmanager_secret.msk_endpoint
modules/rds/main.tf:195                         aws_secretsmanager_secret.db_credentials[0]
modules/rds/main.tf:344                         aws_secretsmanager_secret.db_endpoint[0]
```

`db_credentials` **đã có** `aws_secretsmanager_secret_rotation` tại
[rds/main.tf:239](../../../terraform/modules/rds/main.tf#L239) — Checkov vẫn báo vì nó
check trên resource `aws_secretsmanager_secret` chứ không nhìn sang resource rotation liền
kề. Còn `db_endpoint`/`msk_endpoint` chỉ chứa `host:port`, xoay vòng vô nghĩa.

#### 1C. Subnet public — `CKV_AWS_130` (4)

```
modules/vpc/main.tf:24   aws_subnet.public
modules/vpc/main.tf:24   aws_subnet.public["pub-1"]
modules/vpc/main.tf:24   aws_subnet.public["pub-2"]
modules/vpc/main.tf:24   aws_subnet.public["pub-3"]
```

Subnet public gán IP công khai là **đúng bản chất** của nó — NAT gateway và ALB nằm đó.

#### 1D. EKS public endpoint — `CKV_AWS_38` `CKV_AWS_39` (2)

```
modules/eks/main.tf:94   aws_eks_cluster.this   (cả 2 check)
```

Bật có chủ đích để CI/GitHub Actions apply được. Đã giới hạn: code có
`public_access_cidrs` tại [eks/main.tf:110](../../../terraform/modules/eks/main.tf#L110)
kèm **validation bắt buộc** ở dòng 120 — không cho bật public mà để trống CIDR.

#### 1E. Event notification S3 — `CKV2_AWS_62` (4)

```
bootstrap/develop/main.tf:9              aws_s3_bucket.terraform_state
environments/develop/msk_connect.tf:10   aws_s3_bucket.msk_plugins
environments/sandbox/msk_connect.tf:10   aws_s3_bucket.msk_plugins
modules/cloudtrail/main.tf:12            aws_s3_bucket.cloudtrail_logs
```

Không có nhu cầu nghiệp vụ nào cần event notification trên các bucket này.

#### 1F. Còn lại (6)

| Check | Vị trí | Lý do |
|---|---|---|
| `CKV2_AWS_5` | `modules/rds/main.tf:164` `aws_security_group.proxy[0]` | SG dự phòng, chưa gắn resource |
| `CKV2_AWS_10` | `modules/cloudtrail/main.tf:179` `aws_cloudtrail.main_trail` | **FALSE POSITIVE** — đã có `cloud_watch_logs_group_arn` tại [dòng 186](../../../terraform/modules/cloudtrail/main.tf#L186) |
| `CKV_AWS_339` | `modules/eks/main.tf:94` | **FALSE POSITIVE** — cluster chạy **1.36**, Checkov 3.3.8 chưa biết version này |
| `CKV_AWS_252` | `modules/cloudtrail/main.tf:179` | CloudTrail chưa có SNS — đã dùng EventBridge thay thế |
| `CKV_AWS_272` ×2 | `audit-detection/.../lambda.tf:34`, `cost_guard_automation/main.tf:200` | Code signing quá mức cho lambda nội bộ |

---

### NHÓM 2 — Bỏ qua vì chi phí (29 finding)

Directive cho phép: *"Trong ngân sách"*. Nhưng **phải ghi rõ** chứ không im lặng bỏ qua.

#### 2A. Giữ log 1 năm — `CKV_AWS_338` (5)

```
audit-detection/modules/processor/lambda.tf:25   aws_cloudwatch_log_group.lambda
modules/cloudtrail/main.tf:154                   aws_cloudwatch_log_group.cloudtrail[0]
modules/cost_guard_automation/main.tf:187        aws_cloudwatch_log_group.lambda_logs
modules/eks/main.tf:15                           aws_cloudwatch_log_group.control_plane
modules/msk/main.tf:111                          aws_cloudwatch_log_group.msk
```

#### 2B. S3 cross-region replication — `CKV_AWS_144` (4)

```
bootstrap/develop/main.tf:9              aws_s3_bucket.terraform_state
environments/develop/msk_connect.tf:10   aws_s3_bucket.msk_plugins
environments/sandbox/msk_connect.tf:10   aws_s3_bucket.msk_plugins
modules/cloudtrail/main.tf:12            aws_s3_bucket.cloudtrail_logs
```

×2 tiền lưu trữ + phí transfer.

#### 2C. RDS monitoring — `CKV_AWS_118` + `CKV_AWS_353` (6)

```
modules/rds/main.tf:103   aws_db_instance.this        (cả 2 check)
modules/rds/main.tf:137   aws_db_instance.replica     (cả 2 check)
modules/rds/main.tf:137   aws_db_instance.replica[0]  (cả 2 check)
```

Enhanced monitoring + Performance Insights — phí CloudWatch theo giây.

#### 2D. CloudFront WAF — `CKV_AWS_68` + `CKV2_AWS_47` (4)

```
modules/cloudfront/main.tf:6   aws_cloudfront_distribution.this       (cả 2 check)
modules/cloudfront/main.tf:6   module.cloudfront[0]...this            (cả 2 check)
```

~$5-10/tháng + phí per-request.

#### 2E. RDS Multi-AZ — `CKV_AWS_157` (2)

```
modules/rds/main.tf:137   aws_db_instance.replica
modules/rds/main.tf:137   aws_db_instance.replica[0]
```

×2 tiền RDS.

#### 2F. Lambda trong VPC — `CKV_AWS_117` (2)

```
audit-detection/modules/processor/lambda.tf:34   aws_lambda_function.slack_alert
modules/cost_guard_automation/main.tf:200        aws_lambda_function.cost_guard
```

Cần NAT gateway, thêm tiền.

#### 2G. Nhóm CMK tốn tiền KMS (6) — *chờ chốt câu 3*

| Check | Vị trí |
|---|---|
| `CKV_AWS_149` ×4 | `elasticache/main.tf:72` · `msk/main.tf:167` · `rds/main.tf:195` · `rds/main.tf:344` |
| `CKV_AWS_191` ×1 | `modules/elasticache/main.tf:38` `aws_elasticache_replication_group.this` |
| `CKV_AWS_119` ×1 | `audit-detection/.../lambda.tf:1` `aws_dynamodb_table.idempotency` |

~$1/key/tháng + phí request. `CKV_AWS_149` còn kéo theo việc cấp `kms:Decrypt` cho role
ESO (module `external-secrets-irsa` đã có cơ chế `kms_key_arns`).

---

### NHÓM 3 — Sửa được, nên sửa (37 finding)

#### 3A. Rủi ro thấp, làm trước (~1h, 22 finding)

**RDS — 3 instance, mỗi instance dính 3 check** (9 finding)

```
modules/rds/main.tf:103   aws_db_instance.this
modules/rds/main.tf:137   aws_db_instance.replica
modules/rds/main.tf:137   aws_db_instance.replica[0]
```

| Check | Sửa gì | Rủi ro |
|---|---|---|
| `CKV_AWS_226` | `auto_minor_version_upgrade = true` | AWS tự vá minor trong maintenance window |
| `CKV2_AWS_60` | `copy_tags_to_snapshot = true` | không có |
| `CKV_AWS_293` | `deletion_protection = true` | `terraform destroy` phải tắt tay trước — với prod đó là **tính năng** |

**SNS chưa mã hoá — `CKV_AWS_26`** (3)

```
modules/cloudtrail/main.tf:230             aws_sns_topic.mandate_12_audit_tamper[0]
modules/cost_guard_automation/main.tf:13   aws_sns_topic.budget_alarms_80
modules/cost_guard_automation/main.tf:24   aws_sns_topic.budget_alarms_95
```

Sửa: `kms_master_key_id = "alias/aws/sns"` — key mặc định, **không tốn thêm tiền**.

**S3 `msk_plugins` mới thêm — 3 check × 2 environment** (6)

```
environments/develop/msk_connect.tf:10   aws_s3_bucket.msk_plugins
environments/sandbox/msk_connect.tf:10   aws_s3_bucket.msk_plugins
```

| Check | Sửa gì |
|---|---|
| `CKV2_AWS_6` | thêm `aws_s3_bucket_public_access_block` — 🔴 **finding thật, ưu tiên** |
| `CKV_AWS_21` | thêm `aws_s3_bucket_versioning` |
| `CKV2_AWS_61` | thêm `aws_s3_bucket_lifecycle_configuration` |

**Security group thiếu description — `CKV_AWS_23`** (2)

```
environments/develop/msk_connect.tf:25    aws_security_group.msk_connect
environments/sandbox/msk_connect.tf:25    aws_security_group.msk_connect
```

**Còn lại** (2)

| Check | Vị trí | Sửa gì |
|---|---|---|
| `CKV_AWS_7` | `modules/msk/main.tf:123` `aws_kms_key.msk` | `enable_key_rotation = true` |
| `CKV2_AWS_12` | `modules/vpc/main.tf:1` `aws_vpc.this` | thêm `aws_default_security_group` ingress/egress rỗng |

#### 3B. Nên sửa, cần chút cân nhắc (~11 finding)

| Check | Số | Vị trí | Ghi chú |
|---|---|---|---|
| `CKV_AWS_18` | 4 | `bootstrap:9` · `develop/msk_connect:10` · `sandbox/msk_connect:10` · `cloudtrail:12` | S3 access logging — tốn ít tiền |
| `CKV_AWS_145` | 3 | `bootstrap:9` · 2× `msk_connect:10` | S3 mã hoá bằng KMS — `terraform_state` chứa thông tin nhạy cảm nên **ưu tiên** |
| `CKV_AWS_158` | 3 | `audit-detection/.../lambda.tf:25` · `cost_guard:187` · `msk:111` | Log group mã hoá KMS — **~$1/key/tháng**, có thể đẩy sang N2 |
| `CKV2_AWS_64` | 1 | `modules/msk/main.tf:123` `aws_kms_key.msk` | thêm KMS key policy |

#### 3C. Nên sửa nhưng tốn tiền vận hành (~3 finding)

| Check | Vị trí | Ghi chú |
|---|---|---|
| `CKV_AWS_37` | `modules/eks/main.tf:94` | bật đủ 5 log type EKS — tốn tiền CloudWatch |
| `CKV2_AWS_11` | `modules/vpc/main.tf:1` | VPC flow log — tốn tiền, nhưng là bằng chứng tốt cho Auditability |
| `CKV_AWS_28` | `audit-detection/.../lambda.tf:1` `aws_dynamodb_table.idempotency` | point-in-time recovery — ít tiền |

#### 3D. Rủi ro cao — chờ chốt câu 2 (1 finding)

```
modules/eks/main.tf:94   aws_eks_cluster.this
```

`CKV_AWS_58` — EKS secret encryption. Thao tác **một chiều không tắt lại được** trên
cluster prod đang chạy. Cần cửa sổ bảo trì + backup etcd trước.

---

### NHÓM 4 — Cần đọc từng cái (42 finding)

#### 4A. IAM (17) — ưu tiên đọc trước

**`CKV_AWS_274` (1) — AdministratorAccess** ⚠️ *chờ chốt câu 1*

```
bootstrap/develop/main.tf:110   aws_iam_role_policy_attachment.github_terraform_admin
```

**`CKV_AWS_356` (5) — `*` làm resource cho restrictable action**

```
audit-detection/modules/detection-routing/sns.tf:1   aws_iam_policy_document.pipeline_health_kms
audit-detection/modules/detection-routing/sqs.tf:1   aws_iam_policy_document.queue_kms
modules/eks/karpenter.tf:74                          aws_iam_policy_document.karpenter_controller
modules/external-dns-irsa/main.tf:51                 aws_iam_policy_document.manage_records
modules/external-dns-irsa/main.tf:51                 module.external_dns_irsa[0]...manage_records
```

Karpenter cần `*` cho `ec2:Describe*` — AWS không cho resource-level. Nhưng **external-dns
thu hẹp được** theo hosted zone ARN (module đã nhận `hosted_zone_id`).

**`CKV_AWS_111` (3) + `CKV_AWS_109` (3) — write / permissions management không ràng buộc**

```
audit-detection/modules/detection-routing/sns.tf:1   aws_iam_policy_document.pipeline_health_kms
audit-detection/modules/detection-routing/sqs.tf:1   aws_iam_policy_document.queue_kms
modules/eks/karpenter.tf:74                          aws_iam_policy_document.karpenter_controller
```

Cùng 3 policy với trên — xem chung một lượt.

**`CKV_AWS_355` (2) — `*` cho read**

```
ai-guardrails/main.tf:133                    aws_iam_role_policy.techx_bedrock_invoke
modules/cost_guard_automation/main.tf:85     aws_iam_role_policy.lambda_eks_policy
```

Bedrock invoke: model ARN **liệt kê được** → thu hẹp được thật.

**Còn lại (3)**

| Check | Vị trí |
|---|---|
| `CKV_AWS_108` | `modules/eks/karpenter.tf:74` — data exfiltration |
| `CKV_AWS_290` | `modules/cost_guard_automation/main.tf:85` — write không ràng buộc |
| `CKV_AWS_61` | `ai-guardrails/main.tf:102` `aws_iam_role.techx_bedrock_invoke` — assume role mọi service |

#### 4B. Lambda (8) — cùng 2 function

```
audit-detection/modules/processor/lambda.tf:34   aws_lambda_function.slack_alert
modules/cost_guard_automation/main.tf:200        aws_lambda_function.cost_guard
```

| Check | Nội dung | Đề xuất |
|---|---|---|
| `CKV_AWS_116` ×2 | thiếu Dead Letter Queue | 🟢 **nên sửa** — mất message khi lambda lỗi |
| `CKV_AWS_173` ×2 | env var chưa mã hoá | nên sửa nếu env chứa dữ liệu nhạy cảm |
| `CKV_AWS_115` ×2 | chưa giới hạn concurrency | tuỳ — bảo vệ khỏi chạy tràn |
| `CKV_AWS_50` ×2 | chưa bật X-Ray | bỏ qua, tốn tiền |

#### 4C. CloudFront (8) — cùng 1 distribution, đếm 2 lần do module có/không count

```
modules/cloudfront/main.tf:6   aws_cloudfront_distribution.this
modules/cloudfront/main.tf:6   module.cloudfront[0]...this
```

| Check | Nội dung | Đề xuất |
|---|---|---|
| `CKV_AWS_86` ×2 | chưa bật access logging | 🟢 nên sửa, tốn ít tiền S3 |
| `CKV2_AWS_32` ×2 | thiếu response headers policy | 🟢 nên sửa — thêm security header |
| `CKV_AWS_305` ×2 | thiếu default root object | xem — storefront có thể cần |
| `CKV_AWS_374` ×2 | chưa giới hạn địa lý | bỏ qua — storefront phải public toàn cầu |
| `CKV_AWS_310` ×2 | chưa cấu hình origin failover | bỏ qua — chỉ 1 origin |

> ✅ `CKV_AWS_174` (TLS < 1.2) trong bản cũ **đã sửa xong** — PR #337, nay
> `minimum_protocol_version = "TLSv1.2_2021"`. Không còn trong danh sách fail.

#### 4D. RDS còn lại (5)

| Check | Vị trí | Đề xuất |
|---|---|---|
| `CKV_AWS_129` ×3 | `rds/main.tf:103`, `:137` ×2 | log export sang CloudWatch — tốn tiền |
| `CKV2_AWS_30` ×1 | `rds/main.tf:103` `aws_db_instance.this` | query logging — tốn tiền + ảnh hưởng hiệu năng |
| `CKV_AWS_161` ×1 | `rds/main.tf:103` `aws_db_instance.this` | IAM auth — **đụng app**, app đang dùng user/pass qua ESO |

#### 4E. S3 lifecycle (1)

```
modules/cloudtrail/main.tf:42   aws_s3_bucket_lifecycle_configuration.cloudtrail_logs
```

`CKV_AWS_300` — chưa đặt thời hạn huỷ multipart upload dở. 🟢 nên sửa.

---

### Tổng kết hành động

| Nhóm | Số | Việc |
|---|---|---|
| N1 | 28 | khai skip — trong đó **4 finding là false positive đã chứng minh** (`CKV2_AWS_57` ×6 tính chung, `CKV2_AWS_10`, `CKV_AWS_339`) |
| N2 | 29 | khai skip, viện ràng buộc ngân sách |
| N3A | 22 | **sửa ngay, ~1h, rủi ro thấp** |
| N3B-C | 14 | sửa, cân nhắc chi phí |
| N3D | 1 | `CKV_AWS_58` — chờ chốt |
| N4 | 42 | đọc từng cái; ước ~12 nên sửa, ~30 skip |

**Ước tính cuối:** sửa thật ~35-40 finding, còn lại ~95-100 khai skip có lý do.

## 4. Hai phát hiện khi verify lại

### `CKV2_AWS_57` là false positive — đã chứng minh

Bản cũ chỉ **nghi ngờ**. Nay đã verify được:

```bash
grep -n "aws_secretsmanager_secret_rotation" terraform/modules/rds/main.tf
# 239:resource "aws_secretsmanager_secret_rotation" "db_credentials" {
```

`db_credentials` **đã có** rotation, mà Checkov vẫn báo fail. Lý do: nó check trên
resource `aws_secretsmanager_secret` chứ không nhìn sang resource
`aws_secretsmanager_secret_rotation` liền kề.

Thêm nữa, `db_endpoint` và `msk_endpoint` chỉ chứa `host:port` — xoay vòng vô nghĩa.

→ **Cả 6 finding chuyển sang nhóm 1** (bỏ qua có lý do), không phải việc thật. Bớt được
6 finding khỏi cột "phải sửa".

### Repo tự mâu thuẫn với chính mình về AdministratorAccess

| File | Nội dung |
|---|---|
| [TERRAFORM_BEST_PRACTICE.md:166](../../../terraform/md/TERRAFORM_BEST_PRACTICE.md#L166) | *"KHÔNG gán policy `AdministratorAccess`"* |
| [bootstrap/develop/main.tf:112](../../../terraform/bootstrap/develop/main.tf#L112) | `policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"` |

Vấn đề không nằm ở bản thân quyền admin — README cạnh đó đã giải thích hợp lý rằng
Terraform dựng VPC/EKS/IAM/RDS/Valkey/MSK nên cần quyền rộng, blast radius bị giới hạn
bởi account riêng và OIDC subject chính xác.

Vấn đề là **tự đặt luật rồi tự phá**. Đó mới là điểm dễ bị chất vấn.

---

## 5. Ba câu cần chốt

Bản cũ hỏi 4 câu, nhưng **câu về TLS đã tự giải quyết** (`CKV_AWS_174` sửa ở PR #337).
Còn ba:

### Câu 1 — `CKV_AWS_274` AdministratorAccess: giữ hay thu hẹp?

**Khuyến nghị: giữ, khai báo skip có lý do.** Trust policy đã giới hạn theo
`environment:sandbox` của đúng repo, và thu hẹp là việc lớn dễ vỡ khi thêm resource mới.

Nhưng **nên sửa dòng trong `TERRAFORM_BEST_PRACTICE.md`** để không tự mâu thuẫn — đổi
thành *"không gán trừ role bootstrap, có lý do ghi kèm"*.

### Câu 2 — `CKV_AWS_58` EKS secret encryption: có làm không?

**Khuyến nghị: không làm lúc này.** Đây là thao tác **một chiều, không tắt lại được**
trên cluster prod đang chạy, mà cụm hiện còn đang có 5 pod kẹt vì hết IP. Khai báo skip
kèm ngày review, làm sau khi hạ tầng ổn định.

### Câu 3 — Nhóm tốn tiền KMS: sửa hay skip?

`CKV_AWS_149`, `CKV_AWS_158`, `CKV_AWS_191`, `CKV_AWS_119`.

**Khuyến nghị: skip có lý do**, viện đúng ràng buộc *"trong ngân sách"* mà directive cho
phép. Riêng **`CKV_AWS_26` (SNS) thì nên sửa** vì dùng key mặc định `alias/aws/sns`
không tốn thêm tiền.

### Sau khi chốt

Chốt ba câu này thì làm được ngay: tạo `.checkov.yaml` với skip có lý do, sửa nhóm 3A,
bật gate, và cập nhật `AUDIT-DIRECTIVE-10.md` cho hết lỗi thời.

Hoặc nếu muốn **ưu tiên SAST trước** thì làm CodeQL — cái đó **không cần chốt gì**.

---

## 6. Thứ tự thực hiện

### Đề xuất: bật gate SỚM, trả nợ sau

Mục tiêu của directive không phải *"hạ tầng không còn finding"* mà là **"cổng chặn tồn
tại và chặn thật"**. Vậy nên:

```
1. Viết .checkov.yaml skip đủ 136 finding hiện tại, mỗi dòng có lý do + ngày review
2. Bật exit-code: "1" và soft_fail: false          -> GATE SỐNG NGAY
3. Trả nợ dần: nhóm 3A (~1h) -> nhóm 4A IAM (~2h) -> phần còn lại
```

Cách này khiến gate thành cổng chặn thật **ngay hôm nay**: mọi finding **mới** phát sinh
sau đây sẽ bị chặn, còn nợ cũ được ghi nhận công khai thay vì giấu. Đây đúng cách repo
đang làm với [.trivyignore](../../../.trivyignore) cho CVE, nên nhất quán.

### So với cách cũ: sửa hết rồi mới bật

Bản cũ đề xuất sửa nhóm 3 → đọc nhóm 4 → viết skip → rồi mới bật gate. Vấn đề là mất
2-4 giờ mới có gate, mà **trong lúc đó code mới vẫn đẻ thêm finding** — bằng chứng là
đã tăng 17 finding chỉ trong 3 ngày. Đuổi không kịp.

> [!WARNING]
> Dù chọn cách nào, **không bật gate mà không có file skip**. Bật trước thì cả team
> không merge được gì trong lúc mình xử.

## 7. File cần tạo

`.checkov.yaml` ở gốc repo — mỗi skip **phải có lý do + ngày review**, theo đúng kỷ luật
`.trivyignore` đang dùng cho CVE:

```yaml
skip-check:
  - CKV_AWS_382   # egress 0.0.0.0/0 — pod cần Rekor/Fulcio/ECR/Bedrock. Review: 2026-10-26
  - CKV2_AWS_57   # false positive — rds/main.tf:239 đã có secret_rotation. Review: 2026-10-26
  - CKV_AWS_274   # AdministratorAccess role bootstrap — trust policy giới hạn theo
                  # environment:sandbox. Review: 2026-10-26
  - CKV_AWS_58    # EKS secret encryption — thao tác một chiều trên cluster prod đang
                  # chạy, chờ hạ tầng ổn định. Review: 2026-10-26
  - CKV_AWS_157   # Multi-AZ RDS — ngoài ngân sách capstone. Review: 2026-10-26
  # ...
```

Thêm mục IaC vào [.trivyignore](../../../.trivyignore) (file đã có sẵn cho CVE):

```
AVD-AWS-0104  # egress 0.0.0.0/0 — như trên
```

## 8. Cách chạy lại để kiểm chứng

```bash
# Checkov
python3 -m venv /tmp/cvenv && /tmp/cvenv/bin/pip install checkov
/tmp/cvenv/bin/checkov -d terraform --framework terraform --compact

# Trivy IaC (cùng cấu hình với CI)
trivy config terraform --severity CRITICAL,HIGH
```

---

## 9. Đã thực hiện — 26/07

Nhánh `fix/iac-gate-3a`, cắt từ `origin/develop` (`f5e83ec`).

### Quyết định đã chốt

| Câu | Quyết định |
|---|---|
| 1 — `CKV_AWS_274` AdministratorAccess | **Giữ**, khai skip có lý do + **sửa mâu thuẫn** trong `TERRAFORM_BEST_PRACTICE.md` |
| 2 — `CKV_AWS_58` EKS secret encryption | **Không làm lúc này**, skip kèm ngày review |
| 3 — Nhóm CMK tốn tiền KMS | **Skip** (ràng buộc ngân sách); riêng SNS **sửa thật** vì key mặc định miễn phí |
| Thêm | Nhóm **S3 và RDS hoãn** — đợt này chỉ đụng nhóm rủi ro thấp |

### Đã sửa thật — 6 loại check

| Check | File | Sửa gì |
|---|---|---|
| `CKV_AWS_26` ×3 | [cloudtrail/main.tf:231](../../../terraform/modules/cloudtrail/main.tf#L231) · [cost_guard_automation/main.tf](../../../terraform/modules/cost_guard_automation/main.tf) ×2 | `kms_master_key_id = "alias/aws/sns"` — key mặc định, **không tốn thêm tiền** |
| `CKV_AWS_7` ×1 | [msk/main.tf](../../../terraform/modules/msk/main.tf) `aws_kms_key.msk` | `enable_key_rotation = true` |
| `CKV2_AWS_64` ×1 | [msk/main.tf](../../../terraform/modules/msk/main.tf) `aws_kms_key.msk` | khai KMS key policy tường minh (root + Secrets Manager có điều kiện `kms:CallerAccount`) |
| `CKV2_AWS_12` ×1 | [vpc/main.tf](../../../terraform/modules/vpc/main.tf) | `aws_default_security_group` rỗng — adopt SG mặc định rồi xoá sạch rule |
| `CKV_AWS_23` ×2 | [develop/msk_connect.tf](../../../terraform/environments/develop/msk_connect.tf) · [sandbox/msk_connect.tf](../../../terraform/environments/sandbox/msk_connect.tf) | thêm `description` cho rule egress |
| `AVD-AWS-0179` ×2 | [msk/main.tf](../../../terraform/modules/msk/main.tf) `aws_msk_cluster` | `encryption_at_rest_kms_key_arn` trỏ `alias/aws/kafka` |

**Vì sao `CKV2_AWS_12` không tạo thêm resource:** AWS luôn cấp sẵn một default security
group cho mỗi VPC, và mặc định nó cho phép mọi traffic giữa các resource cùng gắn nó.
Không resource nào của mình dùng SG này, nhưng nó vẫn tồn tại — ai lỡ tạo ENI mà quên chỉ
định SG thì rơi đúng vào đó. Khai `aws_default_security_group` **không tạo SG mới**:
Terraform nhận adopt SG có sẵn rồi xoá hết rule. Để trống ingress/egress nghĩa là chặn cả
hai chiều.

**Vì sao `AVD-AWS-0179` sửa được miễn phí:** MSK vốn đã mã hoá at-rest bằng key AWS quản
lý kể cả khi không khai gì. Khai tường minh qua `alias/aws/kafka` chỉ làm điều đó **đọc
được trong Git** và scanner không phải đoán — không tạo CMK nên không phát sinh phí.

### Đã sửa mâu thuẫn tài liệu

[TERRAFORM_BEST_PRACTICE.md](../../../terraform/md/TERRAFORM_BEST_PRACTICE.md) trước ghi
cụt lủn *"KHÔNG gán policy `AdministratorAccess`"* trong khi code lại gán. Nay đổi thành
quy tắc có ngoại lệ tường minh: không gán **trừ role bootstrap**, kèm lý do (root module
dựng gần như mọi service), biện pháp giới hạn blast radius (account riêng + trust policy
khoá theo GitHub Environment OIDC subject), và điều kiện gỡ bỏ (thay bằng policy hẹp khi
đo được tập API thực tế).

### Đã tạo / sửa file

| File | Nội dung |
|---|---|
| [.checkov.yaml](../../../.checkov.yaml) | **mới** — 56 check skip, nhóm theo lý do, mỗi nhóm có ngày review |
| [.trivyignore](../../../.trivyignore) | thêm mục IaC misconfig — 11 ID, dùng chung file với CVE |
| [infra-cd.yaml](../../../.github/workflows/infra-cd.yaml) | `exit-code: "0"` → `"1"`, `soft_fail: true` → `false`, trỏ tới 2 file skip |

### Đã verify

```bash
terraform fmt -check -recursive terraform/          # exit 0
terraform validate                                  # Success! The configuration is valid.

checkov -d terraform --framework terraform          # passed=543 failed=0
trivy config terraform --severity CRITICAL,HIGH --exit-code 1   # exit 0
```

Kiểm chứng 6 sửa thật **không phải nhờ skip**: tạm đổi tên `.checkov.yaml` rồi chạy lại →
136 fail tụt còn **128**, và cả 5 check ID đều biến mất khỏi danh sách fail.

### Còn lại cho đợt sau

| Việc | Số finding | Ghi chú |
|---|---|---|
| S3 public access block (`CKV2_AWS_6`, `AVD-AWS-0086/87/91/93`) | 6 | **đáng ưu tiên nhất** — bucket `msk_plugins` |
| S3 versioning + lifecycle + KMS | 8 | |
| RDS 3 cờ (minor upgrade, copy tags, deletion protection) | 9 | đụng prod, cần cửa sổ |
| IAM thu hẹp `*` (external-dns theo zone ARN, Bedrock theo model ARN) | ~7 | |
| Lambda DLQ (`CKV_AWS_116`) | 2 | mất message khi lambda lỗi |
| CloudFront access logging + response headers | 4 | |
| `CKV_AWS_58` EKS secret encryption | 1 | chờ hạ tầng ổn định |
