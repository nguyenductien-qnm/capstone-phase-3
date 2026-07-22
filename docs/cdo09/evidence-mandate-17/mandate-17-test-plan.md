# Mandate 17 — Test Plan (Develop Cluster)

> Nhánh: `feat/mandate-17-resilience-containment`  
> Cluster: `ecommerce-develop-dev-eks` (account 458)  
> Ngày: 2026-07-21

---

## Biến môi trường

```bash
DV=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
NS=techx-develop
BRANCH=feat/mandate-17-resilience-containment
```

---

## Gap Analysis — Plan cũ vs Mandate thật

> Plan cũ **chưa đủ** để nộp mentor. 3 lỗ hổng lớn:

| # | Mandate yêu cầu | Plan cũ có không | Thiếu gì |
|---|---|---|---|
| 1 | **R1:** Giết 1 downstream service → checkout SLO vẫn giữ | ❌ Chỉ test pod Running | Test thật: kill `ad`/`recommendation` → verify checkout vẫn qua |
| 2 | **R3:** Deploy "attacker pod" → không scan/kết nối được sang service khác, không gọi ra ngoài | ❌ Chỉ render chart + bật CNI | Test thật: pod tấn công thử `curl`, `nc`, kết nối → bị block |
| 3 | **R4:** Mỗi service có ServiceAccount riêng, RBAC tối thiểu, pod chiếm không gọi được K8s API | ❌ Chỉ check `automountServiceAccountToken=false` | Verify ServiceAccount per-service + RBAC ClusterRole chỉ read pods |

---

## Trạng thái Implementation — Code đã handle đến đâu

> Kiểm tra thực tế từ code trong nhánh `feat/mandate-17-resilience-containment`.

### R1 — Frontend Resilience (Dockerfile + Timeout/Fallback)

| Sub-item | Trạng thái | File | Dòng / Chi tiết |
|---|---|---|---|
| **Circuit breaker** (closed/open/half-open) | ✅ **Đã có** | `techx-corp-platform/src/frontend/utils/resilience/CircuitBreaker.ts` | Dòng 5, 21 — state machine; dòng 23–25, 37 — `failureThreshold/openMs/timeoutMs` |
| **Single-flight** half-open (chống dội burst) | ✅ **Đã có** | `CircuitBreaker.ts` | Dòng 30–33 — `probeInProgress` |
| Log khi mạch đổi trạng thái | ✅ **Đã có** | `CircuitBreaker.ts` | `transitionTo()` — chỉ log khi transition (không spam) |
| `ad`: breaker + gRPC deadline + **fallback `{ads:[]}`** | ✅ **Đã có** | `techx-corp-platform/src/frontend/gateways/rpc/Ad.gateway.ts` | Dòng 15, 19, 26–27 (`Metadata`+`deadline` đúng vị trí CallOption), 32 (fallback) |
| `recommendation`: breaker + deadline + **fallback `{productIds:[]}`** | ✅ **Đã có** | `.../rpc/Recommendations.gateway.ts` | Dòng 15, 19, 27, 32 |
| **Dockerfile COPY utils/resilience** | ✅ **Đã có** | `techx-corp-platform/src/frontend/Dockerfile` | **Dòng 27** — `COPY ./src/frontend/utils/resilience/ utils/resilience/` (commit `4b05b93`) |
| Envoy timeout per-route (bổ trợ) | ✅ **Đã có** | `techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml` | Dòng 56/62/71: timeout 30s cho copilot/ask-ai |
| Timeout LLM reviews / copilot (code team AI, không đụng) | ✅ **Đã có** | `platform/charts/application/values.yaml` | `LLM_REVIEWS_TIMEOUT`, `LLM_COPILOT_TIMEOUT`… |

> **Kết luận R1:** ✅ **Đã đủ timeout + fallback + degrade graceful** cho 2 dependency không-thiết-yếu (`ad`, `recommendation`) — không còn phụ thuộc "try/catch chưa rõ". Phase 1b chỉ để **chứng minh runtime**, không phải để phát hiện gap.

---

### R2 — HA Multi-AZ (PDB + replicas + topologySpread + Karpenter)

