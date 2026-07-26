# 13 — App `techx-corp` Synced / Healthy

![](13-techx-corp-synced-healthy.png)

**Chụp:** 23/07/2026 23:06 · ArgoCD
**Chứng minh:** ràng buộc directive — cụm khỏe sau khi bật Enforce

## Trong ảnh có gì

```
k get app techx-corp -n argocd
NAME         SYNC STATUS   HEALTH STATUS
techx-corp   Synced        Healthy
```

## Vì sao đáng chụp

`techx-corp` là Application chứa **toàn bộ ~20 service ứng dụng**. Nó Healthy nghĩa là sau
khi admission bắt đầu chặn, không service nào bị kẹt vì thiếu chữ ký.

Đây là chốt cuối của mạch 23/07: policy đã Enforce ([08](08-policy-mode-enforce-fail.md)),
chặn được image bẩn ([09](09-enforce-unsigned-bi-chan.md)), nhận image sạch
([10](10-enforce-signed-mutate-digest.md)), rollout được ([12](12-rollout-frontend-thanh-cong.md)),
và toàn hệ vẫn khỏe.

> [!NOTE]
> Trạng thái này **đã đổi** vào 26/07 — `techx-corp` chuyển sang Degraded, nhưng vì lý do
> hoàn toàn khác: một node t3.large hết IP làm 5 pod kẹt `ContainerCreating`. Không liên
> quan Kyverno hay chuỗi cung ứng.
