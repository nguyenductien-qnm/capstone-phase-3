# Karpenter deep-dive — cấu hình thực tế, consolidation, disruption & kế hoạch migrate (study)

> Tiếp nối `karpenter-analysis.md`. Tài liệu này đi sâu vào shape cấu hình thật, cơ chế consolidation/disruption, các gotcha thực tế và lộ trình migrate từ MNG+CA (ADR-REL-003) sang Karpenter trên cluster `ecommerce-dev-eks` (EKS 1.36).
> Nguồn: Karpenter official docs + EKS docs + bài thực chiến 2026. Versions quan sát: Karpenter v1.3.x–v1.14.x (v1 API ổn định).

---

## 1. Trạng thái hiện tại của Karpenter (đến 2026)

- **v1 API ổn định**: `NodePool` (`karpenter.sh/v1`) + `EC2NodeClass` (`karpenter.k8s.aws/v1`). `Provisioner` (v0.x) và `AWSNodeTemplate` **bị xoá ở v1.0** → không dùng YAML v0.x với install v1.x.
- **KHÔNG bị khoá vào 1 version k8s** như CA. CA phải match k8s minor (cluster ta 1.36 → CA 1.35/1.36); Karpenter chạy trên dải version rộng hơn, upgrade độc lập với k8s. Vẫn phải dùng version tương thích với EKS 1.36 (Karpenter mới nhất hỗ trợ).
- Sự khác biệt cốt lõi vs CA:
  - CA poll mỗi ~10s, chọn từ ASG/launch-template có sẵn. Karpenter watch pod event real-time, gọi **EC2 Fleet API trực tiếp** (không qua ASG) → scale-up ~30s.
  - CA co xuống sau idle timeout. Karpenter **chủ động bin-pack**: gom pod, thay node rẻ hơn, terminate node dư (có respect PDB + budget).
  - Karpenter **drift detection**: khi AMI/instance-type config thay đổi, tự thay node (thay vì phải sửa launch template thủ công như CA/MNG).

---

## 2. Shape cấu hình thực tế (manifest mẫu)

### 2.1 EC2NodeClass — "node đến từ đâu"
```yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  role: "KarpenterNodeRole-ecommerce-dev-eks"   # instance profile / node IAM role
  amiSelectorTerms:
    - alias: "al2023@v2026xxxx"                 # AL2023 EKS-optimized; k8s 1.33+ bỏ AL2
  subnetSelectorTerms:
    - tags: { karpenter.sh/discovery: "ecommerce-dev-eks" }
  securityGroupSelectorTerms:
    - tags: { karpenter.sh/discovery: "ecommerce-dev-eks" }
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs: { volumeSize: 20Gi, volumeType: gp3, encrypted: true }
  tags:
    karpenter.sh/cluster: "ecommerce-dev-eks"    # cho cost allocation
    team: reliability
```
> Lưu ý: `kubelet` config (max-pods, labels...) đã chuyển từ NodePool sang **EC2NodeClass** ở v1. Repo ta đang tag MNG bằng `k8s.io/cluster-autoscaler/enabled` + `.../ecommerce-dev-eks`; Karpenter dùng tag `karpenter.sh/discovery` riêng → **không đụng ASG của CA**.

### 2.2 NodePool — "ai được dùng node nào"
```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
        - key: kubernetes.io/os
          operator: In
          values: ["linux"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m", "t"]
        - key: karpenter.k8s.aws/instance-generation
          operator: Gt
          values: ["2"]
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      terminationGracePeriod: 24h        # đủ drain trước khi force delete
  limits:
    cpu: "40"                            # trần cost (bảo vệ budget $300/tuần)
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
    budgets:
      - nodes: "10%"
      - nodes: "0"
        schedule: "0 9 * * mon-fri"      # giờ hành chính: không disrupt
        duration: 8h
  weight: 10
```
- **Nguyên tắc**: các NodePool nên **mutually exclusive** (1 pod khớp tối đa 1 pool). Nếu khớp nhiều, Karpenter chọn pool có `weight` cao nhất.
- `consolidationPolicy: WhenEmpty` = chỉ xoá node rỗng. `WhenEmptyOrUnderutilized` = còn thay node "xấu pack" bằng node rẻ hơn → **tiết kiệm thật nhưng gây churn** →因此有 `budgets`.

