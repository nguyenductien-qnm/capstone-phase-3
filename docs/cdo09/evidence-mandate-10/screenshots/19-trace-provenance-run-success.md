# 19 — Workflow truy ngược chạy thành công

![](19-trace-provenance-run-success.png)

**Chụp:** 26/07/2026 10:08 · GitHub Actions
**Chứng minh:** yêu cầu #5 — công cụ truy ngược tồn tại và chạy được

## Trong ảnh có gì

| Trường | Giá trị |
|---|---|
| Workflow | `trace-image-provenance.yaml` (`on: workflow_dispatch`) |
| Trigger | Manually triggered, actor `lken1514` |
| Commit / nhánh | `01c8cc8` · `develop` |
| Status | **Success** |
| Thời gian | **28s** (job `Trace pod image provenance` 23s) |

## Vì sao đáng chụp

Đây là ảnh mở đầu cho [ảnh 20](20-trace-provenance-8-mat-xich.md) — chứng minh workflow
chạy thật, thành công, và **nhanh** (28 giây).

Con số 28s quan trọng khi demo: mentor bấm nút rồi đứng chờ, nửa phút là chấp nhận được.

Workflow này thay cho `scripts/provenance.sh` trong plan gốc. Đổi từ script sang workflow
có cái lợi là mỗi lần chạy để lại một run log công khai, có người bấm, có thời điểm — bản
thân nó cũng là bằng chứng kiểm toán được.

> [!TIP]
> Khi demo phải lấy **tên pod ngay trước lúc chạy**. Bốn run fail hôm 25/07 đều do dispatch
> với tên pod đã bị rollout thay thế (`pods "..." not found`) — dương tính giả, không phải
> lỗi chuỗi cung ứng.