| Sub-item | Trạng thái | File | Dòng / Chi tiết |
|---|---|---|---|
| `payment` replicas=2 + PDB + topologySpread | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 1086–1089: `replicas:2, topologySpread:true, podDisruptionBudget.maxUnavailable:1` |
| `shipping` replicas=2 + PDB + topologySpread | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 1446–1449: `replicas:2, topologySpread:true, podDisruptionBudget.maxUnavailable:1` |
| `currency` HPA minReplicas=2 + PDB + topologySpread | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 616–622: `hpa.minReplicas:2, podDisruptionBudget, topologySpread:true` |
| `checkout` PDB | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 748–751: `podDisruptionBudget.maxUnavailable:1, topologySpread:true` |
| `cart` PDB | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 381–383: `podDisruptionBudget.maxUnavailable:1, topologySpread:true` |
| `recommendation` PDB + spread + HPA min=2 | ✅ **Đã vá** | `platform/charts/application/values.yaml` | Dòng ~1319 — commit `d3c47ad` (có CPU request 100m nên HPA CPU chạy được) |
| `ad` PDB + spread + HPA min=2 | ✅ **Đã vá** | `platform/charts/application/values.yaml` | Dòng ~327 — commit `d3c47ad` (có CPU request 50m) |
| `frontend`, `frontend-proxy`, `product-catalog`, `ml-guard` | ✅ **Đã có** | `values.yaml` | Dòng 746, 843, 1136, 1043 — spread + PDB + hpaMin=2 |
| Service **chưa** HA (chấp nhận) | ⚠️ **1 replica** | `values.yaml` | email(631), quote(1284), product-reviews(1208), shopping-copilot(1357), llm(1627), accounting(253), fraud-detection(669) — async/không-thiết-yếu |
| Sandbox Karpenter NodePool `zone minValues:2` | ✅ **Đã có** | `platform/karpenter/nodepool-default.yaml` | Dòng 27–30: `topology.kubernetes.io/zone, operator:Exists, minValues:2` |
| Develop Karpenter NodePool `zone minValues:2` | ✅ **Đã vá** | `platform/gitops/environments/develop/karpenter/nodepool-default.yaml` | Dòng 28–31: commit `d4cf460` — thêm `minValues:2` |

> **Kết luận R2:** ✅ **11/18 service** có spread+PDB+≥2 replica — phủ trọn money-path (frontend, frontend-proxy, cart, checkout, product-catalog, currency, payment, shipping) + browse-path (ad, recommendation) + ml-guard. 7 service còn lại là async/không-thiết-yếu, mất AZ chỉ gián đoạn ngắn tới khi reschedule (chấp nhận, nêu rõ khi nộp).

---

### R3 — NetworkPolicy Containment

| Sub-item | Trạng thái | File | Dòng / Chi tiết |
|---|---|---|---|
| Default-deny ingress + egress | ✅ **Đã có** | `platform/charts/application/templates/networkpolicy.yaml` | Dòng 16–24: `default-deny-all` policy |
| DNS egress allow | ✅ **Đã có** | `networkpolicy.yaml` | Dòng 26–43: `allow-dns-egress` |
| Per-service ingress đồ thị | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 100–117: `networkPolicy.serviceIngress` — đầy đủ 18 service |
| Egress internet chỉ pod có label | ✅ **Đã có** | `networkpolicy.yaml` | Dòng 208–226: `allow-internet-egress-selected` (label `egress-internet:true`) |
| Egress datastore (ElastiCache/MSK/RDS) | ✅ **Đã có** | `values.yaml` | Dòng 84–97: `datastoreEgress` — elasticache:6379, msk:9092/9094/9096, rds:5432 |
| Observability scrape/sink | ✅ **Đã có** | `values.yaml` | Dòng 66–81: prometheus, otel-collector, jaeger |
| CIDR sandbox (10.0.0.0/16) | ✅ **Đã có** | `values.yaml` (chart default) | Dòng 83, 87: `apiServerCIDR: 10.0.0.0/16` |
| CIDR develop (10.60.0.0/16) | ✅ **Đã có** | `platform/gitops/environments/develop/values/values-application.yaml` | Override CIDR develop — cần confirm dòng cụ thể |
| `networkPolicy.enabled` mặc định | ⚠️ **TẮT** | `values.yaml` | Dòng 56: `enabled: false` — phải flip=true sau TF apply |
| VPC CNI enforce (Terraform) | ✅ **Đã có** | `terraform/modules/eks/main.tf` + `terraform/modules/eks/variables.tf` | `enable_network_policy` variable + `configuration_values` cho vpc-cni addon |
| Sandbox TF bật CNI | ✅ **Đã có** | `terraform/environments/sandbox/main.tf` | `enable_network_policy = true` |
| Develop TF bật CNI | ✅ **Đã có** | `terraform/environments/develop/main.tf` | `enable_network_policy = true` |

> **Kết luận R3:** Code đầy đủ. **Việc còn lại là runtime:** flip `networkPolicy.enabled=true` sau TF apply → ArgoCD sync → NP áp lên cluster. Phase 3d (attacker pod) sẽ prove containment thật.

---

### R4 — Least-privilege (automount + ServiceAccount + RBAC)

