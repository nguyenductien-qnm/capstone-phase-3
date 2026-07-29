# 04 — Mốc thời điểm: `Audit / Ignore`

![](04-policy-mode-audit-ignore.png)

**Chụp:** 23/07/2026 22:23 · ngay sau ảnh 03
**Chứng minh:** yêu cầu #3 — đóng dấu thời điểm cho vế TRƯỚC

## Trong ảnh có gì

```
k get clusterpolicy verify-image-signature \
  -o jsonpath='{.spec.validationFailureAction} / {.spec.failurePolicy}{"\n"}'
Audit / Ignore
```

## Vì sao đáng chụp

Chụp ngay sau [03](03-audit-unsigned-duoc-nhan.md) để đóng dấu rằng ảnh đó **đúng là chụp
lúc policy còn ở Audit**, không phải ảnh cũ dựng lại. Trong terminal còn thấy nguyên lệnh
`apply --dry-run` của ảnh 03 ở dòng trên.

Cặp [04](04-policy-mode-audit-ignore.md) ↔ [08](08-policy-mode-enforce-fail.md) là hai đầu
mốc của toàn bộ chuỗi before/after.
