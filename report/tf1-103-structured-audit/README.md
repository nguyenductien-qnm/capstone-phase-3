# TF1-103 — Structured remediation audit

## Mục tiêu

Mỗi lần remediation có một `remediation_id` xuyên suốt để trả lời được bốn câu hỏi:

1. Trigger nào khởi tạo lần xử lý này?
2. Các safety gate cho phép hay chặn hành động, và vì sao?
3. Action đã chạy chưa; verify pass hay fail?
4. Rollback có thực sự xảy ra không? Nếu không, vì sao?

Runtime ghi append-only JSONL tại `REMEDIATION_AUDIT_FILE`. Mỗi dòng là một quyết
định độc lập; lỗi ghi audit chỉ phát warning, không làm chết remediation loop.

## Schema v1

Các trường chung:

| Trường | Ý nghĩa |
|---|---|
| `schema_version` | Phiên bản schema, hiện là `1` |
| `event_id` | ID duy nhất cho từng dòng |
| `remediation_id` | Correlation ID của toàn bộ một attempt |
| `ts`, `ts_utc` | Unix timestamp và thời gian UTC đọc được |
| `stage` | `detect`, `circuit_breaker`, `error_budget`, `blast_radius`, `dry_run`, `action`, `verify`, `rollback`, `escalate` |
| `decision` | Quyết định tại stage, ví dụ `allow`, `deny`, `acted`, `pass`, `fail`, `not_required` |
| `rule_id`, `service`, `pod`, `dry_run` | Target và chế độ chạy |
| Các trường bổ sung | Threshold, thời lượng verify, lỗi, lý do rollback/escalate |

`remediation_id` được tạo tường minh ở đầu remediation attempt. Nếu call site mới
quên truyền ID, writer giữ giá trị `null` và cảnh báo; report hiển thị
`missing-remediation-id-*` thay vì tự tạo correlation giả.

Thứ tự terminal hợp lệ:

```text
detect → safety gates → dry_run
detect → safety gates → action(error) → rollback(not_required)
detect → safety gates → action → verify(pass) → rollback(not_required)
detect → safety gates → action → verify(fail) → rollback(not_available) → escalate
```

`k8s_restart_pod` chỉ xóa một pod để ReplicaSet tạo pod thay thế; nó không đổi
configuration hoặc release. Vì vậy nếu verify fail, hệ thống ghi trung thực
`rollback_performed=false`, dừng automation/cập nhật circuit breaker và escalate,
thay vì báo một rollback không tồn tại.

Stage `escalate` ghi `decision=buffered` khi notifier nhận alert vào buffer, hoặc
`decision=suppressed_by_cooldown` khi dedup cooldown chủ động chặn alert. Hai giá trị
này không tuyên bố delivery thành công hay thất bại; delivery thật xảy ra ở `flush()`.

## Tạo artifact Markdown

Từ checkout của repository:

```sh
python aiops/remediation/audit_report.py \
  --input /tmp/audit_log.jsonl \
  --output /tmp/remediation-audit-report.md
```

Lấy evidence từ pod đang chạy là thao tác đọc:

```sh
kubectl -n techx-tf1 exec deploy/aiops-remediation -- \
  cat /data/audit_log.jsonl > /tmp/audit_log.jsonl
```

Report generator vẫn đọc được evidence schema cũ chưa có `remediation_id`, bằng cách
gom một legacy attempt bắt đầu từ mỗi stage `detect`. File live cũ được giữ nguyên tại
[`../mandate22-thresholds/audit_log-live-28jul.jsonl`](../mandate22-thresholds/audit_log-live-28jul.jsonl).

## Giới hạn bằng chứng

- File live ngày 28/07/2026 chỉ chứng minh flow dry-run của schema cũ. Nó không
  chứng minh schema v1 mới đã chạy trên cluster.
- Cần redeploy image mới và capture một attempt live để đóng phần rollout evidence.
- Deployment hiện mount `/data` bằng `emptyDir`: audit sống qua container restart
  trong cùng pod nhưng mất khi pod bị thay thế. Đây là structured local store, **chưa
  phải durable/compliance store**. PVC hoặc log shipping là follow-up vận hành.
- Artifact điều tra và quyết định kỹ thuật nằm tại [`postmortem.md`](postmortem.md).