| Sub-item | Trạng thái | File | Dòng / Chi tiết |
|---|---|---|---|
| `automountServiceAccountToken: false` default | ✅ **Đã có** | `platform/charts/application/values.yaml` | Dòng 49–51: comment CDO-220 + `automountServiceAccountToken: false` ở `defaultValues` |
| SA per-component template | ✅ **Đã có** | `platform/charts/application/templates/component-serviceaccount.yaml` | Dòng 1–19: render SA riêng per-component khi `serviceAccount.create: true` |
| SA `shopping-copilot` (IRSA cần token) | ✅ **Đã có** | `values.yaml` | Dòng 1365–1368: `serviceAccount.create:true, annotations:{}` — explicit opt-in |
| SA `image-provider` | ✅ **Đã có** | `values.yaml` | Dòng 1205–1208: `serviceAccount.create:true` |
| RBAC ClusterRole/RoleBinding per-service | ❌ **THIẾU** | Không tìm thấy trong templates | Không có `role.yaml` hay `rolebinding.yaml` trong chart templates — pod bị chiếm dùng SA nhưng SA không bị giới hạn verb/resource qua RBAC |
| Pod không có token file (verify runtime) | ⚠️ **Chưa verify** | — | Cần exec vào pod thật → Phase 4a |

> **Kết luận R4:** `automountServiceAccountToken: false` đã chuẩn. **Gap lớn:** Không có RBAC Role/RoleBinding per-SA — nếu mentor test pod gọi K8s API, SA không có token (automount=false) nên thực tế không gọi được. Nhưng nếu mentor yêu cầu chứng minh RBAC policy, cần thêm Role/RoleBinding vào chart.

---

### Tổng kết Implementation Status

| Requirement | Code sẵn sàng? | Còn thiếu |
|---|---|---|
| **R1 Dockerfile/timeout** | ✅ 90% done | Verify runtime fallback graceful (Phase 1b) |
| **R2 PDB money-path** | ✅ 85% done | `recommendation` và `ad` chưa có PDB |
| **R2 Karpenter zone** | ✅ Done | — |
| **R3 NetworkPolicy template** | ✅ Done | Chưa flip `enabled=true`, chưa TF apply |
| **R3 VPC CNI TF** | ✅ Done | Chưa apply (plan OK, apply chờ approve) |
| **R4 automount=false** | ✅ Done | — |
| **R4 SA per-service** | ✅ Done (template có) | Chỉ 2/24 service khai `serviceAccount.create:true` explicit |
| **R4 RBAC Role/RoleBinding** | ❌ Thiếu hoàn toàn | Không có trong chart templates — low risk vì automount=false |

---

## Mapping Requirement → Phase (cập nhật)

| Requirement | Mandate nói gì | Phase test |
|---|---|---|
| **R1a** | Dockerfile fix — image chứa resilience handler | Phase 1a |
| **R1b** | Kill downstream → browse→checkout SLO vẫn giữ (fallback/timeout) | Phase 1b ⭐ mới |
| **R2** | HA multi-AZ: PDB + replicas ≥2 + topologySpread + Karpenter zone minValues:2 | Phase 2 |
| **R3a** | NetworkPolicy chart render + VPC CNI enforce | Phase 3a/3b/3c |
| **R3b** | Attacker pod: không lateral movement, không egress tự do | Phase 3d ⭐ mới |
| **R4a** | `automountServiceAccountToken: false` toàn namespace | Phase 4a |
| **R4b** | ServiceAccount per-service + RBAC tối thiểu | Phase 4b ⭐ mới |

---

## Ảnh hưởng đến team / hệ thống

| Phase | Đụng cluster nào | Ảnh hưởng đồng đội | Thời gian ước tính | Đảo ngược được? |
|---|---|---|---|---|
| Phase 0 (chuẩn bị) | Develop (458) | develop-root không tự heal trong lúc test | ~2 phút | ✅ 1 lệnh |
| Phase 1a (sync chart) | Develop (458) | Pod techx-develop rolling restart | ~3–5 phút | ✅ Revert targetRevision |
| Phase 1b (kill ad/rec) | Develop (458) | `ad` hoặc `recommendation` pod down ~5 phút | ~5 phút | ✅ Xóa NetworkPolicy block hoặc scale lại |
| Phase 2d (drain node) | Develop (458) | Node bị drain, pod evict → Karpenter provision node mới | ~5–10 phút | ✅ uncordon node |
| Phase 3c (TF apply VPC CNI) | Develop (458) | `aws-node` DaemonSet rolling restart → ~5s mất network/node | ~5–8 phút | ⚠️ Khó revert nhanh (addon update) |
| Phase 3d (attacker pod) | Develop (458) | 1 pod test chạy rồi xóa | ~2 phút | ✅ `kubectl delete pod` |
| Phase 5 (dọn dẹp) | Develop (458) | Bật lại auto-sync | ~1 phút | ✅ |
| **Sandbox** | **Không đụng** | **Không ảnh hưởng đồng đội** | — | — |

> **Tổng thời gian ước tính:** ~30–45 phút (nếu không có blocker).  
> **Thời điểm nên chạy:** Báo team trước, tránh giờ cao điểm demo/deploy của team.

---

## PHASE 0 — Chuẩn bị

**Ảnh hưởng:** develop-root không selfHeal trong thời gian test. Develop-techx-corp trỏ feature branch.  
**Thời gian:** ~2 phút.

