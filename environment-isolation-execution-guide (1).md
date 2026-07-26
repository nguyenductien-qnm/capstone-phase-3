# Environment Organization & Change Impact Guide

> Phạm vi: Terraform, GitHub Actions, GitOps, Argo CD và Helm  
> Môi trường: Develop và Product-like/Sandbox  
> Quyết định account: [Multi-account Decision](./multi-account-decision.md)

## Mục tiêu tài liệu

Tài liệu được chia thành hai phase:

```text
Phase 1: Hiểu cách repo và environments đang được tổ chức
         + kế hoạch restructure trong tương lai

Phase 2: Hiểu change impact
         + ảnh hưởng riêng
         + ảnh hưởng chéo
         + execution mismatch
         + destructive changes
```

Sau khi đọc, thành viên team phải trả lời được:

1. File mình đang sửa thuộc môi trường nào?
2. File đó là environment-specific hay shared?
3. Thay đổi có ảnh hưởng Develop, Sandbox hay cả hai?
4. Workflow đang chạy dùng root, state và AWS account nào?
5. GitOps destination có đúng cluster/namespace không?
6. Cần plan/render những môi trường nào trước khi merge?

---

# Phase 1 — Current organization và restructure plan

## 1. View tổng thể

```text
Terraform code + environment inputs
        -> plan/apply
        -> AWS: VPC, EKS, RDS, Valkey, MSK, IAM, ECR, DNS

Application code
        -> CI test/build/scan/sign
        -> immutable image trong ECR
        -> cập nhật desired state trong Git
        -> Argo CD + Helm
        -> Kubernetes workloads
```

Ranh giới ownership:

- Terraform quản lý AWS infrastructure, EKS cluster và IAM.
- GitOps quản lý desired state bên trong Kubernetes.
- CI build và kiểm chứng artifact.
- Argo CD reconcile Git với đúng Kubernetes cluster.
- Không để Terraform và Argo CD cùng sở hữu một Kubernetes resource.

## 2. Phân tách môi trường hiện tại

| Thành phần         | Develop                                        | Product-like/Sandbox             |
| ------------------ | ---------------------------------------------- | -------------------------------- |
| AWS account        | `458580846647`                                 | `804372444787`                   |
| Terraform root     | `terraform/environments/develop`               | `terraform/environments/sandbox` |
| State key          | `develop/terraform.tfstate`                    | `dev/terraform.tfstate`          |
| Workflow           | `infra-develop.yaml`                           | `infra-cd.yaml`                  |
| EKS cluster        | `ecommerce-develop-dev-eks`                    | `ecommerce-dev-eks`              |
| Namespace          | `techx-develop`                                | `techx-tf1`                      |
| GitOps root        | `environments/develop/bootstrap/root-app.yaml` | `bootstrap/root-app.yaml`        |
| Capacity           | 2 workload cố định + 1 Ops                     | Workload 2-6 + 1 Ops             |
| Argo sync hiện tại | Manual                                         | Auto-sync, prune, self-heal      |
| ECR                | Pull cross-account                             | Sở hữu shared ECR                |

Dùng chung:

- Terraform modules;
- Helm application chart;
- application source code;
- Git repository và branch `develop`;
- ECR artifact registry hiện tại.

Tách riêng:

- AWS account và IAM identity;
- Terraform state;
- VPC/EKS/data services;
- Argo CD instance và root Application;
- namespace, values và secret scope.

## 3. Terraform organization hiện tại

```text
terraform/
├── modules/                    # Implementation dùng chung
│   ├── vpc/
│   ├── eks/
│   ├── rds/
│   ├── elasticache/
│   ├── msk/
│   └── ...
│
├── environments/develop/       # Composition của Develop
│   ├── main.tf
│   ├── variables.tf
│   ├── providers.tf
│   ├── outputs.tf
│   └── develop-capacity.tfvars
│
└── environments/sandbox/       # Composition của Sandbox
    ├── main.tf
    ├── variables.tf
    ├── providers.tf
    ├── outputs.tf
    ├── primary-capacity.tfvars
    └── primary-schedule.tf
```

