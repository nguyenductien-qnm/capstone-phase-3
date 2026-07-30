# Mandate 04 forensic drill — CDO-46/105/106

Mỗi lần drill tạo thư mục evidence theo `<UTC>-<Jira>-<scenario>`; lưu output đã redact, query, audit ID, run URL và revision, không tạo ảnh giả.

## 1. Kubernetes change

**Preconditions:** AWS SSO cá nhân, `kubectl`, AWS CLI/jq, EKS log types `api/audit/authenticator`. Chạy `forensic-k8s-audit.sh --region <r> --cluster-name <c> --start <ISO> --end <ISO> --generate-demo-event`.

**Expected/evidence:** namespace `audit-forensic-demo`; ConfigMap unique có create/patch/delete. Chụp output chứa timestamp, username/groups, verb, objectRef, source IP, user agent, response code, audit ID. Cleanup ConfigMap tự động; namespace có thể xóa sau khi đã query và phải chứng minh delete event. Nếu trống, đợi ingestion, mở rộng 15 phút, kiểm tra stream `kube-apiserver-audit-*` và clock UTC.

## 2. GitOps change

**Preconditions:** Helm-values PR đã review/merge và ArgoCD healthy. Lấy revision bằng `kubectl -n argocd get application <app> -o jsonpath='{.status.sync.revision}'`; chạy `forensic-change-trail.sh --target <values-file> --revision <sha> --argocd-application <app>` và query K8s audit quanh sync.

**Expected/evidence:** audit actor là service account ArgoCD; revision bằng Git commit; commit liên kết PR author/reviewer/Jira. Chụp application revision/health, audit ID, `git show`, PR approvals/checks. Cleanup bằng revert PR nếu đây là demo. Nếu revision khác, kiểm tra source path/targetRevision và refresh status.

## 3. AWS infrastructure change

**Preconditions:** PR Terraform nhỏ (ví dụ tag/logging) có plan và protected apply. Chạy `forensic-cloudtrail.sh --region <r> --trail-name <t> --start <ISO> --end <ISO> --username gha-<actor>-<run_id>`.

**Expected/evidence:** event write có assumed-role session, source IP/user agent/resource; `run_id` mở đúng GitHub run, nơi hiển thị repository, workflow, actor, SHA và PR. Chụp CloudTrail event ID/output đã redact, run summary, PR/plan. Rollback bằng revert PR và reviewed plan. Nếu không thấy event, kiểm tra region (trail multi-region), time UTC và event name.

## 4. Integrity verification

**Preconditions:** audit admin chỉ đọc; Operator role đã gắn tamper-deny. Chạy `verify-auditability`, `get-trail-status`, `get-event-selectors`; sau đó chạy `aws cloudtrail validate-logs --trail-arn <arn> --start-time <small-start> --end-time <small-end>` trên khoảng nhỏ.

Kiểm tra `get-bucket-versioning`, `get-public-access-block`, `get-bucket-encryption`, và Object Lock nếu bật. Với Operator, thử dry/safe negative test như `aws cloudtrail stop-logging --name <trail>` và mong `AccessDenied`; vì AWS CLI không có dry-run cho lệnh này, chỉ thực hiện khi SCP/permission simulator hoặc môi trường chứng minh explicit deny, không dùng audit-admin/break-glass và không cho phép request thành công. Tương tự không gửi delete thật nếu policy chưa được xác nhận bằng IAM simulator.

**Evidence:** validation success/digest interval, versioning/encryption/public block, simulator/AccessDenied có principal/action, policy ARN. Không cleanup audit evidence. Nếu validation fail, không xóa log; kiểm tra digest delivery, bucket/KMS policy, region/time và mở incident.