```bash
# Verify context đúng trước khi làm bất cứ thứ gì
kubectl config current-context

# Pause develop-root (ngăn selfHeal revert patch)
kubectl --context "$DV" -n argocd patch application develop-root \
  --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'

# Trỏ develop-techx-corp sang feature branch
kubectl --context "$DV" -n argocd patch application develop-techx-corp \
  --type=merge -p '{"spec":{"source":{"targetRevision":"'"$BRANCH"'"}}}'

# Confirm
kubectl --context "$DV" -n argocd get application develop-techx-corp \
  -o jsonpath='{.spec.source.targetRevision}'
# Kỳ vọng: feat/mandate-17-resilience-containment
```

**⚠️ Blocker:** Không pause `develop-root` trước → selfHeal revert `targetRevision` về `develop` trong vài giây.

---

## PHASE 1a — Test R1: Dockerfile fix (pod start được)

**Mandate:** R1 — Dockerfile chứa đúng resilience handler.  
**Ảnh hưởng:** Rolling restart các pod techx-develop.  
**Thời gian:** ~3–5 phút.

```bash
# Sync app với feature branch
kubectl --context "$DV" -n argocd patch application develop-techx-corp \
  --type=merge -p '{"operation":{"sync":{}}}'

# Chờ Synced + Healthy
kubectl --context "$DV" -n argocd get application develop-techx-corp \
  -o jsonpath='{.status.sync.status} {.status.health.status}'

# Verify frontend-proxy không crash
kubectl --context "$DV" -n $NS get pod -l opentelemetry.io/name=frontend-proxy
kubectl --context "$DV" -n $NS logs -l opentelemetry.io/name=frontend-proxy --tail=20
```

**✅ Pass khi:** `STATUS=Running`, log không có `ModuleNotFoundError` / `COPY failed`.

**⚠️ Blocker:** Image chưa build từ CI → `ImagePullBackOff`. Kiểm tra CI workflow đã push image lên ECR chưa.

---

## PHASE 1b — Test R1: Kill downstream → SLO vẫn giữ ⭐

**Mandate:** *"Mentor tự giết một dependency... luồng ra tiền vẫn giữ SLO"*  
**Ảnh hưởng:** `ad` hoặc `recommendation` pod down ~5 phút trên develop.  
**Thời gian:** ~5 phút.

### Cách 1 — Scale về 0 (đơn giản nhất)

```bash
# Giết service ad (frontend gọi khi render trang)
kubectl --context "$DV" -n $NS scale deployment ad --replicas=0

# Đồng thời curl checkout flow để verify SLO
# (thay FRONTEND_URL bằng URL develop)
FRONTEND_URL=$(kubectl --context "$DV" -n $NS get svc frontend-proxy \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Test: browse homepage vẫn load được (ad down nhưng page vẫn hiện)
curl -o /dev/null -s -w "HTTP %{http_code} — Time: %{time_total}s\n" \
  http://$FRONTEND_URL

# Test: add to cart vẫn được
curl -o /dev/null -s -w "HTTP %{http_code} — Time: %{time_total}s\n" \
  http://$FRONTEND_URL/cart
```

### Cách 2 — NetworkPolicy block (realistic hơn, sau khi Phase 3 xong)

```bash
# Block traffic vào ad bằng NetworkPolicy tạm
kubectl --context "$DV" -n $NS apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-kill-ad
  namespace: $NS
spec:
  podSelector:
    matchLabels:
      opentelemetry.io/name: ad
  ingress: []   # block all ingress → ad không nhận được request
EOF

# Test flow như Cách 1

# Dọn dẹp sau test
kubectl --context "$DV" -n $NS delete networkpolicy test-kill-ad

# Scale ad lại nếu dùng Cách 1. LƯU Ý: `ad` giờ có HPA minReplicas=2 (commit d3c47ad)
# -> scale về 1 sẽ bị HPA kéo lại 2. Dùng 2 (hoặc để HPA tự phục hồi).
kubectl --context "$DV" -n $NS scale deployment ad --replicas=2
```

**✅ Pass khi:**
- Homepage trả về HTTP 200, thời gian < 3s (dù không có ad widget)
- Cart/checkout vẫn hoạt động bình thường
- Log frontend không có `500 Internal Server Error` do ad timeout

**⚠️ Blocker:**
- Frontend trả về 500 khi ad down → fallback chưa được implement đúng trong code resilience.
- Thời gian > 3s → timeout quá dài, cần kiểm tra `GRPC_TIMEOUT` hoặc circuit breaker config.

---

## PHASE 2 — Test R2: HA + Multi-AZ

**Mandate:** *"Chịu được mất cả một AZ — workload trải đủ nhiều AZ để luồng ra tiền vẫn giữ SLO"*  
**Ảnh hưởng:** Phase 2d (drain) evict pod, Karpenter provision node mới.  
**Thời gian:** 2a/2b/2c ~5 phút, 2d ~10 phút.

### 2a — PDB tồn tại đúng service

```bash
kubectl --context "$DV" -n $NS get pdb -o wide
```

