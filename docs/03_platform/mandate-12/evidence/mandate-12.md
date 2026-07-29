# MANDATE-12 Evidence Pack

- **Owner:** CDO-09
- **Môi trường:** Sandbox/Product-like
- **Region:** `us-east-1`
- **CloudTrail:** `ecommerce-dev-audit-trail`
- **Scope:** chống làm mù, làm hụt và làm giả audit evidence.

> Trạng thái dưới đây phản ánh kiểm tra gần nhất ngày 21/07/2026 sau protected apply và runtime verification.

## Evidence Matrix

| ID | Đòn tấn công / acceptance | Control | Trạng thái gần nhất |
|---|---|---|---|
| 01 | Change được review trước deploy | Terraform static checks, GitHub plan/apply | **PASS:** workflow thành công; plan/apply `5 add, 1 change, 0 destroy` |
| 02 | Baseline trail còn logging và validation enabled | Multi-region CloudTrail, KMS, CloudWatch, log-file validation | **PASS** |
| 03 | CDO/Mentor nhận preventive policy | Identity Center Permission Sets → generated SSO roles | **PASS enforcement:** policy có 2 attachments trên đúng hai roles; Permission Set ownership do adminHolder xác nhận |
| 04 | Routine operators không làm mù audit | IAM Simulator cho `StopLogging`, `DeleteTrail`, `PutEventSelectors` | **PASS:** cả hai role trả `explicitDeny` |
| 05 | S3 read coverage không bị làm hụt | Advanced Event Selectors cho hai bucket | **PASS** |
| 06 | S3 read thực sự để lại dấu vết | `GetObject` data event trong CloudTrail/CloudWatch | **PASS** |
| 07 | Detective backup độc lập | EventBridge rule riêng → SNS topic riêng | **PASS** |
| 08 | Người nhận thực sự nhận được cảnh báo | SNS subscription confirmed và safe delivery test | **PASS** |
| 09 | Log bị sửa/chèn/xóa có thể bị phát hiện | CloudTrail digest chain và `validate-logs` | **PASS:** 2/2 digest và 85/85 log files hợp lệ |
| 10 | Change trail đầy đủ | PR, reviewer, workflow run, plan/apply, Jira | **PASS:** PR #236 approved/merged; Jira CDO-202; workflow run 29818863006 thành công |

- Chi tiết đường dẫn evidence: [EVIDENCE-INDEX.md](EVIDENCE-INDEX.md).
- Kết quả runtime và blocker: [RUN-RESULTS.md](RUN-RESULTS.md).

## Ba vấn đề Mandate-12

### 1. Làm mù

Preventive control là explicit deny được adminHolder quản lý tại CDO/Mentor IAM Identity Center Permission Sets. Detective backup là EventBridge/SNS email riêng của Mandate-12.

Runtime đã chứng minh deny effective trên hai generated roles. EventBridge/SNS riêng của Mandate-12 đã deploy và safe email delivery đã PASS.

### 2. Làm hụt

Management events tiếp tục ghi Secrets Manager API calls như `GetSecretValue`. Terraform bổ sung read-only S3 object data events, giới hạn vào CloudTrail log bucket và Terraform state bucket.

AWS runtime hiện có management selector và S3 read data selector cho CloudTrail logs bucket cùng Terraform state bucket. Event `GetObject` thật đã được capture.

### 3. Làm giả

Trail đã bật log-file validation và KMS. `validate-logs` dùng digest chain để phát hiện log bị sửa, chèn, xóa hoặc chuỗi digest bị đứt; interval kiểm chứng có 2/2 digest và 85/85 log files hợp lệ.

Object Lock chưa bật và được ghi là residual immutability gap/follow-up riêng, không được trình bày là `PASS`.

## Không thực hiện destructive test

Không gọi thật `StopLogging`, `DeleteTrail`, xóa log hoặc phá selector. Dùng IAM Simulator để chứng minh `explicitDeny`; dùng read-only APIs và safe delivery checks cho evidence còn lại.
