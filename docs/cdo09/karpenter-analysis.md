# Phân tích Karpenter — cách dùng & các vấn đề phải handle

> Mục đích: phân tích cách vận hành Karpenter trên EKS và liệt kê các vấn đề/threat phải xử lý trước khi adopt (cho quyết định follow-up của ADR-REL-003).
> Ngữ cảnh repo: Standard EKS + MNG tĩnh; ADR-REL-003 đã cài Cluster Autoscaler (MNG+ASG). Karpenter được đánh giá để "coexist-first", sau đó mới cân nhắc thay thế CA.

---

## 1. Karpenter là gì (khác CA thế nào)

- **Cluster Autoscaler (CA):** scale theo **Node Group / ASG**. Mỗi ASG = 1 cấu hình fixed (instance type, zone). Muốn đa dạng capacity phải tạo nhiều node group thủ công. Scale-up chậm (theo bước ASG), hay dư idle node.
- **Karpenter:** controller đọc trực tiếp **pod unschedulable**, rồi **provision node sát pod demand** — không cần định nghĩa trước node group. Dùng `NodePool` + `EC2NodeClass` để khai báo capacity policy (instance family, zone, Spot/On-Demand, tag, IAM, AMI). Có **consolidation** tự gom/thay node dư để tối ưu cost.

=> Karpenter provision nhanh hơn, packing tốt hơn, ít idle node hơn CA — nhưng bề mặt vận hành và số thứ phải cấu hình đúng cũng lớn hơn.

---

## 2. Cách dùng (shape của cấu hình)

### 2.1 EC2NodeClass (capacity source)
Khai báo "node đến từ đâu":
- `subnetSelector` / `securityGroupSelector` (tag-based).
- `amiFamily` (Bottlerocket / AL2023 / Ubuntu...).
- `instanceProfile` hoặc IAM thông qua IRSA (Karpenter dùng pod identity/IRSA để gọi EC2).
- `instanceStorePolicy`, `blockDeviceMappings`, `tags` (quan trọng: tag gán cho cost allocation / consolidate).
- `userData` nếu cần bootstrap custom.

### 2.2 NodePool (capacity policy)
Khai báo "ai được dùng node nào":
- `template.spec.requirements` — chọn `kubernetes.io/instance-type` (vd `[m5.large, m6i.large, c6i.large]` hoặc `family`), `topology.kubernetes.io/zone`, `karpenter.sh/capacity-type` (`spot` / `on-demand`), `karpenter.k8s.aws/instance-category`, `arch`.
- `limits` — giới hạn tổng CPU/mem của pool (bảo vệ cost ceiling).
- `weight` — ưu tiên giữa nhiều NodePool (vd NodePool On-Demand weight thấp, Spot weight cao).
- `disruption` — policy cho consolidation & eviction (xem §3.3).
- `taints` / `startupTaints` + `nodeClass` reference.

### 2.3 Cách Karpenter quyết định
1. Pod Pending (không đủ resource / topology / taint).
2. Karpenter tìm NodePool match → chọn instance type pack vừa nhất (bin-packing) → launch 1 node EC2.
3. Sau load spike, **consolidation** đánh giá: gom pods sang ít node hơn, hoặc đổi sang node rẻ hơn (Spot), rồi **terminate node dư** (có respect PDB & disruption budget).

### 2.4 So với CA trong repo hiện tại
- CA hiện dùng auto-discovery ASG của MNG (`k8s.io/cluster-autoscaler/enabled` + `.../ecommerce-dev-eks`), IRSA (`terraform/modules/eks/cluster-autoscaler.tf`).
- Nếu adopt Karpenter: MNG có thể giữ làm "static fallback / system pool" (chạy control-plane-adjacent, observability, `frontend-proxy` ít nhất 2 replica), Karpenter lo application pods (checkout/cart/product-catalog) để lấy packing + consolidation tốt hơn.

---

## 3. Các vấn đề PHẢI handle khi dùng Karpenter

### 3.1 Pod Disruption Budget (PDB) — bắt buộc
- Karpenter terminate node dư trong consolidation/scale-down. Nếu **không có PDB**, nó có thể evict cùng lúc nhiều replica → breach SLO (`checkout ≥99%`, `cart ≥99.5%`).
- Cần PDB cho mọi service nhiều replica (đã có CDO-34 cho Karpenter). Quy tắc: `maxUnavailable: 1` + `topologySpreadConstraints` để replica dàn trên nhiều node/zone.
- ⚠️ **PDB quá khắt khe sẽ block consolidation** → node không bao giờ terminate → mất lợi ích cost. Phải tune `maxUnavailable`/`minAvailable` vừa đủ.

### 3.2 Resource requests phải ĐÚNG
- Karpenter pack node theo `resources.requests`. Requests sai (quá thấp) → node quá tải; quá cao → node rỗng, lãng phí, cost tăng.
- Phải set `resources.requests`/`limits` chuẩn cho tất cả workload (kể cả daemonset: see §3.4). Đây là tiền đề chung của cả HPA/CA/Karpenter.

### 3.3 Disruption budget & consolidation policy
- `NodePool.spec.disruption` có `consolidationPolicy: WhenEmpty` (mặc định, an toàn) vs `WhenEmptyOrUnderutilized` (chủ động gom, tiết kiệm hơn nhưng gây node churn).
- `budgets` giới hạn số node bị disrupt mỗi khoảng thời gian (vd không terminate quá X node/giờ) — bảo vệ SLO trong giờ cao điểm.
- ⚠️ `WhenEmptyOrUnderutilized` + consolidation liên tục có thể gây **node churn** (node bị tạo/xoá liên tục) làm latency spike. Cần cân bằng giữa tiết kiệm và ổn định.

