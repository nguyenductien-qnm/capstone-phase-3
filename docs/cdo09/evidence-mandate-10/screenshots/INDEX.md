# MANDATE-10 — chú thích ảnh bằng chứng (23/07 → 26/07/2026)

20 ảnh chụp trên **PROD** (account `804372444787`, cluster `ecommerce-dev-eks`, namespace
`techx-tf1`). Xếp theo thời gian, nhóm theo yêu cầu của directive.

Đọc nhanh: ảnh **09 + 10** là cặp chứng minh admission chặn thật; ảnh **17** chứng minh
CI đỏ không merge được; ảnh **20** chứng minh truy ngược full provenance.

## Bảng tra nhanh

| # | Ảnh | Thời điểm | Chứng minh yêu cầu |
|---|---|---|---|
| 01 | [01-kyverno-pods-pdb](01-kyverno-pods-pdb.md) | 23/07 22:08 | #3 — Kyverno chạy HA |
| 02 | [02-policyreport-audit-20pass](02-policyreport-audit-20pass.md) | 23/07 22:10 | #3 — soak Audit sạch |
| 03 | [03-audit-unsigned-duoc-nhan](03-audit-unsigned-duoc-nhan.md) | 23/07 22:22 | #3 — **vế TRƯỚC** |
| 04 | [04-policy-mode-audit-ignore](04-policy-mode-audit-ignore.md) | 23/07 22:23 | #3 — mốc `Audit/Ignore` |
| 05 | [05-argocd-diff-map-rong](05-argocd-diff-map-rong.md) | 23/07 22:25 | phụ — giải thích OutOfSync |
| 06 | [06-pr-flip-enforce-diff](06-pr-flip-enforce-diff.md) | 23/07 22:36 | #3 — diff flip Enforce |
| 07 | [07-argocd-apps-sau-flip](07-argocd-apps-sau-flip.md) | 23/07 22:45 | #3 — GitOps đã sync |
| 08 | [08-policy-mode-enforce-fail](08-policy-mode-enforce-fail.md) | 23/07 22:48 | #3 — mốc `Enforce/Fail` |
| 09 | [09-enforce-unsigned-bi-chan](09-enforce-unsigned-bi-chan.md) | 23/07 22:49 | #3 — **vế SAU** ⭐ |
| 10 | [10-enforce-signed-mutate-digest](10-enforce-signed-mutate-digest.md) | 23/07 22:52 | #3 — tag→digest ⭐ |
| 11 | [11-policyreport-36-aiops-pass](11-policyreport-36-aiops-pass.md) | 23/07 22:52 | #3 — bịt shadow path |
| 12 | [12-rollout-frontend-thanh-cong](12-rollout-frontend-thanh-cong.md) | 23/07 22:53 | ràng buộc — giữ SLO |
| 13 | [13-techx-corp-synced-healthy](13-techx-corp-synced-healthy.md) | 23/07 23:06 | ràng buộc — cụm khỏe |
| 14 | [14-do-tre-admission-3-lan](14-do-tre-admission-3-lan.md) | 23/07 23:07 | ràng buộc — chi phí |
| 15 | [15-ruleset-target-branches](15-ruleset-target-branches.md) | 25/07 23:28 | #1 — phạm vi ruleset |
| 16 | [16-ruleset-require-pr-approval](16-ruleset-require-pr-approval.md) | 25/07 23:29 | #1 + #5 — bắt buộc duyệt |
| 17 | [17-ruleset-3-required-checks](17-ruleset-3-required-checks.md) | 25/07 23:30 | #1 — **cổng chặn** ⭐ |
| 18 | [18-pr410-approved-checks-passed](18-pr410-approved-checks-passed.md) | 26/07 00:33 | #1 — cổng chạy thật |
| 19 | [19-trace-provenance-run-success](19-trace-provenance-run-success.md) | 26/07 10:08 | #5 — workflow chạy |
| 20 | [20-trace-provenance-8-mat-xich](20-trace-provenance-8-mat-xich.md) | 26/07 10:09 | #5 — **truy ngược** ⭐ |
| 21 | [21-codeql-8-ngon-ngu-pass](21-codeql-8-ngon-ngu-pass.md) | 26/07 19:43 | #2 — SAST chạy thật ⭐ |
| 22 | [22-pr413-build-skipped](22-pr413-build-skipped.md) | 26/07 19:49 | #6 — chỉ đụng cái gì đổi ⭐ |
| 23 | [23-ruleset-4-checks-co-sast](23-ruleset-4-checks-co-sast.md) | 26/07 20:03 | #1 + #2 — SAST vào ruleset ⭐ |
| 24 | [24-pr444-pinguard-do-merge-xam](24-pr444-pinguard-do-merge-xam.md) | 27/07 10:53 | #1 — **PR đỏ bị chặn** ⭐ |
| 25 | [25-pr444-diff-doi-sha-ve-tag](25-pr444-diff-doi-sha-ve-tag.md) | 27/07 10:53 | #4 — lỗi mồi là lỗi thật |
| 26 | [26-add-check-codeql-vs-sast](26-add-check-codeql-vs-sast.md) | 27/07 11:04 | #1 — chọn đúng cổng |
| 27 | [27-ruleset-7-required-checks](27-ruleset-7-required-checks.md) | 27/07 11:05 | #1 — **7 cổng** ⭐ |
| 28 | [28-pr443-alert-sql-injection-high](28-pr443-alert-sql-injection-high.md) | 27/07 11:06 | #2 — SAST bắt High |
| 29 | [29-pr443-alert-command-injection-critical](29-pr443-alert-command-injection-critical.md) | 27/07 11:06 | #2 — SAST bắt Critical |
| 30 | [30-pr443-codeql-required-merge-xam](30-pr443-codeql-required-merge-xam.md) | 27/07 11:06 | #1 + #2 — **PR đỏ bị chặn** ⭐ |
| 31 | [31-pr446-trivy-8-cve-perl-base](31-pr446-trivy-8-cve-perl-base.md) | 27/07 11:24 | #2 — Trivy bắt 8 CVE |
| 32 | [32-pr446-image-scan-gate-merge-xam](32-pr446-image-scan-gate-merge-xam.md) | 27/07 11:24 | #1 + #2 — **PR đỏ bị chặn** ⭐ |