| File | Vai trò |
|---|---|
| `main.tf` | Chọn và nối shared modules |
| `variables.tf` | Input contract, type và validation |
| `providers.tf` | Provider, account guard và backend |
| `outputs.tf` | Kết quả sau khi đọc/apply state |
| `*.tfvars` | Environment policy không nhạy cảm |
| `modules/**` | Capability dùng chung |

### 3.1 Input, output và state

```text
GitHub Variables + environment tfvars
        -> variables.tf
        -> main.tf/modules
        -> AWS resources
        -> outputs.tf + Terraform state
```

- GitHub Environment chứa Terraform inputs, không phải Terraform outputs.
- `outputs.tf` là kết quả sau khi Terraform đọc hoặc apply state.
- State quyết định Terraform root đang sở hữu tài nguyên nào.
- Hạn chế copy output thủ công trở lại GitHub Variables vì dễ drift.

### 3.2 Nguồn variables hiện tại

- Develop lấy phần lớn input từ GitHub Environment `develop`.
- Sandbox lấy phần lớn input từ GitHub Repository Variables.
- Capacity nằm trong `develop-capacity.tfvars` và `primary-capacity.tfvars`.
- Explicit `-var-file` thắng `TF_VAR_*` khi trùng key.

Workflow thực hiện mapping:

```text
GitHub: TF_VAR_VPC_CIDR
        -> Runner: TF_VAR_vpc_cidr
        -> Terraform variable "vpc_cidr"
```

### 3.3 Giá trị nên nằm ở đâu

Nên để trong Git:

- network topology;
- EKS/RDS/Valkey/MSK sizing;
- HA, proxy và replica policy;
- scheduled scaling;
- cấu hình không nhạy cảm cần PR review.

Chỉ nên giữ trong GitHub Environment:

- AWS account và OIDC role;
- backend bucket/key/region;
- bootstrap values phụ thuộc account;
- secrets và tokens.

## 4. GitOps organization hiện tại

```text
platform/
├── charts/application/                 # Shared Helm chart
│   ├── templates/
│   └── values.yaml                     # Shared defaults
│
└── gitops/
    ├── bootstrap/root-app.yaml          # Product-like root
    ├── applications/                    # Product-like Applications
    │   ├── application.yaml
    │   ├── external-secrets.yaml
    │   ├── external-dns.yaml
    │   ├── metrics-server.yaml
    │   ├── karpenter.yaml
    │   └── ...
    │
    └── environments/
        ├── sandbox/                     # Product-like values
        └── develop/
            ├── bootstrap/
            ├── applications/
            ├── values/
            ├── karpenter/
            └── public-exposure/
```

Product-like flow:

```text
Product-like Argo CD
-> platform/gitops/bootstrap/root-app.yaml
-> platform/gitops/applications/**
-> shared chart + sandbox values
-> namespace techx-tf1
```

Develop flow:

```text
Develop Argo CD
-> environments/develop/bootstrap/root-app.yaml
-> environments/develop/applications/**
-> shared chart + develop values
-> namespace techx-develop
```

GitOps isolation được xác định bởi:

```text
Argo instance
+ root path
+ destination cluster
+ namespace
+ environment values
+ IAM/secret scope
+ image digest
+ sync policy
```

## 5. Helm values layering

Shared base:

```text
platform/charts/application/values.yaml
```

Develop overrides:

```text
values-application.yaml
-> values-ops-observability.yaml
-> values-external-secrets.yaml
-> values-single-replica.yaml
-> values-image-tags.yaml
```

Sandbox overrides:

```text
values-flagd-sync.yaml
-> values-ops-observability.yaml
-> values-external-secrets.yaml
-> values-aio-llm.yaml
-> values-image-tags.yaml
```

File load sau override file trước. Reviewer phải kiểm tra effective values sau merge, không kết luận từ một file riêng lẻ.

| Layer | Nên chứa |
|---|---|
| Shared `values.yaml` | Default không phụ thuộc môi trường |
| Environment values | Replica, HPA, ingress, scheduling và secret reference |
| Image values | Immutable tag/digest được promotion |
| Argo Application | Chart path, values order, destination và sync policy |