**✅ Pass khi:** Thấy PDB cho `payment`, `shipping`, `currency`, `checkout`, `cart`. Cột `ALLOWED DISRUPTIONS = 1`.

**⚠️ Blocker:** `ALLOWED=0` → replicas chưa đủ 2.

---

### 2b — Pod trải đúng ≥2 AZ

```bash
kubectl --context "$DV" -n $NS get pod -l opentelemetry.io/name=payment \
  -o custom-columns="NAME:.metadata.name,NODE:.spec.nodeName,STATUS:.status.phase"

kubectl --context "$DV" get node \
  -o custom-columns="NAME:.metadata.name,ZONE:.metadata.labels.topology\.kubernetes\.io/zone"
```

**✅ Pass khi:** 2 pod payment/shipping/currency ở 2 AZ khác nhau.

---

### 2c — Karpenter NodePool zone minValues:2 — ⚪ **OPTIONAL, NGOÀI phạm vi mandate**

> **Mandate R2 nguyên văn:** *"workload **trải đủ nhiều AZ** để luồng ra tiền vẫn giữ SLO khi mất trọn một AZ."*
> Mandate **KHÔNG** nhắc `karpenter` / `autoscaling` / `cấp node` (grep = 0). Yêu cầu chỉ gồm
> **(a) workload trải AZ** và **(b) giữ SLO khi mất 1 AZ** — cả hai do **kube-scheduler**
> (topologySpread + PDB + ≥2 replica) lo, KHÔNG phụ thuộc Karpenter.
>
> **Đã verify: develop KHÔNG có Karpenter** — `crd nodepools.karpenter.sh` không tồn tại,
> không có `deploy/karpenter`, 0 ArgoCD app karpenter. 4 node đều từ **Managed Node Group**.
>
> ⇒ **Đây KHÔNG phải gap của mandate.** Bỏ qua 2c ở develop là hợp lệ; chỉ cần ghi chú trong
> evidence. Commit `d4cf460` (zone minValues cho develop nodepool) là **inert ở develop** —
> vô hại, có tác dụng khi nào develop cài Karpenter.

```bash
# (chỉ để xác nhận trạng thái, không phải điều kiện pass/fail của mandate)
kubectl --context "$DV" get crd nodepools.karpenter.sh 2>&1        # kỳ vọng: NotFound ở develop
kubectl --context "$DV" -n kube-system get deploy karpenter 2>&1   # kỳ vọng: NotFound ở develop
```

---

### 2d — Drain 1 AZ (mô phỏng mất AZ) — ⭐ **BẰNG CHỨNG CHÍNH CHO R2**

> ⚠️ Chỉ làm khi 2a/2b xanh. **Báo team trước.**

#### Chọn node — QUY TẮC BẮT BUỘC

| Node | AZ | Nodegroup | Taint | Quyết định |
|---|---|---|---|---|
| `ip-10-60-11-81` | **us-east-1a** | primary | none | ✅ **DRAIN node này** |
| `ip-10-60-12-102` | us-east-1b | primary | none | giữ |
| `ip-10-60-12-251` | us-east-1b | primary | none | giữ |
| `ip-10-60-12-28` | us-east-1b | **ops** | `dedicated` | 🚫 **CẤM DRAIN — node observability** (prometheus, grafana, jaeger, opensearch) |

**Vì sao drain AZ `us-east-1a`:**
- Node observability nằm ở **1b** → drain 1a **không đụng tới nó** (đúng yêu cầu tech lead).
- Grafana/Prometheus vẫn sống → **vẫn đo và chụp được SLO trong lúc chaos** (nếu drain 1b thì mất dashboard đúng lúc cần bằng chứng).
- 1a chỉ có **1 node**; 1b có 3 (drain 1b = mất 3/4 cluster).

> ❌ **TUYỆT ĐỐI KHÔNG** dùng `jsonpath items[0].spec.nodeName` để chọn node — nó có thể trúng node ở 1b, kể cả node ops.

```bash
DV=develop-ecommerce-develop-dev-eks
NS=techx-develop
NODE=ip-10-60-11-81.ec2.internal    # AZ us-east-1a — KHÔNG phải node ops

# Xác nhận lại trước khi drain: đúng AZ 1a và KHÔNG có taint 'dedicated'
kubectl --context "$DV" get node $NODE \
  -o custom-columns='NODE:.metadata.name,ZONE:.metadata.labels.topology\.kubernetes\.io/zone,TAINTS:.spec.taints[*].key'

kubectl --context "$DV" cordon $NODE
kubectl --context "$DV" drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=180s

# Quan sát money-path luôn còn >=1 pod Running (chạy song song ở terminal khác)
kubectl --context "$DV" -n $NS get pod -l opentelemetry.io/name=checkout -w
kubectl --context "$DV" -n $NS get pod --field-selector=status.phase=Pending
```

**✅ Pass khi:** checkout/cart/payment **không bao giờ = 0 pod Running** trong suốt quá trình drain; storefront vẫn mua hàng được; SLO trên Grafana không gãy.