### 2.3 Tách critical path vs spot (2 NodePool)
```yaml
# on-demand: checkout/cart/frontend-proxy (critical path)
requirements:
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["on-demand"]
---
# spot: load-generator, batch, non-critical
requirements:
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot"]
```
Workload định tuyến qua `nodeAffinity`/`tolerations` (VD `karpenter.sh/capacity-type: spot`).

---

## 3. Consolidation — chỗ Karpenter thắng CA (và chỗ dễ đau)

3 loại consolidation Karpenter làm:
- **Empty-node**: gom pod khỏi node rỗng rồi terminate.
- **Multi-node**: gom nhiều node underutilized thành ít node hơn.
- **Single-node**: thay 1 node bằng instance type rẻ/pack tốt hơn (kể cả Spot→Spot).

=> Tiết kiệm đến từ đây, KHÔNG tự xảy ra. Cần:
- requests chuẩn (§ gotcha).
- `consolidateAfter` đủ (VD 1m) để không churn lúc rolling update.
- `budgets` để giờ cao điểm không bị disrupt.

**Spot-to-Spot consolidation yêu cầu ≥15 instance type rẻ hơn trong pool** — nếu NodePool giới hạn vài family, nó **im lặng không làm gì** (xem event `Unconsolidatable`). Fix: mở rộng instance flexibility.

---

## 4. Disruption & Spot interruption

- **Spot interruption**: Karpenter nhận cảnh báo 2 phút qua **SQS interruption queue** (EventBridge subscribe `EC2 Spot Instance Interruption Warning`, `Instance Rebalance Recommendation`, `Instance State-change`). Khi có, nó **cordón + drain node (respect PDB) và provision node thay SONG SONG** → không downtime nếu PDB `minAvailable ≥ 2`.
  - Cần tạo SQS queue + EventBridge rule + IAM quyền cho controller (thêm vào policy IRSA).
- **NodeRepair** (opt-in, feature gate `NodeRepair=true`): node `Ready=False/Unknown` 30p → Karpenter force terminate + thay. Safety: **không repair nếu >20% node trong pool unhealthy** (tránh cascade). Cần node monitoring agent (Node Problem Detector) để có status conditions.

---

## 5. Gotcha thực tế (đúc kết từ thực chiến)

1. **1 PDB `maxUnavailable: 0` chặn CẢ node.** Nếu pod A có PDB khắt khe, mọi pod khác trên node đó không thể evict → consolidation đứng im. Audit PDB trước khi thắc mắc tại sao không consolidate. (Đã có CDO-34.)
2. **`do-not-disrupt` annotation** (trên pod/node) làm node kẹt ở draining cho tới khi pod xong hoặc `terminationGracePeriod` ép xoá. Dùng cẩn thận.
3. **Đổi `expireAfter` gây DRIFT, không update trực tiếp.** NodeClaim cũ giữ giá trị cũ; Karpenter thay node qua drift path (có rate-limit bởi budget) → rollout có thể mất hàng giờ nếu budget chặt.
4. **`WhenEmptyOrUnderutilized` thiếu `consolidateAfter`/`budgets` = churn.** Rolling update kích hoạt thay node liên tục. Luôn set `consolidateAfter: 1m` + budgets.
5. **Behavioral fields (`consolidationPolicy`, `limits`, `weight`) apply ngay, không cycle node.** Không dùng drift để rollout từ từ strategy mới.
6. **Karpenter KHÔNG quản MNG hiện có.** Nó provision EC2 ngoài ASG. MNG cũ vẫn do CA/manual quản lý trừ khi đưa workload sang Karpenter rồi scale MNG về 0.
7. **Spot-to-Spot cần ≥15 instance type** (mục 3).
8. **Ubuntu AMI bị drop ở v1.0**; AL2 bỏ ở k8s 1.33. Dùng AL2023.

---

## 6. Kế hoạch migrate CA → Karpenter (repo ta)

