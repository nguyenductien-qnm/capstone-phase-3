# TF1-103 — Postmortem: remediation audit evidence gap

**Ngày lập:** 31/07/2026  
**Trạng thái:** Code và automated tests hoàn tất; live rollout evidence còn chờ deploy  
**Phạm vi:** `aiops/remediation/`

## Tóm tắt

Remediation engine đã alert qua Slack/Discord và ghi log ứng dụng, nhưng bằng chứng
điều tra chưa đủ để nối toàn bộ một attempt từ trigger đến kết quả cuối. Các dòng
JSONL cũ không có correlation ID, không ghi rõ rollback có xảy ra hay không, và
incident replay đọc các field aggregate không tồn tại. `report/` cũng thiếu index và
artifact riêng cho audit/postmortem.

Không có bằng chứng hệ thống đã thực hiện rollback sai. Vấn đề là **không thể chứng
minh đầy đủ quyết định của hệ thống sau sự cố**.

## Ảnh hưởng

- Người trực khó trả lời một action được phép/chặn ở safety gate nào.
- Nhiều remediation chạy gần nhau không thể được correlate chắc chắn.
- Verify fail có thể bị diễn giải nhầm là đã rollback dù action `restart_pod` không
  tạo thay đổi configuration/release có thể hoàn tác.
- Replay/report cũ hiển thị các field rỗng và không tạo được artifact điều tra tin cậy.
- Audit file trong pod có thể mất khi pod bị thay thế do dùng `emptyDir`.

## Timeline

| Thời gian | Sự kiện |
|---|---|
| 28/07/2026 | Capture live 5 dòng audit của một dry-run OOM; flow safety gate có dữ liệu nhưng schema chưa có `remediation_id`, `event_id`, UTC timestamp hoặc rollback record |
| 31/07/2026 | Xác định khoảng trống TF1-103 và đối chiếu remediation flow, deployment, replay và report artifacts |
| 31/07/2026 | Thêm schema v1, correlation ID xuyên suốt attempt và stage `rollback`/`escalate` |
| 31/07/2026 | Thêm Markdown report generator tương thích evidence legacy; sửa incident replay đọc field thực |
| 31/07/2026 | Thêm automated tests cho correlation, verify-fail, rollback transparency và legacy evidence |

## Nguyên nhân gốc

1. Audit ban đầu được thiết kế như các dòng quyết định riêng lẻ, chưa có khóa nối
   toàn bộ remediation attempt.
2. Flow có verify và circuit breaker nhưng chưa biểu diễn rollback như một quyết định
   audit tường minh.
3. Replay kỳ vọng một record tổng hợp (`outcome`, `verify`,
   `rollback_or_escalate`) trong khi writer ghi record theo stage.
4. Runtime file được ưu tiên để hoạt động với read-only root filesystem, nhưng
   lifecycle của `emptyDir` chưa đáp ứng retention dài hạn.
5. Không có generator và report index để chuyển machine evidence thành artifact cho
   người review.

## Khắc phục

| Hạng mục | Thay đổi | Kết quả mong đợi |
|---|---|---|
| Correlation | Một `remediation_id` được tạo sau khi xác nhận OOM pod và truyền qua mọi stage | Query được trọn một attempt |
| Event identity | Mỗi record có `schema_version`, `event_id`, `ts`, `ts_utc` | Schema có version và thời gian dễ điều tra |
| Rollback | Ghi `rollback_performed` cùng `not_required` hoặc `not_available` | Không suy diễn rollback từ verify |
| Escalation | Ghi stage `escalate` sau safety deny hoặc verify fail | Chứng minh handoff cho người trực |
| Reporting | `audit_report.py` tạo summary và timeline Markdown | Có artifact post-incident tái tạo được |
| Legacy | Generator nhóm evidence cũ bắt đầu từ `detect` | Không bỏ dữ liệu live đã capture |
| Replay | In các field stage-level có thật | Không còn report dựa trên schema tưởng tượng |

## Validation

| Case | Bằng chứng cần có |
|---|---|
| Dry-run | Chung một `remediation_id`; terminal stage `dry_run`; không có action thật |
| Verify pass | `action=acted` → `verify=pass` → `rollback=not_required`, `rollback_performed=false` |
| Verify fail | `action=acted` → `verify=fail` → `rollback=not_available` → `escalate=sent` |
| Legacy JSONL | Generator đọc được file chưa có schema/correlation ID và đánh dấu rollback `not recorded` |
| Invalid JSONL | Generator báo đúng file và số dòng thay vì tạo report sai |

Automated validation được đặt trong
[`../../aiops/remediation/test_remediation.py`](../../aiops/remediation/test_remediation.py).

## Rollback của chính thay đổi này

Code change chỉ bổ sung field/dòng JSONL và một CLI report; các consumer phải bỏ qua
field chưa biết. Nếu cần rollback deployment, dùng image tag trước đó. Evidence đã ghi
không cần và không nên xóa; generator mới vẫn đọc schema legacy.

## Phần còn mở

1. Deploy image chứa schema v1 lên `techx-tf1`.
2. Capture ít nhất một live dry-run và một terminal path có action/verify khi được
   phê duyệt an toàn.
3. Chọn retention backend (PVC hoặc log shipper tới store tập trung), định nghĩa
   retention/access control và thay `emptyDir`.
4. Đính kèm live generated report vào thư mục này sau rollout.

Do chưa có live rollout của code mới, artifact này không tuyên bố TF1-103 đã được
verify end-to-end trên cluster.