**⚠️ Cảnh báo trước khi chạy:**
1. **ArgoCD control-plane nằm trên node 1a** (`application-controller`, `dex`, `applicationset`, `notifications`) → sẽ bị evict, ArgoCD gián đoạn ~1–2 phút. **Đợi sync xong rồi mới drain.**
2. Sau drain còn 3 node, nhưng node ops có taint `dedicated` → **thực chất chỉ 2 node** nhận workload thường. Theo dõi `Pending`.
3. **Develop KHÔNG có Karpenter → node bị drain KHÔNG được thay thế tự động.**

```bash
# BẮT BUỘC khôi phục sau khi thu xong bằng chứng
kubectl --context "$DV" uncordon $NODE
kubectl --context "$DV" get nodes -L topology.kubernetes.io/zone   # xác nhận node trở lại Ready
```

---

## PHASE 3a/3b/3c — Test R3: NetworkPolicy Chart + CNI Enforce

**Mandate:** *"Mỗi pod chỉ nói được với đúng thứ nó cần"*  
**Ảnh hưởng:** Phase 3c: `aws-node` DaemonSet rolling restart (~5s/node mất network).  
**Thời gian:** 3a offline ~2 phút, 3b CI ~5 phút, 3c TF apply ~8 phút.

### 3a — Chart render đúng (offline)

```bash
helm template techx-corp platform/charts/application \n  -f platform/gitops/environments/develop/values/values-application.yaml \n  -f platform/gitops/environments/develop/values/values-single-replica.yaml \n  --set networkPolicy.enabled=true \n  | grep -c "kind: NetworkPolicy"

# Verify CIDR develop (10.60.0.0/16)
helm template techx-corp platform/charts/application \n  -f platform/gitops/environments/develop/values/values-application.yaml \n  --set networkPolicy.enabled=true \n  | grep -E "10.60."
```

**✅ Pass khi:** Count = 31, CIDR `10.60.0.0/16` đúng.

### 3b — Terraform plan (review)

```bash
gh workflow run infra-develop.yaml --ref $BRANCH
# Xem log CI: 0 to add, 1 to change (vpc-cni), 0 to destroy
```

### 3c — Apply Terraform (bật CNI enforce)

```bash
# Input ĐÚNG của infra-develop.yaml: apply (bool), bootstrap_argocd (bool), confirm (string)
gh workflow run infra-develop.yaml --ref develop \
  -f apply=true -f bootstrap_argocd=false -f confirm=apply-develop

# Verify enforce đã bật: cờ nằm ở container aws-eks-nodeagent (args), không phải env aws-node
kubectl --context "$DV" -n kube-system get ds aws-node \
  -o jsonpath='{range .spec.template.spec.containers[?(@.name=="aws-eks-nodeagent")]}{.args}{end}' \
  | tr ',' '\n' | grep -i "network-policy"

# (tuỳ chọn) xác nhận từ phía addon
aws eks describe-addon --cluster-name ecommerce-develop-dev-eks --addon-name vpc-cni \
  --query 'addon.configurationValues' --output text \
  --profile Phase3-CDO-PermissionSet-458580846647
```

**✅ Pass khi:** thấy `--enable-network-policy=true` (và addon config chứa `enableNetworkPolicy: "true"`).

**⚠️ Blocker:** addon dùng `resolve_conflicts_on_update = "PRESERVE"` → nếu cờ không đổi, cân nhắc `OVERWRITE` cho vpc-cni rồi apply lại.

---

## PHASE 3d — Test R3: Attacker Pod (containment thật) ⭐

**Mandate:** *"Thử một pod 'kẻ tấn công': nó không quét/kết nối được sang service khác và không gọi ra ngoài được — chứng minh containment, không phải mô tả trên slide."*  
**Ảnh hưởng:** Deploy 1 pod test → xóa sau khi test. Không ảnh hưởng service thật.  
**Thời gian:** ~5 phút.

> ⚠️ Phase này chỉ có ý nghĩa SAU KHI 3c (CNI enforce) đã xanh và NetworkPolicy đã được enable (`networkPolicy.enabled=true` trong values).

```bash
# Deploy attacker pod (dùng image netshoot — có đầy đủ network tools)
kubectl --context "$DV" -n $NS apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: attacker
  namespace: $NS
  labels:
    app: attacker   # label không match ingress rule của service nào
spec:
  containers:
  - name: attacker
    image: nicolaka/netshoot
    command: ["sleep", "3600"]
  automountServiceAccountToken: false
EOF

# Chờ pod Running
kubectl --context "$DV" -n $NS get pod attacker -w
```

### Test lateral movement (phải bị block)

