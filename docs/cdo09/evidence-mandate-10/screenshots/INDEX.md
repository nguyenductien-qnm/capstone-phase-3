# MANDATE-10 — chú thích ảnh bằng chứng (23/07 → 26/07/2026)

23 ảnh: **01–14** chụp trên PROD (account `804372444787`, cluster `ecommerce-dev-eks`,
namespace `techx-tf1`), **15–23** chụp trên GitHub (ruleset + Actions). Xếp theo thời gian,
nhóm theo yêu cầu của directive.

Đọc nhanh: ảnh **09 + 10** là cặp chứng minh admission chặn thật; ảnh **17 → 23** là dòng
thời gian cổng chặn từ 3 lên 4 check; ảnh **20** chứng minh truy ngược full provenance;
ảnh **21** chứng minh SAST chạy thật; ảnh **22** chứng minh không rebuild thừa.

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
| 21 | [21-codeql-8-ngon-ngu-pass](21-codeql-8-ngon-ngu-pass.md) | 26/07 19:43 | #2 — **SAST chạy thật** ⭐ |
| 22 | [22-pr413-build-skipped](22-pr413-build-skipped.md) | 26/07 19:49 | #6 — **không rebuild thừa** ⭐ |
| 23 | [23-ruleset-4-checks-co-sast](23-ruleset-4-checks-co-sast.md) | 26/07 20:03 | #1+#2 — **SAST thành cổng chặn** ⭐ |

---

## Đã vá thêm ngày 26/07 (ảnh 21–23)

Ba mục dưới đây trước còn ghi "chưa phủ", nay đã có ảnh:

| Yêu cầu | Trước 26/07 | Nay |
|---|---|---|
| #2 — vế SAST | 0/13 workflow có SAST | ✅ [21](21-codeql-8-ngon-ngu-pass.md) CodeQL 8 ngôn ngữ pass + [23](23-ruleset-4-checks-co-sast.md) đã required |
| #2 — vế IaC gate | `exit-code:"0"` + `soft_fail:true` | ✅ Đã bật chặn (PR #429 merged) — bằng chứng lệnh trong [IAC-GATE.md](../IAC-GATE.md) |
| #6 — scoped build | chỉ có bằng chứng file | ✅ [22](22-pr413-build-skipped.md) workflow tự chứng minh trên chính nó |

## Những gì 23 ảnh này VẪN CHƯA phủ

Ghi rõ để không ai tưởng bộ ảnh là đủ:

| Yêu cầu | Thiếu gì |
|---|---|
| #1 — cảnh PR đỏ | Ảnh 18 là PR **xanh** bị chặn vì out-of-date. Còn thiếu ảnh PR **cố tình đỏ** → nút merge xám vì check fail. Đây là màn 1 trong mục "Phải nộp" của directive |
| #2 — vế IaC gate | Đã bật thật nhưng **chưa có ảnh** job `Terraform fmt, validate, scan` pass ở chế độ chặn |
| #4 — pin SHA/digest | Chưa có ảnh; bằng chứng đang ở dạng lệnh grep (`uses:@vX` = 0, 57/57 `FROM` có `@sha256:`). Chưa có job CI nào **gate** việc pin, nên chỉ chứng minh được "đang pin", không chứng minh được "không trôi lại được" |
