# Mandate 13 — Hướng dẫn thực thi (Execution Guide)

> Branch: `feat/mandate-13-cost-efficiency-elastic`
> Target: Terraform/GitOps `develop`, cluster `ecommerce-develop-dev-eks`, account `458580846647`, namespace `techx-develop`
> Mandatory Reference: `environment-isolation-execution-guide (1).md` (thư mục gốc) — tất cả các bước dưới đây tuân thủ các nguyên tắc của tài liệu này, trích dẫn các case cụ thể khi cần.
> Các lệnh tự động `terraform apply`/`gh workflow run ... apply=true` sẽ không chạy thay cho bạn — đây là tài liệu hướng dẫn thực thi thủ công.

---

## 0. Biến môi trường dùng xuyên suốt

```bash
DV=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
NS=techx-develop
BRANCH=feat/mandate-13-cost-efficiency-elastic
```

## 1. Bối cảnh Multi-account (phải hiểu trước khi chạy lệnh)

| | Develop (mục tiêu của mandate này) | Sandbox (KHÔNG ĐƯỢC chạm vào) |
|---|---|---|
| AWS account | `458580846647` | `804372444787` |
| Terraform root | `terraform/environments/develop` | `terraform/environments/sandbox` |
| State key | `develop/terraform.tfstate` | `dev/terraform.tfstate` |
| Workflow | `.github/workflows/infra-develop.yaml` | `.github/workflows/infra-cd.yaml` |
| EKS cluster | `ecommerce-develop-dev-eks` | `ecommerce-dev-eks` |
| Trigger apply | `workflow_dispatch`, CHỈ chạy khi `github.ref == refs/heads/develop` | `workflow_dispatch` (plan tự động trigger trên PR/push chạm vào `terraform/modules/**`) |

`terraform/modules/eks/**` là một shared module — PR này sửa đổi nó, nên **cả hai workflow đều sẽ phản hồi**: `infra-develop.yaml` chỉ chạy kiểm tra tĩnh (fmt/validate) trên PR, trong khi `infra-cd.yaml` (sandbox) **tự động chạy một lệnh `terraform plan` thật** và comment kết quả vào PR vì path filter của nó bao gồm `terraform/modules/**`. Đây chính là cơ chế cung cấp bằng chứng "sandbox không thay đổi" ở §3.

## 2. Pre-flight checklist — hoàn thành trước khi mở PR

1. **✅ ĐÃ FIX: `terraform/environments/develop/develop-capacity.tfvars` từng đè lên `eks_node_scaling`.**
   File này được truyền vào bằng `-var-file="develop-capacity.tfvars"` trong cả bước `plan` và `apply` của `infra-develop.yaml` — theo đúng quy tắc `explicit -var-file wins over TF_VAR_*` ở §3.2 của environment-isolation guide. Các giá trị trong file này trước đây đã **đè (override)** lên các giá trị mặc định trong `variables.tf` (hardcode `min=2,max=3,desired=3`, một phần tồn đọng từ Mandate-19 Phase 2-3 dùng để đo mức trần mỗi pod). Chúng tôi đã xác nhận Mandate-19 có bằng chứng đầy đủ cho đến mức tương đương Phase 6 (22-07-2026), nên việc bỏ override là an toàn — block `eks_node_scaling` đã bị xóa khỏi file này, đưa hệ thống trở về giá trị mặc định chính xác trong `variables.tf` (`min=2,max=3,desired=2`). Đã chạy `terraform fmt -check` + `terraform validate` (tắt backend, không cần credentials) cho develop root, `terraform/modules/eks`, và sandbox root — cả ba đều trả về **Success**. Vẫn khuyên bạn nên kiểm tra kỹ dòng `desired_size` trong output của lệnh plan thật (bước 4 bên dưới) trước khi apply, để đảm bảo không còn override ngầm nào khác.
2. **✅ ĐÃ FIX: `nodepool-default.yaml` (develop) từng có `minValues: 2` trên `topology.kubernetes.io/zone`.**
   Đợt merge `origin/develop` (`c9f8b29`) kéo theo 2 commit sửa lỗi zone-requirement cho **sandbox**
   (`67e5cb2` rồi `ab5087a`) sau khi A/B test xác nhận `minValues: 2` khiến Karpenter reject **100%**
   node launch thật (mỗi NodeClaim chỉ pin 1 AZ cụ thể nên value-list co lại còn 1, trong khi
   `minValues` luôn đòi ≥2). Fix ở `ab5087a` chỉ áp cho `platform/karpenter/nodepool-default.yaml`
   (sandbox) — file **develop** (`platform/gitops/environments/develop/karpenter/nodepool-default.yaml`)
   bị sót, vẫn giữ `minValues: 2` cho tới khi phát hiện và sửa lại (đã xóa dòng `minValues`, giữ
   `operator: In` + danh sách AZ, dựa vào `topologySpreadConstraints` ở pod level để trải AZ). Nếu bạn
   thấy `kubectl get nodeclaims` không tạo được node nào dù có pod Pending, đây là nguyên nhân số 1 cần
   loại trừ trước — xem thêm bảng lỗi ở §11.