```bash
# Thử kết nối sang payment (phải timeout/refused)
kubectl --context "$DV" -n $NS exec attacker -- \
  curl -m 5 http://payment:8080/health 2>&1
# Kỳ vọng: "Connection timed out" hoặc "Connection refused"

# Thử kết nối sang checkout
kubectl --context "$DV" -n $NS exec attacker -- \
  curl -m 5 http://checkout:8080 2>&1
# Kỳ vọng: bị block

# Thử scan port toàn namespace (nmap)
kubectl --context "$DV" -n $NS exec attacker -- \
  nmap -p 8080 payment checkout currency --open -T4 2>&1
# Kỳ vọng: "Host seems down" hoặc no open ports
```

### Test egress ra ngoài (phải bị block)

```bash
# Thử gọi ra internet
kubectl --context "$DV" -n $NS exec attacker -- \
  curl -m 5 https://google.com 2>&1
# Kỳ vọng: "Connection timed out"

# Thử gọi metadata AWS (IMDS)
kubectl --context "$DV" -n $NS exec attacker -- \
  curl -m 5 http://169.254.169.254/latest/meta-data/ 2>&1
# Kỳ vọng: bị block (egress NP không whitelist IMDS)
```

### Dọn dẹp

```bash
kubectl --context "$DV" -n $NS delete pod attacker
```

**✅ Pass khi:**
- `curl payment` → timeout/refused (lateral movement blocked)
- `curl google.com` → timeout (egress blocked)
- `curl 169.254.169.254` → timeout (IMDS blocked)

**⚠️ Blocker:**
- **NP chưa bật:** Nếu `networkPolicy.enabled=false` (default) → attacker kết nối được tất cả. Phase 3d chỉ chạy sau khi flip `networkPolicy.enabled=true` và ArgoCD đã sync.
- **CNI chưa enforce:** VPC CNI chưa apply → NetworkPolicy object tồn tại nhưng không có effect. Phase 3c phải xong trước.

---

## PHASE 4a — Test R4: automountServiceAccountToken=false

**Mandate:** *"Pod bị chiếm không gọi được K8s API ngoài quyền tối thiểu"*  
**Ảnh hưởng:** Không có (chỉ đọc).  
**Thời gian:** ~2 phút.

```bash
# Kiểm tra tất cả pod
kubectl --context "$DV" -n $NS get pod \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t automount="}{.spec.automountServiceAccountToken}{"\n"}{end}'

# Verify không có token file trong pod thật
POD=$(kubectl --context "$DV" -n $NS get pod -l opentelemetry.io/name=payment \
  -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$DV" -n $NS exec $POD -- \
  ls /var/run/secrets/kubernetes.io/serviceaccount/ 2>&1
# Kỳ vọng: No such file or directory
```

**✅ Pass khi:** Tất cả pod `automount=false/nil`, không có token file.

---

## PHASE 4b — Test R4: ServiceAccount per-service + RBAC tối thiểu ⭐

**Mandate:** *"Mỗi service dùng service account riêng, quyền RBAC tối thiểu — pod bị chiếm không leo ra quyền cluster"*  
**Ảnh hưởng:** Không có (chỉ đọc + test từ trong pod).  
**Thời gian:** ~5 phút.

### Verify ServiceAccount per-service

```bash
# Liệt kê tất cả ServiceAccount trong namespace
kubectl --context "$DV" -n $NS get serviceaccount

# Verify mỗi pod dùng SA riêng (không dùng chung default)
kubectl --context "$DV" -n $NS get pod \
  -o custom-columns="POD:.metadata.name,SA:.spec.serviceAccountName"
```

**✅ Pass khi:** Mỗi service có SA riêng (vd `payment`, `checkout`, `shipping`...), không phải tất cả dùng `default`.

### Verify pod bị chiếm không gọi được K8s API

```bash
# Lấy pod nào đó đang chạy (không phải shopping-copilot vì nó cần IRSA)
POD=$(kubectl --context "$DV" -n $NS get pod -l opentelemetry.io/name=payment \
  -o jsonpath='{.items[0].metadata.name}')

# Thử gọi K8s API từ trong pod (không có token → phải fail)
kubectl --context "$DV" -n $NS exec $POD -- \
  sh -c 'curl -sk https://kubernetes.default.svc/api/v1/namespaces 2>&1 | head -5'
# Kỳ vọng: "Unauthorized" hoặc không kết nối được (không có token)

# Thử list pods trong namespace từ trong pod
kubectl --context "$DV" -n $NS exec $POD -- \
  sh -c 'curl -sk -H "Authorization: Bearer $(cat /var/run/secrets/kubernetes.io/serviceaccount/token 2>/dev/null)" https://kubernetes.default.svc/api/v1/namespaces/'"$NS"'/pods 2>&1 | head -5'
# Kỳ vọng: "No such file" (không có token) hoặc "Forbidden" (RBAC block)
```

**✅ Pass khi:** Pod không đọc được danh sách pods/secrets trong cluster → RBAC hoạt động đúng.