### 3.4 DaemonSet overhead
- DaemonSet (observability agent, CNI, log shipper) trừ resource trên mọi node → ảnh hưởng trực tiếp packing & cost.
- Phải đo overhead DaemonSet và cộng vào tính toán capacity; nếu DaemonSet nặng, node nhỏ sẽ pack được ít pod → Karpenter chọn node to hơn (đắt hơn).

### 3.5 Spot interruption (nếu dùng Spot)
- Spot có thể bị AWS thu hồi bất kỳ lúc nào (2 phút warning). Karpenter xử lý qua `karpenter.sh/capacity-type: spot` + `disruption` nhưng:
  - Critical path (checkout/cart) nên **On-Demand** hoặc NodePool riêng có `capacity-type: on-demand`.
  - Workload chịu interruption (load-generator, batch, non-critical) mới cho Spot.
  - App phải graceful shutdown (handle SIGTERM, drain connection) để không breach SLO khi node bị reclaim.

### 3.6 Interference với Cluster Autoscaler (khi coexist)
- **CA và Karpenter KHÔNG được quản cùng 1 ASG / node group.** Nếu MNG vẫn do CA quản, Karpenter phải chỉ provision node NGOÀI ASG đó (NodePool riêng, tag khác).
- Nếu không phân ranh rõ, CA và Karpenter tranh chấp scale → flapping. Quy tắc repo: MNG+CA = system/static pool; Karpenter = app pool, tag `karpenter.sh/managed=true`.

### 3.7 Node termination / drain timing
- Karpenter thay node nhanh hơn CA → thời gian drain ngắn hơn. Phải đảm bảo `terminationGracePeriodSeconds` đủ để pod drain, và `preStop` hook / readiness gate đúng.
- Load balancer (NLB → `frontend-proxy`) phải deregister pod trước khi node mất (target draining).

### 3.8 Metrics & cost observability (blind spot hiện tại)
- Prometheus repo **chỉ có K8s-infra metrics, không có app HTTP metrics** (phát hiện từ CDO-159). Karpenter sinh ra metrics riêng (`karpenter_node_age`, `karpenter_pods_state`, disruption events, provisioning latency).
- Phải thêm: Karpenter metrics + node cost allocation (theo tag) + pod-request accuracy dashboard. Thiếu cái này sẽ không chứng minh được Karpenter "rẻ hơn" (xem §4).

### 3.9 Version / upgrade lifecycle
- Karpenter version phải tương thích với EKS k8s version (như CA: appVersion gần cluster). Upgrade Karpenter = vận hành thêm (controller deploy, CRD `NodePool`/`EC2NodeClass` thay đổi giữa minor).
- Phải có runbook upgrade và test trên dev trước.

### 3.10 Stateful workload trên worker node
- Karpenter thay node tự động → **không chạy database/stateful có volume attach trên pool Karpenter** (PostgreSQL đã sang RDS, Valkey sang ElastiCache — boundary này đã đúng, theo `eks-karpenter-vs-auto-mode.md`). Stateful còn lại phải có operator/HA/backup hoặc nằm ngoài Karpenter pool.

### 3.11 IAM / auth
- Karpenter controller cần quyền EC2 (Create/Delete/Describe instances, subnets, SG, tags...). Repo đã chuẩn hoá **IRSA** + OIDC provider sẵn có → tái dùng pattern `terraform/modules/eks/cluster-autoscaler.tf` nhưng viết policy riêng cho Karpenter (ít nhất-priv, scoping theo tag).

---

## 4. Rủi ro chính (tóm tắt)

| Vấn đề | Hậu quả nếu không handle | Cách đối phó |
|---|---|---|
| Thiếu PDB / PDB quá khắt | Breach SLO hoặc block consolidation (lãng phí) | PDB đúng + topologySpread, tune maxUnavailable |
| Resource requests sai | Node quá tải / rỗng, cost tăng | Set requests chuẩn, đo thực tế |
| Consolidation churn | Latency spike do node tạo/xoá liên tục | `consolidationPolicy` + `budgets` giới hạn |
| Spot interruption | Pod chết giữa chừng, checkout fail | Critical path On-Demand, graceful shutdown |
| CA + Karpenter tranh ASG | Flapping scale | Tách pool, tag riêng |
| Thiếu metrics cost | Không chứng minh được tiết kiệm | Thêm Karpenter metrics + cost allocation |
| Stateful trên Karpenter | Volume detach rủi ro | Chỉ stateless trên Karpenter pool |

---

## 5. Điều kiện để adopt (go/no-go)

Nên adopt Karpenter khi:
- Đã có PDB + resource requests đúng cho toàn bộ workload critical (CDO-34 done mindset).
- Đã tách stateful ra khỏi worker node (RDS/ElastiCache ✅).
- Có metrics Karpenter + cost allocation để đo.
- Có người vận hành controller/upgrade (hoặc chấp nhận cost vận hành).

Giữ MNG+CA (ADR-REL-003) nếu 3 tuần còn lại ưu tiên ít moving parts; Karpenter là follow-up "coexist-first", đo chênh lệch cost/SLO rồi mới quyết định replace.

## 6. Verification (khi adopt)
- Load test 200 user → đo pod pending time và node provisioning latency (Karpenter vs CA).
- Sau load → xác nhận node dư được consolidate/terminate (cost xuống).
- Rolling update app lúc đang consolidate → không breach SLO.
- Simulate Spot interruption → checkout vẫn ≥99%.
- Đo Cost Explorer chênh lệch MNG+CA vs MNG+CA+Karpenter.
