# Mandate 17 — 2-Environment Change Impact Evidence

> Theo chuẩn Environment Organization & Change Impact Guide (mục 18: required evidence).
> Nhánh: `feat/mandate-17-resilience-containment`. Ngày: 2026-07-21.

## 1. Phân loại thay đổi (impact type)

| Thay đổi | Loại | Env ảnh hưởng |
|---|---|---|
| `platform/charts/application/**` (R1/R2/R4 + NP template) | **Shared** | Develop + Sandbox |
| `terraform/modules/eks/**` (variable enable_network_policy) | **Shared module** | Develop + Sandbox (capability) |
| `terraform/environments/sandbox/main.tf` (enable=true) | Env-specific | Sandbox |
| `terraform/environments/develop/main.tf` (enable=true) | Env-specific | Develop |
| `gitops/environments/sandbox/values-*` (egress label) | Env-specific | Sandbox |
| `gitops/environments/develop/values/values-application.yaml` (CIDR 10.60) | Env-specific | Develop |

→ Shared chart + shared module ⇒ **bắt buộc render/plan CẢ 2 env** (mục 5, 20-rule-5).

## 2. Helm render evidence (cả 2 env)

| Render | NetworkPolicy | PDB | VPC CIDR |
|---|---|---|---|
| sandbox, NP off (như production hiện tại) | **0** | 10 | — |
| sandbox, NP on | 31 | 10 | **10.0.0.0/16** |
| develop, NP off | **0** | 10 | — |
| develop, NP on | 31 | 10 | **10.60.0.0/16** |

- File render: `render-{sandbox,develop}-np-{off,on}.yaml` (cùng thư mục).
- NP off = 0 policy ở CẢ 2 → merge không tạo NetworkPolicy nào (an toàn, không siết traffic).
- CIDR đúng per-env (sandbox 10.0 / develop 10.60) → egress API-server + datastore trỏ đúng VPC mỗi env.
- PDB=10 cả 2 (money-path đủ PDB).

## 3. Terraform plan intent (cả 2 root)

- **modules/eks** thêm `variable enable_network_policy` (default false) + `configuration_values` cho addon vpc-cni khi bật.
- **sandbox root**: `enable_network_policy = true` → plan: `aws_eks_addon["vpc-cni"]` update in-place (`+ enableNetworkPolicy = "true"`). Đã thấy trên CI infra-cd (0 add, 1 change, 0 destroy).
- **develop root**: `enable_network_policy = true` → plan tương tự cho cluster `ecommerce-develop-dev-eks` (account 458). Chạy qua CI `infra-develop.yaml`.
- Cả 2: **không add/destroy**, chỉ update in-place addon → không destructive.

## 4. Execution context (mục 10) — tách bạch

| | Develop | Sandbox |
|---|---|---|
| Terraform root | environments/develop | environments/sandbox |
| State key | develop/terraform.tfstate | dev/terraform.tfstate |
| Account | 458580846647 | 804372444787 |
| CI | infra-develop.yaml | infra-cd.yaml |
| EKS | ecommerce-develop-dev-eks | ecommerce-dev-eks |
| Namespace | techx-develop | techx-tf1 |

## 5. ⚠️ Blast radius khi merge nhánh → branch `develop`

**Cả 2 ArgoCD cùng theo branch `develop`, nhưng sync policy KHÁC nhau (verify live):**
- Sandbox `techx-corp`: **auto-sync + prune + selfHeal** → tự áp chart change (R2/R4 + label; NP vẫn off).
- Develop `develop-techx-corp`: **manual** → không tự áp, chờ sync tay.

⇒ Merge vào develop **tự áp R2/R4 lên SANDBOX ngay** (rollout pod, NP off nên an toàn), còn **develop không đổi cho tới khi sync tay**.
⇒ Muốn giữ đúng "develop trước": **pause auto-sync sandbox** (hoặc pin revision) trước khi merge, sync develop trước, verify, rồi mới cho sandbox.

Terraform: merge chỉ **plan** cả 2 CI (không auto-apply). CNI enforce chỉ bật khi dispatch apply thủ công (sandbox: confirm `apply-sandbox`; develop: confirm `apply-develop`).

## 6. Rollback
- App: `networkPolicy.enabled` giữ false (mặc định) → chưa cần rollback; nếu đã bật thì set false + sync.
- Terraform: `enable_network_policy = false` + apply.
- Không destructive, không đổi state key, không đổi Argo root path.