## 6. Những điểm chưa đồng nhất hiện tại

| Hiện trạng | Vấn đề |
|---|---|
| Product-like Applications nằm ở `gitops/applications` | Không thể hiện rõ đây là Sandbox scope |
| Develop có đủ `bootstrap/applications/values` dưới environment | Layout hai môi trường không đối xứng |
| Develop dùng Environment Variables, Sandbox dùng Repository Variables | Source of truth khác nhau |
| Nhiều non-secret inputs nằm ngoài Git | Khó review và tái tạo từ commit |
| `TFVARS_SANDBOX` tồn tại nhưng không dùng | Gây nhầm nguồn input thực tế |
| Shared chart chủ yếu được CI render với Sandbox values | Develop có thể lỗi muộn |
| Shared module chưa luôn plan cả hai roots | Không thấy đầy đủ blast radius |
| Develop image tags là snapshot riêng | Promotion flow chưa thống nhất |
| Applications chủ yếu dùng `project: default` | Destination permission còn rộng |

## 7. Restructure plan đề xuất

Đây là target organization, chưa phải current state:

```text
terraform/
├── modules/
└── environments/
    ├── develop/
    │   ├── main.tf
    │   ├── variables.tf
    │   ├── providers.tf
    │   ├── outputs.tf
    │   └── environment.tfvars
    ├── sandbox/
    │   ├── main.tf
    │   ├── variables.tf
    │   ├── providers.tf
    │   ├── outputs.tf
    │   └── environment.tfvars
    └── prod/

platform/gitops/
├── charts/application/              # Shared chart giữ nguyên
└── environments/
    ├── develop/
    │   ├── bootstrap/
    │   ├── applications/
    │   └── values/
    ├── sandbox/
    │   ├── bootstrap/
    │   ├── applications/
    │   └── values/
    └── prod/
```

Mục tiêu restructure:

- layout Develop/Sandbox đối xứng;
- nhìn path biết ngay ownership;
- non-secret desired configuration được review trong Git;
- shared code nằm ngoài environment directories;
- CI dễ route plan/render theo path;
- chuẩn bị sẵn convention cho Production.

### 7.1 Workflow target

```text
infra-plan.yaml                 # reusable/matrix plan
infra-apply-develop.yaml        # Develop approval + account guards
infra-apply-sandbox.yaml        # Sandbox approval + account guards
gitops-validate.yaml            # render matrix
promote-image.yaml              # Develop -> Sandbox digest promotion
```

Shared validation có thể reuse, nhưng apply workflows nên giữ environment-specific guards để tránh truyền nhầm account/state bằng input tự do.

### 7.2 Migration phải theo phase

```text
Step 1: Inventory current ownership và references
Step 2: Tạo target paths nhưng chưa xóa legacy paths
Step 3: Plan/render old và new, chứng minh parity
Step 4: Update workflow path filters và Argo roots
Step 5: Tạm tắt prune khi chuyển Argo root path
Step 6: Quan sát runtime và drift
Step 7: Xóa legacy paths sau khi ổn định
```

Guard khi restructure:

- không đổi Terraform state key chỉ vì đổi folder;
- không chạy `terraform state mv` nếu resource address không đổi;
- không chuyển Argo root path cùng lúc với bật prune;
- không xóa legacy Applications trước khi new root healthy;
- update tất cả CI path filters;
- render cả hai environments trước merge;
- có rollback commit/path rõ ràng.

---

# Phase 2 — Change impact và environment isolation

## 8. Khái niệm change impact

| Loại impact | Ý nghĩa |
|---|---|
| Direct/local impact | File chỉ được một environment root đọc |
| Shared impact | File được nhiều environments sử dụng |
| Execution mismatch | Source đúng nhưng workflow/state/account sai |
| Indirect dependency impact | Thay đổi shared external dependency như ECR/DNS |
| Control-plane impact | Thay đổi cluster-wide controller, CRD hoặc Argo root |
| Destructive impact | Destroy, prune, replace hoặc data deletion |

Mọi thay đổi phải xác định loại impact trước khi merge.

## 9. Change-impact decision tree