> Nguyên tắc ADR-REL-003: **coexist-first**, đo chênh lệch rồi mới replace.

### Bước 0 — chuẩn bị (prereqs)
- OIDC provider đã có (repo dùng IRSA) ✅.
- Tag subnet/SG bằng `karpenter.sh/discovery: ecommerce-dev-eks`.
- Tạo SQS interruption queue + EventBridge rule (cho Spot).
- Tất cả workload critical có PDB đúng + requests chuẩn (CDO-34, ADR-REL-001/002).

### Bước 1 — IAM (tái dùng pattern `terraform/modules/eks/cluster-autoscaler.tf`)
- Tạo `KarpenterControllerRole-ecommerce-dev-eks` (IRSA, trust OIDC) với quyền EC2: `CreateFleet`, `TerminateInstances`, `DescribeSubnets/SecurityGroups/InstanceTypes`, `DeleteLaunchTemplate`, SQS receive/delete, EventBridge.
- Tạo `KarpenterNodeRole-ecommerce-dev-eks` (instance profile) + attach `AmazonEKSWorkerNodePolicy`, `AmazonEC2ContainerRegistryReadOnly`, `AmazonSSMManagedInstanceCore`.

### Bước 2 — deploy Karpenter (ArgoCD, giống pattern CA)
- Helm `oci://public.ecr.aws/karpenter/karpenter`, `--set settings.clusterName`, `settings.interruptionQueue`, `serviceAccount.annotation = controller role ARN`, `replicas: 2` (HA).
- App manifest trong `platform/gitops/applications/karpenter.yaml` (theo chuẩn `cluster-autoscaler.yaml`).

### Bước 3 — NodePool + EC2NodeClass (mục 2)
- `default` (on-demand) cho critical path; `spot` pool cho load-generator/non-critical.

### Bước 4 — coexist & chuyển dần workload
- Giữ MNG+CA chạy (system pool: observability, `frontend-proxy` ≥2 replica).
- Dùng `nodeAffinity`/`tolerations` đẩy app pods (checkout/cart/product-catalog) sang Karpenter pool.
- Quan sát: pod pending time, node provisioning latency, consolidation events, Cost Explorer.

### Bước 5 — quyết định replace (nếu đo được lợi)
- Khi tin tưởng: scale MNG `desired/min` về 0 (hoặc tắt CA `enable_cluster_autoscaler=false`), để Karpenter fully quản worker node.
- Rollback: bật lại CA + MNG desired>0; xoá Karpenter app.

### Validation (bắt buộc)
- Load test 200 user → đo pod pending time (Karpenter vs CA).
- Sau load → xác nhận node dư consolidate/terminate (cost xuống).
- Rolling update app lúc consolidate → không breach SLO.
- Simulate Spot interruption → checkout ≥99%.
- Cost Explorer: MNG+CA vs MNG+CA+Karpenter.

---

## 7. So sánh nhanh (thực tế)

| Khía cạnh | CA (đang có) | Karpenter |
|---|---|---|
| Trigger | poll 10s | real-time pod watch |
| Node selection | ASG/launch-template có sẵn | 60+ instance type, bin-pack tối ưu |
| Scale-up | 30–60s | ~30s (EC2 Fleet trực tiếp) |
| Scale-down | idle timeout | chủ động consolidate + thay node rẻ hơn |
| Spot | cần ASG riêng/tay | native price-capacity-optimized |
| Drift/AMI | sửa launch template thủ công | auto thay node khi config đổi |
| CRD | không | NodePool, EC2NodeClass |
| Rủi ro chính | idle node dư, chậm | churn, PDB block, metrics gap |

## 8. Kết luận cho repo
Karpenter hợp lý NẾU ta sẵn sàng vận hành: PDB chuẩn, requests chuẩn, SQS interruption, metrics Karpenter + cost allocation (hiện đang thiếu — CDO-159). Với 3 tuần còn lại, **giữ MNG+CA (ADR-REL-003)** là an toàn; Karpenter là follow-up "coexist-first" theo Bước 0–5, đo chênh lệch rồi quyết replace.