**⚠️ Blocker:**
- **Chưa tạo SA per-service trong chart:** Nếu chart chưa khai `serviceAccount.create: true` per-component → tất cả dùng `default`. Cần thêm vào values.
- **RBAC ClusterRole quá rộng:** Nếu SA có ClusterRole `cluster-admin` hoặc `view` rộng → pod leo quyền được. Phải dùng Role (namespace-scoped) với chỉ verb `get/list` trên resource cụ thể.

---

## PHASE 5 — Dọn dẹp + Tạo PR

**Ảnh hưởng:** Bật lại auto-sync, develop trở về trạng thái bình thường.  
**Thời gian:** ~2 phút.

```bash
# Revert targetRevision về develop (TRƯỚC KHI merge)
kubectl --context "$DV" -n argocd patch application develop-techx-corp \
  --type=merge -p '{"spec":{"source":{"targetRevision":"develop"}}}'

# Bật lại develop-root
kubectl --context "$DV" -n argocd patch application develop-root \
  --type=merge -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'

# KHÔNG bật automated cho develop-techx-corp!
# Trạng thái GỐC của app này là MANUAL (syncPolicy.automated = none). Sau khi un-pause
# develop-root (auto+selfHeal), nó sẽ tự render lại app từ Git về đúng trạng thái gốc.
# Patch thêm 'automated' ở đây là THỪA và tạo drift khác ban đầu.

# Confirm
kubectl --context "$DV" -n argocd get application develop-techx-corp \
  -o jsonpath='{.spec.source.targetRevision}'
# Kỳ vọng: develop
```

Sau đó: tạo PR `feat/mandate-17` → `develop` → merge → bàn team về sandbox.

---

## Bảng tổng kết verify (đầy đủ)

| Phase | Requirement | Mandate gốc | Pass khi | Blocker tiềm năng |
|---|---|---|---|---|
| **1a** | R1 Dockerfile | Pod Running sau fix | `STATUS=Running`, không CrashLoop | Image chưa build |
| **1b** ⭐ | R1 Fallback | Kill ad → checkout vẫn SLO | HTTP 200, < 3s, không 500 | Fallback chưa implement |
| **2a** | R2 PDB | PDB tồn tại | `ALLOWED=1` cho money-path | Replicas chưa đủ |
| **2b** | R2 Multi-AZ | Pod trải 2 AZ | 2 pod ở 2 AZ khác nhau | Cluster thiếu node AZ2 |
| **2c** | R2 Karpenter | NodePool zone | `minValues: 2` trong spec | App trỏ branch cũ |
| **2d** | R2 Drain | Mất AZ SLO giữ | Payment ≥1 pod khi drain | PDB block (replicas=1) |
| **3a** | R3 Chart | NP render đúng | 31 NP, CIDR `10.60.0.0/16` | CIDR sai trong values |
| **3b** | R3 TF plan | Plan an toàn | `1 change`, không destroy | TF code sai |
| **3c** | R3 CNI | Enforce bật | `ENABLE_NETWORK_POLICY=true` | Workflow thiếu input |
| **3d** ⭐ | R3 Attacker pod | Containment thật | curl payment/google → timeout | NP hoặc CNI chưa bật |
| **4a** | R4 Token | Không automount | `automount=false/nil`, no token file | Pod cần IRSA chưa whitelist |
| **4b** ⭐ | R4 RBAC | SA per-service + least-privilege | Pod không gọi được K8s API | SA chưa per-service, RBAC rộng |
| **5** | Cleanup | GitOps sạch | `targetRevision=develop` trước merge | Quên revert → drift |

---

## Timeline ước tính toàn bộ

```
Phase 0  (~2 phút)   : Chuẩn bị / pause root / trỏ nhánh
Phase 1a (~5 phút)   : Sync + verify pod Running
Phase 1b (~5 phút)   : Kill ad → test checkout SLO
Phase 2  (~15 phút)  : PDB + AZ spread + drain test
Phase 3a (~2 phút)   : Helm render offline
Phase 3b (~5 phút)   : TF plan CI
Phase 3c (~8 phút)   : TF apply VPC CNI
Phase 3d (~5 phút)   : Attacker pod test
Phase 4  (~5 phút)   : automount + RBAC verify
Phase 5  (~2 phút)   : Dọn dẹp + revert
─────────────────────
Tổng     : ~54 phút (không có blocker)
```

---

## Ghi chú vận hành

- **Sandbox:** Toàn bộ plan chỉ đụng cluster develop (458). Sandbox không bị ảnh hưởng cho đến Phase 5.
- **Thông báo team:** Báo team trước Phase 2d (drain) và Phase 3c (TF apply) — 2 bước có tác động cluster thật.
- **Thứ tự bắt buộc:** 0 → 1a → 1b → 2(a→d) → 3(a→b→c→d) → 4(a→b) → 5. Không skip 3c trước 3d.
- **Phase 3d là bằng chứng nộp mentor:** Screenshot `curl payment → timeout` + `curl google → timeout` là evidence cứng nhất cho R3.
- **Phase 1b là bằng chứng nộp mentor:** Screenshot checkout HTTP 200 khi ad=0 replicas là evidence R1.
