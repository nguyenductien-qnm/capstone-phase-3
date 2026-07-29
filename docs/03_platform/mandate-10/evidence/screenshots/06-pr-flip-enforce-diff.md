# 06 — Diff của PR flip Enforce

![](06-pr-flip-enforce-diff.png)

**Chụp:** 23/07/2026 22:36 · GitHub PR view
**Chứng minh:** yêu cầu #3 — thay đổi đi qua Git, không patch tay

## Trong ảnh có gì

Diff `platform/policies/kyverno/verify-image-signature.yaml`, `+55 −18`. Bỏ dòng
`validationFailureAction: Audit`, thêm khối comment dài giải thích và chuyển sang Enforce.

## Vì sao đáng chụp

Trước hết là chứng minh thay đổi **đi qua Git**. ArgoCD bật selfHeal nên `kubectl patch`
tay sẽ bị revert sau vài phút — mọi thay đổi policy buộc phải qua PR.

Quan trọng hơn, phần comment mới ghi lại một ràng buộc đã vấp phải thật: **`mutateDigest:
true` chỉ hợp lệ với `Enforce`**. Webhook `validate-policy` từ chối thẳng tổ hợp `Audit` +
`mutateDigest` với lỗi:

```
mutateDigest must be set to false for 'Audit' failure action
```

Lý do là ở Audit policy không được phép sửa resource, mà mutate chính là hành vi của
Enforce. Hệ quả thực tế cho vận hành: **khi rollback về Audit phải hạ `mutateDigest` xuống
`false` CÙNG LÚC**, nếu không ArgoCD sync fail và policy kẹt ở bản cũ.

Comment cũng liệt kê điều kiện flip đã đủ: 29 PolicyReport PASS=29 FAIL=0, 80 lần
"verification succeeded" 0 failed, 2 image aiops đã qua app-build.
