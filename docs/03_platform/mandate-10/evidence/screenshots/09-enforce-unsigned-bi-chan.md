# 09 ⭐ — Vế SAU: image không chữ ký BỊ CHẶN

![](09-enforce-unsigned-bi-chan.png)

**Chụp:** 23/07/2026 22:49 · ns `techx-tf1`
**Chứng minh:** yêu cầu #3 — **bằng chứng đắt nhất của MANDATE-10**

## Trong ảnh có gì

Cùng file `pod-unsigned.yaml` đã dùng ở [ảnh 03](03-audit-unsigned-duoc-nhan.md), giờ nhận:

```
Error from server: admission webhook "mutate.kyverno.svc-fail" denied the request:

resource Pod/techx-tf1/kyverno-test-unsigned was blocked due to the following policies

verify-image-signature:
  verify-techx-corp-images: 'failed to verify image
    804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp@sha256:0311458d9347de8d79727bc1ed7f97866e3c54625099a5808157c26e796bdc9e:
    .attestors[0].entries[0].keyless: no signatures found'
```

## Vì sao đáng chụp

Ba chi tiết làm nên sức nặng của ảnh này.

Thứ nhất, lệnh chạy **hai lần** — một lần `apply` thật, một lần `--dry-run=server` với
`--context $PROD` — cả hai đều bị chặn với cùng thông điệp. Không phải trục trặc ngẫu nhiên.

Thứ hai, lỗi ghi rõ **`no signatures found`**, tức policy thật sự đi tìm chữ ký và không
thấy, chứ không phải fail vì mạng hay timeout.

Thứ ba và quan trọng nhất: so với [ảnh 03](03-audit-unsigned-duoc-nhan.md) thì **cùng một
manifest, cùng một cụm, chỉ khác chế độ policy** — kết quả lật từ `created` sang `blocked`.
Đây đúng thứ directive đòi ở #3: *"cluster chỉ chạy image đã ký... admission enforce
(không phải audit/cảnh báo suông)"*, và đúng bài mentor bấm nút: *"thử deploy một image
chưa ký → admission phải từ chối"*.

Cặp đôi: [03](03-audit-unsigned-duoc-nhan.md) trước ↔ **09** sau.
Bổ sung: [10](10-enforce-signed-mutate-digest.md) chứng minh không chặn nhầm image sạch.
