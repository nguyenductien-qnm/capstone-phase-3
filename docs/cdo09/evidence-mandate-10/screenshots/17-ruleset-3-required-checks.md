# 17 ⭐ — Ba required status check

![](17-ruleset-3-required-checks.png)

**Chụp:** 25/07/2026 23:30 · GitHub repo settings → Rules
**Chứng minh:** yêu cầu #1 — **"CI đỏ = không merge, không deploy"**

## Trong ảnh có gì

| Cấu hình | Trạng thái |
|---|---|
| `Require status checks to pass` | ✅ |
| `Require branches to be up to date before merging` | ✅ |
| `Block force pushes` | ✅ |
| `Require code scanning results` | ⬜ **chưa bật** |

Danh sách check bắt buộc (đều là GitHub Actions):

| Check | Chặn cái gì |
|---|---|
| `Secret scan (gitleaks)` | secret lọt vào repo |
| `Helm lint + render (deploy gate)` | manifest hỏng ra cluster |
| `Unit tests` | code đỏ |

## Vì sao đáng chụp

Bằng chứng trực tiếp và đầy đủ nhất cho yêu cầu #1: *"CI đỏ = không merge, không deploy.
Bật branch protection + required status checks trên nhánh deploy. Hết cảnh pipeline chạy
cho vui"*.

Tên `Unit tests` là job discovery mới từ PR #340, thay cho hai check cứng
`Unit test (checkout)` và `Unit test (product-catalog)` trước đây. Job tự dò service nào
có test thay vì liệt kê tay, nên thêm service mới không phải sửa ruleset.

`Block force pushes` bịt đường vòng: không thể force-push đè lên nhánh để né cổng.

> [!WARNING]
> Ô **`Require code scanning results` chưa bật** — khớp với kết luận **SAST còn thiếu** tại
> thời điểm chụp. Grep 10 công cụ (`codeql semgrep sonar snyk bandit gosec njsscan horusec
> opengrep`) trên cả 13 workflow đều ra 0 kết quả.

> [!NOTE]
> **Cập nhật 26/07:** câu "đây chính là ô cần tick để SAST thành cổng chặn" ở bản trước
> **không đúng**. Thực tế chỉ cần thêm `SAST (codeql)` vào danh sách required check là đủ
> chặn merge — xem [23](23-ruleset-4-checks-co-sast.md). Ô `Require code scanning results`
> vẫn cố ý để trống, lý do ghi trong ảnh 23.

Xem cổng này chặn thật: [18](18-pr410-approved-checks-passed.md)
Xem cổng này sau khi thêm SAST: [23](23-ruleset-4-checks-co-sast.md)