```text
File có nằm trong shared module/chart/workflow không?
|
├── Có -> mặc định ảnh hưởng Develop + Sandbox
|         -> plan/render cả hai
|
└── Không
    |
    ├── nằm trong develop/** -> candidate impact: Develop
    └── nằm trong sandbox/** -> candidate impact: Sandbox

Sau đó kiểm tra:

Execution root có đúng không?
Backend/state có đúng không?
AWS account có đúng không?
Argo destination/namespace có đúng không?
Có cross-account/shared dependency không?
Có destroy/prune/replace không?
```

Folder chỉ xác định candidate scope. Execution context và dependencies mới xác định actual blast radius.

## 10. Terraform execution context

Một lần chạy Terraform chỉ an toàn khi khớp toàn bộ:

```text
Terraform root
+ input variables
+ shared modules
+ backend/state
+ AWS identity/account
+ reviewed plan artifact
```

Develop context:

```text
root     = terraform/environments/develop
state    = develop/terraform.tfstate
account  = 458580846647
identity = Develop Terraform role
```

Sandbox context:

```text
root     = terraform/environments/sandbox
state    = dev/terraform.tfstate
account  = 804372444787
identity = Product-like Terraform role
```

Chỉ cần một thành phần trỏ nhầm là execution phải dừng.

## 11. Terraform impact matrix

| Thay đổi | Direct impact | Cross impact | Required evidence |
|---|---|---|---|
| `develop/environment.tfvars` hoặc capacity file | Develop | Không, nếu không có shared change | Develop plan |
| `sandbox/environment.tfvars` hoặc capacity file | Sandbox | Không | Sandbox plan |
| `develop/main.tf` composition | Develop | Có nếu đồng thời sửa module | Develop plan |
| `sandbox/main.tf` composition | Sandbox | Có nếu đồng thời sửa module | Sandbox plan |
| `modules/eks/**` | Develop + Sandbox | Có | Hai plans |
| `modules/rds/**` | Develop + Sandbox | Có | Hai plans + data review |
| `providers.tf` | Environment root tương ứng | State/account mismatch risk | Backend + STS evidence |
| Backend key/bucket | State ownership | Có thể quản nhầm toàn môi trường | Critical review |
| Terraform workflow | Root workflow quản lý | Có thể inject sai account/state | Workflow validation |
| Sandbox ECR module/policy | Sandbox ECR | Develop pull cross-account | ECR dependency check |
| Destroy workflow | Target environment | Shared resources/data | Destructive approval |

## 12. Terraform cases

### Case T1 — Sửa Develop-only file

```text
Change: terraform/environments/develop/develop-capacity.tfvars
Expected impact: Develop
Required: Develop plan
Sandbox expectation: No changes
```

Nếu Sandbox plan xuất hiện change dù chỉ sửa Develop file, phải dừng và kiểm tra shared inputs/state/workflow.

### Case T2 — Sửa Develop và shared module

```text
Change:
- environments/develop/main.tf
- modules/eks/main.tf

Impact:
- Develop composition change
- Develop + Sandbox shared EKS behavior
```

Required evidence:

- Develop plan;
- Sandbox plan;
- review replace/destroy;
- apply Develop trước;
- smoke test rồi re-plan Sandbox.

### Case T3 — Feature chỉ dành cho Develop nhưng nằm trong shared module

Cách sai:

```hcl
# Hard-code behavior mới trong shared module
desired_size = 2
```

Cách đúng:

```hcl
variable "enable_feature" {
  type    = bool
  default = false
}
```

```text
Develop: enable_feature = true
Sandbox: enable_feature = false
```

Module cung cấp capability; environment root quyết định policy.

### Case T4 — Sửa Develop nhưng chạy Sandbox CD

Nếu workflow dùng Sandbox root/state/account, Terraform không đọc Develop files.

```text
Expected: Sandbox No changes
```

Không apply một plan không liên quan chỉ vì workflow đã chạy thành công.

### Case T5 — Develop root nhưng Sandbox backend

```text
root  = develop
state = dev/terraform.tfstate
```

Severity: Critical.

Workflow phải validate root-to-state mapping trước `terraform init`.

