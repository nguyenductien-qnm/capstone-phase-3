# MANDATE-04 Evidence Pack

**Owner:** Nguyễn Tấn Huy  
**Jira:** CDO-46, CDO-105, CDO-106  
**AWS SSO profile:** `phase3-cdo`  
**AWS region:** `us-east-1`  
**Scope:** Kubernetes Audit Logs, AWS CloudTrail, Change Management, Forensic Investigation và Tamper Protection.

> Trạng thái dưới đây phản ánh kiểm tra runtime thật ngày 15/07/2026. Không đổi mục FAIL/BLOCKED thành PASS trước khi control được review, apply và kiểm tra lại.

## Evidence Matrix

| Evidence | Ticket | Nội dung chứng minh | Kết quả runtime |
|---|---|---|---|
| 01 — Terraform validate | CDO-46 | Terraform hợp lệ và backend S3 truy cập được | **PASS** |
| 02 — Terraform plan | CDO-46 | Thay đổi hạ tầng đúng phạm vi auditability | **BLOCKED:** thiếu sandbox tfvars thật |
| 03 — EKS audit enabled | CDO-46 | EKS bật `api`, `audit`, `authenticator` | **PASS** |
| 04 — CloudWatch audit stream | CDO-46/CDO-106 | Audit streams tồn tại và có event | **PARTIAL:** stream PASS; retention 7 ngày/KMS chưa apply |
| 05 — K8s forensic timeline | CDO-106 | Truy được user, thời gian, verb, resource, source IP, user agent và audit ID | **PASS** |
| 06 — CloudTrail status | CDO-46/CDO-105 | Trail đang logging, multi-region/global/validation, management read/write | **PASS** |
| 07 — CloudTrail user identity | CDO-105 | AWS event truy về IAM Identity Center session cá nhân | **PARTIAL:** SSO PASS; GitHub session chưa deploy |
| 08 — S3 log protection | CDO-105 | Versioning, encryption và public-access protection | **FAIL:** Versioning chưa cấu hình |
| 09 — CloudTrail validation | CDO-105 | Kiểm tra integrity digest/log | **PASS:** 3/3 digest, 126/126 log hợp lệ |
| 10 — PR/Jira/review | CDO-105 | Jira, tác giả, reviewer, approval và CI | **BLOCKED:** chưa có PR auditability |
| 11 — ArgoCD/Git correlation | CDO-105 | ArgoCD revision nối về commit, PR và Jira | **PASS:** root revision → PR #87 → CDO-49 |
| 12 — Operator explicit deny | CDO-105 | Operator không thể xóa/dừng audit pipeline | **FAIL:** IAM Simulator hiện trả `allowed` |

Chi tiết và đường dẫn raw evidence: [EVIDENCE-INDEX.md](EVIDENCE-INDEX.md).  
Kết quả chạy và blocker: [RUN-RESULTS.md](RUN-RESULTS.md).

## Forensic Demonstration

Drill đã dùng namespace cô lập `audit-forensic-demo` và ConfigMap `forensic-20260715082752`:

1. SSO user `huynt` tạo ConfigMap.
2. Annotation và label tạo các audit event `patch`.
3. ConfigMap được xóa và tạo audit event `delete`.
4. CloudWatch Logs Insights trả username/group, timestamp, verb, resource, source IP, user agent, response code và audit ID.
5. Namespace demo đã cleanup.

Raw evidence: `logs/05-k8s-forensic-timeline.json`.  
Query đã dùng: `queries/05-k8s-forensic-timeline-used.txt`.

## Integrity Result

CloudTrail validation trên khoảng thời gian nhỏ trả:

```text
3/3 digest files valid
126/126 log files valid
```

Raw evidence: `logs/09-cloudtrail-validation.txt`.

## Tamper Protection Status

Đã có:

- CloudTrail log-file validation.
- S3 AES256 encryption.
- S3 Public Access Block với bốn control đều bật.
- Terraform `prevent_destroy` trong code.

Chưa đạt runtime:

- S3 Versioning chưa bật.
- Tamper-deny managed policy chưa được tạo/gắn vào Operator Permission Set.
- Current SSO role đang có `AdministratorAccess`; simulator trả `allowed` cho CloudTrail stop/delete/update và S3 delete/bypass.
- Object Lock chưa bật, phù hợp thiết kế opt-in/migration nhưng không được ghi là PASS.

Không thực hiện destructive test thật đối với CloudTrail hoặc S3.

## Evidence Locations

- Workspace guide: `docs/cdo09/evidence-mandate-04/README.md`
- Evidence index: `docs/cdo09/evidence-mandate-04/EVIDENCE-INDEX.md`
- Runtime results: `docs/cdo09/evidence-mandate-04/RUN-RESULTS.md`
- Screenshots: `docs/cdo09/evidence-mandate-04/screenshots/`
- Command outputs: `docs/cdo09/evidence-mandate-04/logs/`
- Saved queries: `docs/cdo09/evidence-mandate-04/queries/`
- Main report: `docs/cdo09/cdo-46-105-106-mandate-04-auditability.md`
- Change-management runbook: `docs/cdo09/change-management-runbook.md`
- Forensic drill: `docs/cdo09/mandate-04-forensic-drill.md`