3. **⚠️ CẦN LÀM THỦ CÔNG NGAY TRƯỚC §7/§8: tắt tạm `components.load-generator.enabled` trong `values-ops-observability.yaml`.**
   PR #382 (`e052091`, cũng vào theo merge `c9f8b29`) bật lại continuous background traffic (10 user Locust
   tự chạy liên tục) để giữ telemetry Develop sống — nhưng đây chính là nguyên nhân từng khiến Mandate-19
   phải tắt nó đi ("baseline không còn là 0, mọi mẫu số mCPU/rps đều sai"). Traffic nền này cộng dồn vào pha
   "low" của `locust-loadcurve-mandate13-job.yaml` (§7) và có thể khiến node không bao giờ đạt đúng nghĩa
   "underutilized" để consolidate — làm nhiễu bằng chứng "node co xuống thật" (yêu cầu #2) và pha peak
   spot-kill (§8). File này là shared giữa các mục đích quan sát khác của team continuous-loadgen, nên
   **không sửa cứng trong repo** — trước khi chạy §7, tắt tạm qua `kubectl -n techx-develop scale ... --replicas=0`
   hoặc patch Application/Helm values tại thời điểm demo, và bật lại sau khi đã chụp xong bằng chứng nếu mục
   đích "giữ telemetry sống" của #382 vẫn cần cho việc khác.
4. Xác minh GitHub Environment `develop` có đầy đủ các biến cần thiết (`TF_AWS_ROLE_ARN`, `TF_BACKEND_BUCKET`, và tất cả `required_tf_vars` được liệt kê trong job `terraform-plan` của `infra-develop.yaml`) — nếu thiếu bất kỳ biến nào, job sẽ fail ngay tại bước "Validate GitHub Environment configuration" trước khi tương tác với AWS.
5. Xác minh repo secret `ARGOCD_REPO_TOKEN` tồn tại trong GitHub Environment `develop` nếu dự định chạy với `bootstrap_argocd=true`.
6. Đảm bảo `git status` sạch, và nhánh `feat/mandate-13-cost-efficiency-elastic` chứa đầy đủ các commit cần thiết (karpenter.tf gate, nodepool-default.yaml, root-app.yaml un-exclude, values.yaml payment, develop-capacity.tfvars...).

## 3. Phase A — Mở PR, lấy bằng chứng sandbox UNCHANGED (Case T1)

```bash
gh pr create --base develop --head "$BRANCH" \
  --title "Mandate-13: Karpenter spot autoscaling + interruption survival" \
  --body "Xem docs/cdo09/evidence-mandate-13/ cho ADR + evidence pack"
```

Sau khi mở PR:

1. Đợi `infra-cd.yaml` (sandbox) tự động chạy job `terraform-plan` (được trigger vì PR chạm vào `terraform/modules/eks/**`).
2. Mở comment plan do bot để lại trên PR — **Kỳ vọng bắt buộc: `No changes.`** cho tất cả các resource liên quan đến `karpenter_interruption`. Đây là bằng chứng cho thấy biến rào `enable_karpenter_interruption_queue` hoạt động chính xác (ADR Decision 2). Nếu comment hiển thị có thay đổi trong sandbox (ví dụ: `aws_sqs_queue.karpenter_interruption` xuất hiện) — **DỪNG LẠI**, điều này chỉ ra rào chắn bị lỗi (biến `enable_karpenter_interruption_queue` không thực sự lấy mặc định là `false`, hoặc đã bị set nhầm ở sandbox) — hãy sửa nó trước khi merge, tuyệt đối không apply.
3. Lưu link/ảnh chụp màn hình của comment này vào `docs/cdo09/evidence-mandate-13/logs/sandbox-plan-no-changes.txt` (copy nội dung comment) — đây là bằng chứng bắt buộc cho mục §2 trong `README.md` evidence pack (tuân thủ Case T3).
4. Xem lại kiểm tra tĩnh của `infra-develop.yaml` (fmt/validate) trên PR — chúng phải xanh (green).
5. Merge PR vào `develop` sau khi review xong (đợi đủ số lượng approve theo branch protection rule nếu có).

## 4. Phase B — Terraform plan + apply cho Develop

**Chỉ có thể chạy sau khi PR đã merge vào `develop`** — job `terraform-plan` trong `infra-develop.yaml` có điều kiện ngặt `github.ref == 'refs/heads/develop'`, dispatch từ các branch khác sẽ bị skip.

```bash
# Bước 1 — chỉ plan, KHÔNG apply, để xem trước diff (đặc biệt là dòng eks_node_scaling, §2.1)
gh workflow run infra-develop.yaml --ref develop \
  -f apply=false -f bootstrap_argocd=false

# Theo dõi tiến trình chạy, tải artifact "terraform-develop-plan" hoặc đọc tóm tắt trong CI log.
gh run list --workflow=infra-develop.yaml --branch develop --limit 1
gh run view <run-id> --log
```

Đọc cẩn thận output của plan, đối chiếu với ADR §Decisions:

- `aws_sqs_queue.karpenter_interruption[0]`, `aws_cloudwatch_event_rule.karpenter_interruption[0]`, `aws_cloudwatch_event_target.karpenter_interruption[0]`, `aws_sqs_queue_policy.karpenter_interruption[0]` → **to add** (vì `enable_karpenter_interruption_queue = true` chỉ được set trong develop).
- `aws_iam_role_policy.karpenter_controller` → **to update** (thêm statement `InterruptionQueue`).
- `module.eks.aws_eks_node_group.this` (`primary`) → cấu hình scaling khớp với các giá trị ĐÃ XÁC NHẬN từ bước pre-flight §2.1, không phải giá trị giả định từ `variables.tf`.
- Không có dòng nào đụng tới `terraform/environments/sandbox/**` hoặc các resource trong account `804372444787` — root này chỉ có provider trỏ tới `458580846647` (xem `providers.tf` + rào `allowed-account-ids` trong workflow).

Nếu plan khớp với kỳ vọng:

```bash
# Bước 2 — apply thật. "confirm" PHẢI bằng chính xác chuỗi "apply-develop", nếu không job apply sẽ bị bỏ qua.
gh workflow run infra-develop.yaml --ref develop \
  -f apply=true -f bootstrap_argocd=true -f confirm=apply-develop
```

`bootstrap_argocd=true` được chạy đồng thời để đăng ký/refresh Develop root Application (`platform/gitops/environments/develop/bootstrap/root-app.yaml`) — file này đã được sửa để KHÔNG CÒN exclude 3 file Karpenter (xem ADR Decision 1), nên bước bootstrap này sẽ cho phép ArgoCD phát hiện `develop-karpenter-crd`, `develop-karpenter`, và `develop-karpenter-nodepool` bên trong cây App-of-Apps. Root app có `automated: {prune:true, selfHeal:true}` (từ commit `db40817`), nên các Application con sẽ tự động được **tạo ra**, nhưng — xem §5 — bản thân 3 Application đó **không có** `syncPolicy.automated`, nên các resource bên trong chúng vẫn cần sync thủ công.

Xác minh account/state là chính xác ngay sau khi workflow hoàn thành (đối chiếu §11 của environment-isolation guide, Case T5/T6):

```bash
aws sts get-caller-identity --query Account --output text
# Kỳ vọng: 458580846647

aws s3api head-object --bucket "$TF_BACKEND_BUCKET" --key develop/terraform.tfstate >/dev/null && echo "state key OK"
```

## 5. Phase C — Manual Sync cho 3 Application Karpenter (đúng thứ tự sync-wave)

Vì `develop-karpenter-crd` (sync-wave `-2`), `develop-karpenter` (sync-wave `-1`), và `develop-karpenter-nodepool` (sync-wave `0`) đều **không có** `syncPolicy.automated` — comment trong `karpenter-nodepool.yaml` ghi rõ "Manual sync only. Review the EC2NodeClass role and discovery tags first." — nên chúng phải được sync thủ công theo ĐÚNG THỨ TỰ đó, đợi báo trạng thái Healthy ở mỗi bước rồi mới đi tiếp.

Truy cập ArgoCD qua kênh private vận hành hiện có cho cluster này (cổng vận hành không public — Directive #1 của TF, xem `platform/gitops/tailscale`), sau đó:

```bash
# Nếu dùng port-forward tạm thời thay cho kênh private hiện có:
kubectl --context "$DV" -n argocd port-forward svc/argocd-server 8080:443 &

argocd login localhost:8080 --insecure
argocd app sync develop-karpenter-crd
argocd app wait develop-karpenter-crd --health --timeout 120

argocd app sync develop-karpenter
argocd app wait develop-karpenter --health --timeout 180

argocd app sync develop-karpenter-nodepool
argocd app wait develop-karpenter-nodepool --health --timeout 60
```

Nếu không có CLI `argocd`, hãy thay thế bằng `kubectl patch application ... --type merge -p '{"operation":{"sync":{}}}'` trong namespace `argocd`, hoặc dùng giao diện ArgoCD UI qua kênh private tương tự.

## 6. Phase D — Xác minh Karpenter hoạt động đúng (trước khi chạy load test)

```bash
# Node hiện tại + capacity-type + architecture
kubectl --context "$DV" get nodes -L karpenter.sh/capacity-type,kubernetes.io/arch,eks.amazonaws.com/capacityType

# Các NodeClaim do Karpenter quản lý — kỳ vọng thấy nodeclaim mới xuất hiện khi có pod pending
kubectl --context "$DV" get nodeclaims -o wide

# Xác minh Karpenter có thể đọc interruption queue mới tạo
kubectl --context "$DV" -n kube-system logs deploy/karpenter -c controller | grep -i interrupt

# Đối chiếu với EC2 instances thật — filter chính xác cho cluster develop
aws ec2 describe-instances \
  --filters "Name=tag:karpenter.sh/cluster,Values=ecommerce-develop-dev-eks" \
  --query 'Reservations[].Instances[].{Id:InstanceId,Life:InstanceLifecycle,Type:InstanceType,Arch:Architecture}' \
  --output table

# Kiểm tra các service nào hiện đang được bảo vệ bởi PDB trên luồng checkout
kubectl --context "$DV" -n "$NS" get pdb
```

Nếu `kubectl get nodes` không hiển thị label `karpenter.sh/capacity-type` sau vài phút dù có pod Pending — kiểm tra lại §5 (xem các Application đã Healthy chưa) trước khi nghi ngờ NodePool.

## 7. Phase E — Chạy đường cong tải (load curve thấp→cao→thấp)

```bash
kubectl --context "$DV" -n "$NS" apply -f docs/mandate-19/loadtest/locust-loadcurve-mandate13-job.yaml

# Theo dõi tiến trình
kubectl --context "$DV" -n "$NS" logs -f job/locust-loadcurve-mandate13
```

Trong khi job chạy (tổng thời gian hiện tại là 1800s ≈ 30 phút, xem phần `stages` trong file yaml job), **quay video live** panel Grafana "Node Count and Scaling" (`kubernetes-scaling.json`) và dashboard SLO (checkout success/p95) — đây là bằng chứng cho yêu cầu #2 và panel ③ của directive. Đối chiếu với §5 của EVIDENCE-INDEX.md để biết phải lưu file log/screenshot ở đâu.

Dọn dẹp sau khi chạy (Job có `ttlSecondsAfterFinished: 7200` nên tự động xóa sau 2h, xóa thủ công là tùy chọn):

```bash
kubectl --context "$DV" -n "$NS" delete job locust-loadcurve-mandate13 --ignore-not-found
```

## 8. Phase F — Live spot-kill test (Bằng chứng nặng đô nhất, yêu cầu #3)

**Chỉ thực thi bước này sau khi §6 đã xác nhận có đủ PDB trên luồng checkout** (`payment` đã có graceful-drain theo ADR Decision 5). Thực thi lệnh này vào giữa đường cong tải từ §7 khi nó đang ở pha tải cao/đỉnh (peak load):

```bash
# Tìm một spot instance đang chạy host các pod ứng dụng
aws ec2 describe-instances \
  --filters "Name=tag:karpenter.sh/cluster,Values=ecommerce-develop-dev-eks" \
            "Name=instance-lifecycle,Values=spot" \
  --query 'Reservations[].Instances[].InstanceId' --output text

# Theo dõi việc pod reschedule song song trong một terminal khác TRƯỚC KHI kill
kubectl --context "$DV" -n "$NS" get pods -w

# Giả lập thao tác thu hồi (revocation) — thay <spot-instance-id> bằng ID lấy ở trên
aws ec2 terminate-instances --instance-ids <spot-instance-id>
```

Kỳ vọng: Tỉ lệ checkout success trên Grafana vẫn giữ ≥99%, p95 <1s xuyên suốt; `kubectl get pods -w` hiển thị các pod cũ bị evict một cách nhẹ nhàng (gracefully, không có hàng loạt trạng thái `Error`/`OOMKilled`) và pod thay thế chuyển sang `Running` trên một node khác trong vòng vài phút. Lưu log terminal + ảnh chụp Grafana tại đúng thời điểm kill vào `logs/live-spot-kill.txt` theo `EVIDENCE-INDEX.md`.

## 9. Phase G — Cost Explorer (trend, không block việc quay video)

Cost Explorer bị delay khoảng ~24h — hãy chạy bước này sau, đừng đợi nó khi đang quay video (directive có ghi chú rõ điều này). Group by Purchase Option + Instance Type, Granularity Daily/Hourly, làm chính xác theo phần §"Cách đo & nộp" của `mandates/MANDATE-13-cost-efficiency-elastic.md`.

## 10. Rollback nhanh

| Mục đích Rollback | Lệnh |
|---|---|
| Tắt interruption queue + spot trên develop | Set `enable_karpenter_interruption_queue = false` trong `terraform/environments/develop/main.tf`, PR + apply lại qua §4 — rào `count` sẽ tự động hủy sạch mọi thứ gọn gàng, không cần `-target` |
| Dừng Karpenter không nhận thêm tải | `argocd app delete develop-karpenter-nodepool --cascade` hoặc sync lại NodePool cũ (`capacity-type: [on-demand]`, `consolidationPolicy: WhenEmpty`) |
| Đưa toàn bộ Karpenter về trạng thái ngủ (dormant) | Revert `platform/gitops/environments/develop/bootstrap/root-app.yaml` về phiên bản có `exclude: '{karpenter-crd.yaml,karpenter.yaml,karpenter-nodepool.yaml}'` |
| MNG `primary` cần scale thủ công khi có sự cố | `aws eks update-nodegroup-config --cluster-name ecommerce-develop-dev-eks --nodegroup-name primary --scaling-config minSize=2,maxSize=3,desiredSize=2` (khớp giá trị mặc định hiện tại trong `variables.tf` — `develop-capacity.tfvars` không còn đè giá trị này, xem §2.1; nhớ sync lại Terraform sau khi sự cố qua đi) |

## 11. Bảng lỗi thường gặp → đối chiếu environment-isolation guide

| Triệu chứng | Case Tương Ứng | Hành động cần làm |
|---|---|---|
| Comment PR Sandbox KHÔNG PHẢI LÀ "No changes" | Case T3 (Tính năng Develop bị leak sang shared module) | Kiểm tra xem mặc định của `enable_karpenter_interruption_queue` trong `variables.tf` có đúng là `false` chưa, hoặc có bị set nhầm thành `true` ở `sandbox/main.tf` không |
| Job `terraform-plan` của `infra-develop.yaml` không chạy dù đã dispatch | Điều kiện `github.ref == refs/heads/develop` không thỏa mãn | Xác minh PR đã được merge, và chạy lệnh dispatch chính xác với `--ref develop` |
| `aws sts get-caller-identity` trả về account khác `458580846647` giữa lúc apply | Case T6 | Dừng ngay lập tức, kiểm tra lại `TF_AWS_ROLE_ARN` trong GitHub Environment `develop` |
| MNG `primary` desired_size không khớp `variables.tf` sau khi apply | §2.1 pre-flight (override bằng var-file) | Đọc lại `develop-capacity.tfvars`, đây hầu như luôn là nguyên nhân |
| Node không được tạo dưới dạng spot dù NodePool đã cho phép | Giống Case G7 (tác động toàn cluster, cần thời gian) | Đợi 1-3 phút cho EC2 Fleet + kubelet bootstrap (Karpenter binpack → EC2 Fleet API → node Ready → pod được xếp lịch), kiểm tra `kubectl describe nodeclaim` |
| Checkout bị rớt request khi kill spot node | Thiếu PDB/graceful-drain | Dừng test, quay lại §6 để audit PDB/preStop trước khi thử lại |
| `kubectl get nodeclaims` không tạo node nào dù có pod Pending, log Karpenter báo reject liên quan `topology.kubernetes.io/zone` | `minValues` còn sót trên NodePool | Kiểm tra `platform/gitops/environments/develop/karpenter/nodepool-default.yaml` không còn dòng `minValues:` trên requirement `zone` (đã fix, xem §2 mục 2) |
| Grafana "Node Count and Scaling" không cho thấy scale-down rõ ràng ở pha "low" cuối của §7, hoặc mCPU/rps baseline không về gần 0 | Continuous load-generator (PR #382) vẫn `enabled: true` | Tắt tạm background traffic trước khi chạy §7/§8, xem §2 mục 3 |