### Case T6 — Develop root nhưng Sandbox AWS role

```text
Expected account = 458580846647
Actual account   = 804372444787
```

Severity: Critical. Dừng trước plan bằng provider guard, `allowed-account-ids` và STS check.

### Case T7 — Thay đổi Sandbox ECR lifecycle/policy

ECR thuộc Sandbox account nhưng Develop pull images cross-account.

Impact có thể gồm:

- Develop `ImagePullBackOff`;
- image digest bị lifecycle xóa;
- node role Develop mất pull permission.

Đây là cross-account impact dù file nằm trong Sandbox root.

### Case T8 — Terraform destroy Develop

Expected impact: Develop runtime.

Phải kiểm tra:

- correct Develop account/state;
- snapshot/data policy;
- Kubernetes LoadBalancer/PVC pre-clean;
- không thay đổi shared ECR;
- orphan ENI/EBS/LB sau destroy.

### Case T9 — Terraform destroy Sandbox

Severity: Critical.

Sandbox sở hữu shared ECR, public endpoint và Product-like data. Full destroy không phải cleanup thông thường và có thể ảnh hưởng Develop.

Required:

- ECR dependency migration/retention;
- data retention decision;
- downtime approval;
- full destroy inventory;
- cross-account consumer review.

## 13. Terraform CI routing

```text
develop/**   -> plan Develop
sandbox/**   -> plan Sandbox
modules/**   -> plan Develop + Sandbox
bootstrap/** -> plan bootstrap riêng
workflow/**  -> validate mọi root workflow có thể chạy
```

Shared module apply order:

```text
plan cả hai
-> review
-> apply Develop
-> smoke test
-> re-plan Sandbox
-> approval
-> apply Sandbox
```

## 14. GitOps impact matrix

| Thay đổi | Direct impact | Cross impact | Required evidence |
|---|---|---|---|
| Develop values | Develop workloads | Không nếu chart không đổi | Develop render |
| Sandbox values | Sandbox workloads | Có thể ECR/public dependency | Sandbox render |
| Shared chart template | Develop + Sandbox | Có | Hai renders |
| Shared chart `values.yaml` | Develop + Sandbox | Có | Effective values diff |
| Develop Application | Develop child app | Cluster-wide nếu controller | Destination review |
| Sandbox Application | Sandbox child app | Cluster-wide nếu controller | Destination review |
| Root Application path | Toàn bộ environment tree | Prune risk | Critical review |
| Namespace/destination | Target cluster resources | Deploy nhầm môi trường | Critical review |
| ExternalSecret path/IRSA | Secret sync | Cross-account secret risk | IAM/secret review |
| Karpenter/NodePool | Cluster capacity | Workload eviction/cost | Capacity review |
| Image values | Service deployment | Shared artifact dependency | Digest evidence |

## 15. GitOps cases

### Case G1 — Sửa Develop values

```text
Change: environments/develop/values/**
Expected impact: Develop
Required: Develop Helm render + Argo diff
```

### Case G2 — Sửa shared chart

```text
Change: platform/charts/application/templates/**
Impact: Develop + Sandbox
```

Required:

- lint shared chart;
- render Develop values;
- render Sandbox values;
- compare resource deletion/rename;
- deploy Develop trước.

### Case G3 — Thay values order

File load sau override file trước. Đổi order có thể thay effective values dù nội dung từng file không đổi.

Required: render full Application value order, không chỉ lint từng file.

### Case G4 — Đổi Argo root path với prune bật

Argo có thể coi resources cũ đã biến mất khỏi Git và prune toàn bộ.

Migration phải:

1. tắt hoặc kiểm soát prune;
2. tạo new root path;
3. chứng minh object ownership/parity;
4. sync new root;
5. quan sát health;
6. xóa legacy path sau cùng.

### Case G5 — Destination namespace sai

```yaml
destination:
  namespace: techx-tf1
```

trong Develop Application có thể deploy resource Develop sang Product-like namespace nếu cluster destination cũng sai hoặc dùng shared cluster context.

AppProject phải giới hạn namespace để tạo hard guard.

### Case G6 — External Secrets role/path sai

Impact:

