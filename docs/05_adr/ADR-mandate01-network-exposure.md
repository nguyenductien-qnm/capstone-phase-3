# ADR-Mandate01: Hoàn thiện Tailscale Kubernetes Operator cho Private Ops Access

- **Status:** Accepted (implemented & verified)
- **Date:** 2026-07-30
- **Owner (ký):** Hung Nguyen Do Khanh
- **Deciders:** Task Force CDO
- **Mandate nguồn:** `xbrain-learners/phase3/mandates/MANDATE-01-network-exposure.md`
  ("[DIRECTIVE #1] Storefront công khai, mọi cổng vận hành phải riêng tư")
- **ADR liên quan:** `docs/05_adr/ADR-log-cdo05.md` § ADR-001 (quyết định kiến trúc gốc,
  2026-07-13) — file này bổ sung phần **thực thi thực tế bị thiếu + cách khôi phục**, không
  thay đổi kiến trúc đã chọn.
- **Evidence:** PR [#501](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/501),
  PR [#502](https://github.com/nguyenductien-qnm/capstone-phase-3/pull/502)

---

## Bối cảnh: Mandate yêu cầu gì

Ban Hạ tầng & Bảo mật yêu cầu (Directive #1): storefront giữ public, nhưng **mọi cổng vận
hành** (Grafana, Jaeger, ArgoCD, và tương đương) **không được public** — chỉ vào được qua
VPN/tunnel/mạng riêng do team tự chọn công cụ. Mentor/BTC vẫn phải vào được để chấm.

Ngày 2026-07-13, team đã ra quyết định kiến trúc (ADR-001): dùng **Tailscale Kubernetes
Operator** để expose Grafana/Jaeger/ArgoCD/Locust qua 4 Tailscale L7 `Ingress`, mỗi endpoint
có MagicDNS + TLS + tag ACL riêng.

**Vấn đề phát hiện khi audit hạ tầng (2026-07-30):** quyết định đó **chưa từng được thực thi
đầy đủ**. Thư mục `platform/gitops/tailscale/` trong git chỉ có 4 file `Ingress` + 1
ConfigMap — không có bất kỳ manifest nào cài đặt **Operator**. Hệ quả:

- Cluster không có `IngressClass tailscale`.
- AWS Load Balancer Controller admission webhook từ chối cả 4 `Ingress`
  (`invalid ingress class: IngressClass "tailscale" not found`).
- ArgoCD app `tailscale-ingress` kẹt vĩnh viễn ở `OutOfSync` / `Missing`.
- Không có OAuth client secret nào cho Operator — không trong git, không trong AWS Secrets
  Manager.

Đối chiếu tailnet thật (console.tailscale.com) cho thấy Operator **từng chạy** (5 máy
`tailscale-operator`, `argocd-tf1`, `grafana-tf1`, `jaeger-tf1`, `locust-tf1` — tất cả last
seen cùng lúc **28/07**), rồi biến mất cùng thời điểm nodegroup EKS bị tạo lại (29/07). Vì
cấu hình cài Operator chưa từng nằm trong GitOps, không có gì tự dựng lại sau khi node cũ mất
— **gap giữa "quyết định" và "triển khai bền vững"**, không phải lỗi cấu hình.

---

## Vì sao chọn Tailscale (nhắc lại, không đổi quyết định gốc)

Trước khi chốt Tailscale, team đã cân 4 phương án
(`docs/03_platform/mandate-01/network-exposure-report.md`):

| Phương án | Bảo mật | Chi phí | Độ khó | Trải nghiệm mentor |
|---|---|---|---|---|
| SSM Port-Forwarding | Rất cao (Zero-Trust) | $0 | Dễ/TB | Phải cài AWS CLI + SSM plugin |
| SSH Bastion | Trung bình (lộ port 22) | Tốn EC2 24/7 | Dễ | Cần file `.pem` |
| Cloudflare Zero Trust Tunnel | Rất cao (OAuth) | $0 (free tier) | Rất khó | Tốt nhất, nhưng setup domain/DNS phức tạp trong 3 tuần |
| **Tailscale (đã chọn)** | Cao | $0 (≤6 user, ≤50 tagged resource) | Trung bình | Chỉ cần cài Tailscale client + mở URL |

Report ban đầu nghiêng về SSM Tunnel (không cần cài phần mềm phía mentor), nhưng ADR-001 cuối
cùng chọn **Tailscale** vì cân bằng tốt nhất giữa trải nghiệm mentor (không cần nhớ lệnh AWS
CLI), TLS/MagicDNS tự động theo từng service, và ACL tách theo tag
(`tag:ops-grafana/jaeger/argocd/locust`) thay vì một quyền truy cập chung chung như SSM.

---

## Quyết định lần này: hoàn thiện phần thực thi bị thiếu

Giữ nguyên kiến trúc ADR-001. Bổ sung đúng phần còn thiếu — **cài Operator qua Helm, quản lý
100% bằng GitOps (ArgoCD)**, không `helm install` tay, để lần sau node/cluster có bị tạo lại
thì ArgoCD tự dựng lại toàn bộ, không lặp lại gap lần này.

### Cách triển khai

**1. Terraform (`terraform/environments/sandbox/tailscale.tf`)** — tạo OAuth client secret
trong AWS Secrets Manager (`ecommerce-dev-tailscale-oauth`), giá trị `client_id`/
`client_secret` chỉ nhận qua `TF_VAR_tailscale_oauth_client_id`/`_client_secret`, không bao
giờ commit. Cấp quyền đọc secret này cho IRSA role của External Secrets Operator
(`terraform/environments/sandbox/main.tf`, thêm ARN vào `secret_arns`).

**2. GitOps — sinh Secret trong cluster** (`platform/gitops/tailscale/`):
   - `operator-secretstore.yaml`: `SecretStore` trỏ AWS Secrets Manager trong namespace
     `tailscale`.
   - `operator-oauth-external-secret.yaml`: `ExternalSecret` sinh Secret tên **`operator-oauth`**
     với key `client_id`/`client_secret` — đây là tên/key mặc định mà chart `tailscale-operator`
     tự tìm khi `oauth.clientId` không set trong Helm values (xác nhận qua source
     `values.yaml` của chart + GitHub issue #18244 của tailscale/tailscale) — nhờ vậy secret
     không bao giờ đi qua Helm values / git.

**3. ArgoCD Application cho Helm chart** (`platform/gitops/applications/tailscale-operator.yaml`):
   chart chính thức `tailscale-operator` (repo `https://pkgs.tailscale.com/helmcharts`,
   version `1.98.9` — chọn bản sau `1.92.3` vì bản đó có bug không mount đúng OAuth secret
   pre-created). `sync-wave: "-1"` để chạy **trước** app `tailscale-ingress` đã có sẵn, đảm
   bảo `IngressClass tailscale` tồn tại trước khi 4 `Ingress` được apply.

**4. CI (`​.github/workflows/infra-cd.yaml`)**: bổ sung `TF_VAR_tailscale_oauth_client_id`/
   `_client_secret` từ GitHub Environment secrets (`sandbox`) vào cả job `terraform-plan` và
   `terraform-apply`, theo đúng pattern đã có của `audit_slack_webhook_url` — nếu không, mọi
   lần CI plan sau này sẽ fail vì thiếu biến bắt buộc.

**5. Sự cố phụ trong lúc triển khai (đáng ghi lại):**
   - Ban đầu định thêm Terraform vào `terraform/environments/develop/` — sai root. Xác minh
     lại bằng `providers.tf`/backend config + tag thực tế trên AWS, phát hiện hạ tầng đang
     chạy thật nằm ở `terraform/environments/sandbox/` (`develop` là root khác, account khác,
     README ghi rõ "Do not run the main Develop root locally"). Đã revert và làm lại đúng root.
   - `terraform plan` scoped bằng `-target` ban đầu kéo theo thay đổi ngoài ý muốn: 3 subnet
     bị đổi tag `kubernetes.io/cluster/ecommerce-dev-eks` → `auzema-dev-eks` do file
     `terraform.auto.tfvars` local có placeholder sai — tag này là thứ AWS Load Balancer
     Controller dùng để tự tìm subnet, đổi nhầm có thể ảnh hưởng việc tạo ALB. Phát hiện qua
     review plan (đúng theo terraform.md: luôn đọc kỹ output trước khi apply), sửa tfvars local
     rồi plan lại — kết quả sạch: `2 to add, 1 to change, 0 to destroy`.
   - `develop` có branch protection (chặn push thẳng, bắt buộc PR + 7/7 status check) — tách
     commit sang branch riêng, mở PR thay vì force push.
   - Sau khi merge, tên MagicDNS bị thêm hậu tố `-1` (`grafana-tf1-1.tail101540.ts.net`) do 5
     máy cũ (từ lần chạy 28/07) vẫn còn đăng ký trong tailnet dù offline. Xoá 5 máy cũ trên
     Tailscale console, sau đó xoá luôn Secret + Pod trạng thái cũ của 4 proxy trong cluster
     (`kubectl delete secret/pod ts-*-0 -n tailscale`) để buộc đăng ký lại từ đầu — StatefulSet
     tự tạo lại pod, nhận đúng hostname sạch không hậu tố.

---

## Kết quả (verified 2026-07-30)

| Kiểm tra | Kết quả |
|---|---|
| `kubectl get ingressclass` | `tailscale` tồn tại (controller `tailscale.com/ts-ingress`) |
| ArgoCD `tailscale-operator` | `Synced` / `Healthy` |
| ArgoCD `tailscale-ingress` | `Synced` / `Healthy` |
| Pod `operator-*` (namespace `tailscale`) | `Running`, không crash loop |
| Pod `ts-argocd-ts-*`, `ts-grafana-ts-*`, `ts-jaeger-ts-*`, `ts-locust-ts-*` | `Running 1/1` |
| Secret `operator-oauth` | Tồn tại, đủ 2 key (`client_id`, `client_secret`) |
| Tailscale admin console — 5 máy | `Connected`, đúng tag (`tag:ops-*`, `tag:k8s-operator`) |
| `kubectl get ingress -A` — ADDRESS | 4/4 có MagicDNS hostname sạch |

**Endpoint truy cập riêng tư (chỉ vào được từ trong tailnet):**

```
https://argocd-tf1.tail101540.ts.net
https://grafana-tf1.tail101540.ts.net
https://jaeger-tf1.tail101540.ts.net
https://locust-tf1.tail101540.ts.net
```

Khớp đúng format trong `docs/03_platform/mandate-01/runbook_tailscale_ops_access.md` — mentor
chỉ cần được mời vào tailnet (`group:ops-reviewers`) và cài Tailscale client, không cần
`kubectl`, AWS CLI hay Helm.

---

## Alternatives đã cân nhắc (cho lần khắc phục này)

- **Chấp nhận hậu tố `-1` vĩnh viễn, chỉ cập nhật link trong runbook:** khả thi, ít rủi ro
  hơn, nhưng làm tài liệu lệch khỏi format gốc mentor đã quen. Bị loại vì việc reclaim tên
  sạch chỉ tốn xoá 5 máy cũ + restart 4 pod, rủi ro thấp, không ảnh hưởng storefront.
- **`helm install` tay trực tiếp** (không qua ArgoCD): nhanh hơn ngắn hạn, nhưng đúng là
  nguyên nhân gốc của sự cố lần này (Operator "sống" ngoài git, mất là mất luôn khi node đổi).
  Bị loại vì lặp lại gap đã audit ra.
- **Terraform `helm_release` resource** thay vì ArgoCD Application: bị loại vì repo đã có quy
  ước rõ ràng "Terraform CHỈ dựng hạ tầng, ArgoCD KHÔNG cài bằng helm_release" (comment trong
  `infra-cd.yaml`) — giữ nhất quán với toàn bộ platform layer còn lại (external-dns, karpenter,
  kyverno... đều là ArgoCD Application).

---

## Consequences

- **+ Security:** đúng yêu cầu Directive #1 — ops endpoints không public, ACL tách theo tag,
  audit được qua Tailscale admin console.
- **+ Auditability:** toàn bộ cấu hình Operator giờ nằm trong Git (ArgoCD Application +
  ExternalSecret), `selfHeal: true` — node/cluster bị thay thế trong tương lai sẽ tự dựng lại,
  không lặp lại gap lần này.
- **+ Cost:** $0 — vẫn trong hạn free plan Tailscale (≤6 user, ≤50 tagged resource).
- **− Phụ thuộc control plane Tailscale:** nếu Tailscale (SaaS) gặp sự cố, ops access mất theo
  dù cluster vẫn khoẻ. Chấp nhận rủi ro vì storefront không đi qua đường này.
- **− OAuth client cần refresh thủ công:** nếu client secret bị revoke/hết hạn, Operator
  ngừng đăng ký máy mới — cần quy trình xoay secret (rotate qua Secrets Manager + restart
  Operator pod), chưa tự động hoá.
- **Bài học:** một quyết định ADR "Accepted" không đồng nghĩa đã triển khai xong — cần thêm
  bước xác minh định kỳ (vd. `kubectl get ingressclass` trong health-check script) để phát
  hiện sớm nếu phần thực thi bị thiếu/rớt, thay vì chỉ phát hiện khi audit thủ công.

---

## Rollback

Gỡ theo đúng thứ tự ngược: xoá ArgoCD Application `tailscale-operator` (Operator + IngressClass
biến mất, 4 `Ingress` cũ quay lại `Missing` nhưng không ảnh hưởng storefront) → xoá
`ExternalSecret`/`SecretStore` trong `platform/gitops/tailscale/` → `terraform destroy
-target=aws_secretsmanager_secret.tailscale_oauth` (chỉ nếu chắc chắn không dùng lại secret).
Storefront (Envoy `frontend-proxy`) không nằm trên đường phụ thuộc này nên không bị ảnh hưởng
ở bất kỳ bước nào.

---

## Tham chiếu

- [Tailscale Kubernetes Operator Helm chart values.yaml](https://github.com/tailscale/tailscale/blob/main/cmd/k8s-operator/deploy/chart/values.yaml)
- [GitHub issue #18244 — pre-created `operator-oauth` secret behavior](https://github.com/tailscale/tailscale/issues/18244)
- `docs/03_platform/mandate-01/network-exposure-report.md` — phân tích 4 phương án gốc
- `docs/03_platform/mandate-01/runbook_tailscale_ops_access.md` — hướng dẫn truy cập cho mentor
- `docs/05_adr/ADR-log-cdo05.md` § ADR-001 — quyết định kiến trúc gốc
