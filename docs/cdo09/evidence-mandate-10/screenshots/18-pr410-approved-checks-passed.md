# 18 — Cổng chặn chạy thật trên PR #410

![](18-pr410-approved-checks-passed.png)

**Chụp:** 26/07/2026 00:33 · GitHub PR #410
**Chứng minh:** yêu cầu #1 — cổng không chỉ nằm trên trang cấu hình

## Trong ảnh có gì

PR #410 `fix(cicd): link provenance trace run and tighten review check`, từ nhánh
`fix/mandate10-trace-action-link-reviewer` vào `develop`:

- ✅ *"Changes approved — 1 approving review by reviewers with write access"*
  (`nguyenductien-qnm` approved)
- ✅ *"All checks have passed — 3 skipped, 4 successful checks"*
- ⚠️ *"This branch is out-of-date with the base branch"*
- 🚫 Nút **Merge pull request bị xám**

## Vì sao đáng chụp

[Ảnh 17](17-ruleset-3-required-checks.md) cho thấy cổng **được cấu hình**. Ảnh này cho thấy
cổng **thật sự cản người**.

Điều thú vị là PR này đã có đủ mọi thứ: được duyệt, mọi check xanh. Vậy mà nút merge vẫn
xám — vì `Require branches to be up to date before merging` ở ảnh 17 đang làm việc. Nhánh
chưa rebase theo `develop` mới nhất thì không được merge, kể cả khi tự nó hoàn hảo.

Ý nghĩa của quy tắc này: nó chặn tình huống hai PR riêng lẻ đều xanh nhưng gộp lại thì hỏng.
Buộc phải test với code mới nhất mới cho vào.

> [!NOTE]
> Còn **thiếu một ảnh** cho bài mentor: PR **cố tình đỏ** (test fail) → nút merge xám kèm
> dòng "Required statuses must pass". Ảnh 18 là PR xanh bị chặn vì lý do khác. Cần chụp bổ
> sung để hoàn thiện bộ bằng chứng.