- workload thiếu secret;
- đọc nhầm secret prefix;
- cross-account access ngoài dự kiến.

Required:

- IRSA ARN đúng account;
- remote secret prefix đúng environment;
- ExternalSecret diff;
- smoke test SecretSynced.

### Case G7 — Karpenter/CRD change

Đây là cluster-wide impact, không phải application-local impact.

Có thể gây:

- node replacement;
- workload eviction;
- scheduling failure;
- cost tăng mạnh;
- CRD incompatibility.

Yêu cầu approval và rollout riêng.

### Case G8 — Image tag/digest change

Impact trực tiếp là service có image thay đổi. Impact gián tiếp có thể lan qua API contract hoặc downstream services.

Required:

- immutable digest tồn tại;
- vulnerability/signature gate pass;
- Develop smoke test;
- promotion evidence trước Sandbox.

## 16. GitOps CI routing

```text
shared chart       -> lint/render Develop + Sandbox
develop values     -> render Develop
sandbox values     -> render Sandbox
root/applications  -> validate project, destination, namespace, sync policy
image promotion    -> verify source digest and target environment
```

## 17. Severity model

| Severity | Ví dụ | Required control |
|---|---|---|
| Low | labels, non-functional metadata | Normal PR review |
| Medium | replica, HPA, resource requests | Environment render/plan |
| High | shared module/chart, ingress, controller version | Multi-environment evidence |
| Critical | backend, account, state, destination, root path, destroy | Hard guard + explicit approval |

Severity phụ thuộc blast radius, không phụ thuộc số dòng thay đổi.

Một thay đổi một dòng ở backend key có thể nguy hiểm hơn hàng trăm dòng application code.

## 18. Required evidence theo scope

| Scope | Evidence tối thiểu |
|---|---|
| Develop-only Terraform | Develop plan |
| Sandbox-only Terraform | Sandbox plan |
| Shared Terraform module | Develop + Sandbox plans |
| Develop-only GitOps | Develop render/diff |
| Sandbox-only GitOps | Sandbox render/diff |
| Shared Helm chart | Develop + Sandbox renders |
| Account/state/destination | Identity + backend/destination proof |
| Destroy/prune | Inventory + data policy + approval + post-check |
| Cross-account ECR | Consumer/policy/digest validation |

## 19. Review checklist

### Source scope

1. File nằm trong environment path hay shared path?
2. Có environment nào khác import file/module/chart này không?
3. Có shared ECR, DNS, IAM hoặc secret dependency không?

### Execution scope

4. Terraform root nào đang chạy?
5. Backend bucket và state key là gì?
6. AWS caller account là gì?
7. Argo destination cluster/namespace là gì?

### Change behavior

8. Có create/update/replace/destroy/prune không?
9. Có thay đổi resource address, name hoặc ownership không?
10. Có data migration hoặc data loss risk không?

### Evidence

11. Đã plan/render tất cả environments bị ảnh hưởng chưa?
12. Shared change đã kiểm chứng Develop trước chưa?
13. Rollback path là gì?
14. Saved plan/image digest/Git revision đã được ghi nhận chưa?

## 20. Team rules

1. Giải thích current organization trước khi thay đổi cấu trúc.
2. Restructure repo là migration có phase, không phải file move thông thường.
3. Xác định blast radius trước khi merge.
4. Environment path chỉ cho biết candidate scope; phải kiểm tra execution context và dependencies.
5. Shared code mặc định ảnh hưởng đa môi trường cho đến khi plan/render chứng minh ngược lại.
6. Không apply nếu root, state hoặc AWS identity không khớp.
7. Không sync nếu destination, namespace hoặc secret scope không khớp.
8. Non-secret desired config thuộc Git; identity, backend và secrets thuộc GitHub Environment.
9. Shared change phải kiểm chứng Develop trước khi apply/sync Sandbox.
10. Sandbox chỉ nhận artifact đã được kiểm chứng tại Develop.

> Hiểu cấu trúc để xác định ownership. Hiểu change impact để kiểm soát blast radius. Cả hai đều bắt buộc trước khi team restructure repo hoặc mở rộng thêm Production.