---

## Ba màn "PR cố tình đỏ"

Yêu cầu *"mở PR với CI cố tình đỏ → phải bị chặn merge"* cần chứng minh cổng chặn **đúng
chỗ**, không phải chặn bừa. Nên có ba màn, mỗi màn một loại cổng và một cơ chế chặn khác
nhau:

| | PR #444 · ảnh [24](24-pr444-pinguard-do-merge-xam.md), [25](25-pr444-diff-doi-sha-ve-tag.md) | PR #443 · ảnh [28](28-pr443-alert-sql-injection-high.md)–[30](30-pr443-codeql-required-merge-xam.md) | PR #446 · ảnh [31](31-pr446-trivy-8-cve-perl-base.md), [32](32-pr446-image-scan-gate-merge-xam.md) |
|---|---|---|---|
| Cổng đỏ | `Pin guard` | `CodeQL` | `Image scan gate` |
| Loại lỗi | Cấu hình pipeline sai | Lỗ hổng mã nguồn | CVE trong ảnh container |
| Cách gài | Đổi `setup-python` SHA → `@v5` | Thêm SQL + command injection | Gỡ 8 dòng `perl-base` khỏi `.trivyignore` |
| Ai quyết định đỏ | Script tự viết trong workflow | GitHub so ngưỡng severity | Job gộp đọc kết quả workflow khác qua API |
| Số chặng | 1 — gate tự bắt | 2 — quét rồi so ngưỡng | **3 — Trivy → build → gate** |
| Thời gian đỏ | 10 giây | 1 giây (đọc kết quả có sẵn) | 1 phút (chờ build xong) |
| Cổng còn lại | 🟢 xanh hết | 🟢 xanh hết | 🟢 xanh hết |

Cả ba PR đều **đã có 1 approval** mà nút Merge vẫn xám — chứng minh thứ giữ cửa là gate,
không phải thiếu chữ ký.

Cả ba đã đóng sau khi chụp, nhánh giữ lại để đối chiếu commit.

### Vì sao cần cả ba

Ba cơ chế chặn khác hẳn nhau, và mỗi cái có thể hỏng theo cách riêng:

- **Một chặng** (Pin guard) — script tự viết, hỏng thì thấy ngay
- **Hai chặng** (CodeQL) — job xanh mà cổng vẫn đỏ được; chứng minh `SAST (codeql)` và
  `CodeQL` là hai thứ khác nhau (xem [26](26-add-check-codeql-vs-sast.md))
- **Ba chặng** (Trivy) — cổng chặn nằm ở workflow KHÁC với chỗ phát hiện lỗi, nối với nhau
  qua GitHub API. Đây là dây nối chưa từng được kiểm trước PR #446

## Những gì bộ ảnh này CHƯA phủ

Ghi rõ để không ai tưởng là đủ:

| Yêu cầu | Thiếu gì |
|---|---|
| #1 — cổng hạ tầng | `Terraform fmt, validate, scan` chưa vào ruleset. Không phải quên: workflow hạ tầng chưa có job gộp tên cố định, thêm job matrix vào sẽ dính bẫy tên động (xem [26](26-add-check-codeql-vs-sast.md)) |

Ngoài ra repo còn **6 alert code scanning đang mở** (`py/flask-debug`, 3 ×
`js/tainted-format-string`, 2 × `actions/missing-workflow-permissions`). Chúng không làm
`CodeQL` đỏ vì đều dưới mức high, nhưng vẫn là nợ cần xử.
