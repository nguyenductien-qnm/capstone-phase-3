# 08 — Mốc thời điểm: `Enforce / Fail`

![](08-policy-mode-enforce-fail.png)

**Chụp:** 23/07/2026 22:48
**Chứng minh:** yêu cầu #3 — đóng dấu thời điểm cho vế SAU

## Trong ảnh có gì

Cùng một lệnh với [ảnh 04](04-policy-mode-audit-ignore.md), kết quả đổi thành:

```
Enforce / Fail
```

## Vì sao đáng chụp

Đây là đầu mốc thứ hai. Cặp [04](04-policy-mode-audit-ignore.md) `Audit / Ignore` ↔
[08](08-policy-mode-enforce-fail.md) `Enforce / Fail` xác định chính xác ranh giới thời
gian: mọi thứ chụp trước 22:23 là hành vi Audit, mọi thứ sau 22:48 là hành vi Enforce.

Hai chữ đổi cùng lúc mang hai ý nghĩa khác nhau. `Enforce` là "vi phạm thì chặn".
`Fail` là "webhook lỗi cũng chặn" — fail-closed, xem [01](01-kyverno-pods-pdb.md).
