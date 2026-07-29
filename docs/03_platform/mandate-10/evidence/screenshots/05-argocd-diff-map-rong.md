# 05 — Vì sao ArgoCD báo OutOfSync vĩnh viễn

![](05-argocd-diff-map-rong.png)

**Chụp:** 23/07/2026 22:25 · ArgoCD UI
**Chứng minh:** phụ trợ — tránh hiểu nhầm policy hỏng

## Trong ảnh có gì

Diff của ArgoCD trên CRD `deletingpolicies.policies.kyverno.io`. Bên phải (live) thừa hai
dòng được tô xanh: `annotations: {}` và `labels: {}`.

## Vì sao đáng chụp

Chart Kyverno khai hai map **rỗng**. Kubernetes không lưu field rỗng, nên khi ArgoCD đọc
về thì hai dòng đó biến mất. So Git với cluster thấy lệch, và vì bản chất là "Git có, live
không bao giờ có", diff này **không bao giờ hết** — OutOfSync vĩnh viễn.

Đây là drift cosmetic, hoàn toàn vô hại. Chụp lại để sau này không ai nhìn thấy chữ
OutOfSync rồi tưởng policy chưa lên hoặc đã hỏng. Dọn được bằng cách thêm 2 `jsonPointer`
vào `ignoreDifferences`, nhưng không gấp.

Liên quan: [07](07-argocd-apps-sau-flip.md) (chỗ chữ OutOfSync xuất hiện)
