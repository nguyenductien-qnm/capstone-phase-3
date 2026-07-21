# Runbook verify Mandate 17 — cluster dev `ecommerce-dev-eks` (namespace: techx-tf1)

Rollout 2 phase: **Phase 0** bật CNI enforce (terraform) → **Phase 1** deploy R1/R2/R4 (NP tắt) → **Phase 2** bật NetworkPolicy (R3) → chaos → evidence.
Chỉ chạy trên context cluster dev. 5 mục xác minh gắn thẻ **[V1]–[V5]** đúng bước cần kiểm.

## 0. Chọn đúng cluster
```bash
kubectl config current-context          # arn:...:cluster/ecommerce-dev-eks
kubectl get ns techx-tf1
```

---

## PHASE 0 — Bật CNI NetworkPolicy enforcement (terraform, phối hợp trước)
> Nếu bỏ phase này, NetworkPolicy KHÔNG được enforce → R3 chỉ trang trí.
> Rollout `aws-node` DaemonSet (RollingUpdate 10%) → blip mạng ngắn cho pod mới. Cluster chỉ có techx-tf1 nên phạm vi hẹp.
```bash
cd terraform/environments/sandbox
terraform plan    # kỳ vọng: chỉ đổi addon vpc-cni (configuration_values enableNetworkPolicy)
terraform apply
```
**[V1] Confirm enforce đã áp (do resolve_conflicts_on_update=PRESERVE):**
```bash
aws eks describe-addon --cluster-name ecommerce-dev-eks --addon-name vpc-cni \
  --query 'addon.configurationValues' --output text          # phải chứa enableNetworkPolicy: "true"
kubectl -n kube-system get ds aws-node \
  -o jsonpath='{range .spec.template.spec.containers[?(@.name=="aws-eks-nodeagent")]}{.args}{end}{"\n"}'
  # phải thấy --enable-network-policy=true ; addon version ≥ v1.14 (hiện v1.22.4 OK)
```

---

## PHASE 1 — Commit 1: R1 + R2 + R4 (NetworkPolicy vẫn TẮT)
```bash
# commit gồm: chart _objects/values (zone-spread, automount, replicas), karpenter nodepool,
# frontend circuit breaker, label egress-internet (flagd/product-reviews/shopping-copilot).
# networkPolicy.enabled = false -> app KHÔNG bị siết.
git push   # ArgoCD selfHeal auto-sync (hoặc: argocd app sync techx-corp)
argocd app wait techx-corp --health
```

### 1a. R4 — không mount token
```bash
kubectl -n techx-tf1 get deploy frontend -o jsonpath='{.spec.template.spec.automountServiceAccountToken}{"\n"}'  # false
```

### 1b. R2 — replica + phân bố AZ
```bash
kubectl get nodes -L topology.kubernetes.io/zone
kubectl -n techx-tf1 get deploy frontend cart checkout product-catalog currency payment shipping

# [V3] topologySpread hostname-hard: có pod Pending (không đủ node) không? 7 node/3 AZ nên đủ.
kubectl -n techx-tf1 get pods --field-selector=status.phase=Pending

# Phân bố pod theo AZ (mỗi service money-path nên nằm ở ≥2 zone khác nhau):
for s in frontend cart checkout product-catalog currency payment shipping; do
  echo "== $s =="
  for p in $(kubectl -n techx-tf1 get pods -l opentelemetry.io/name=$s -o name); do
    node=$(kubectl -n techx-tf1 get $p -o jsonpath='{.spec.nodeName}')
    zone=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}')
    echo "  $p -> $node ($zone)"
  done
done
```

### 1c. [V4] R1 chuẩn bị — confirm Bedrock ra Internet public (trước khi bật NP ở Phase 2)
```bash
kubectl -n techx-tf1 exec deploy/shopping-copilot -- nslookup bedrock-runtime.us-east-1.amazonaws.com
# IP public -> rule internet-egress (except 10.0.0.0/8) OK.
# IP 10.x (VPC endpoint) -> phải sửa allow-internet-egress-selected (bỏ except dải đó).
```

---

## PHASE 2 — Commit 2: bật NetworkPolicy (R3)
```bash
# đổi networkPolicy.enabled: true trong platform/charts/application/values.yaml
git push && argocd app wait techx-corp --health
```

### 2a. NetworkPolicy đã áp
```bash
kubectl -n techx-tf1 get networkpolicy      # kỳ vọng ~28 policy
# Smoke test app: browse -> cart -> checkout vẫn chạy (allow-rules đúng đường).
```

### 2b. [V2] Confirm Prometheus vẫn scrape được (không mất metrics/SLO)
```bash
# Trên Prometheus UI (Status > Targets) hoặc:
kubectl -n techx-tf1 port-forward svc/<prometheus> 9090:9090
# -> mở /targets: app pod money-path phải UP (scrape intra-namespace đã phủ).
# LƯU Ý: target node/kubelet (:10250) & node-exporter (:9100) có thể DOWN vì rule
# apiserver-egress chỉ mở 443. Metric SLO app KHÔNG mất; nếu cần metric node thì mở
# thêm egress 10250/9100 tới dải node.
```

### 2c. [V5] Ghi chú (không cần làm): `apiServerCIDR: 10.0.0.0/16` cho 3 pod obs egress 443 toàn VPC
> Rộng hơn "chỉ API server" nhưng chấp nhận được (3 pod tin cậy, 1 port). Dùng CIDR vì IP ENI API server xoay.

---

## 3. Chaos (mỗi lần 1 kịch bản, thu evidence trước khi sang bước sau)
```bash
./kill-dependency.sh ad techx-tf1 120              # R1
./kill-dependency.sh recommendation techx-tf1 120  # R1
./drain-az.sh us-east-1a                            # R2 (AZ thật: us-east-1a/1b/1c)
./attacker-check.sh techx-tf1                       # R3/R4 — CHỈ có ý nghĩa nếu Phase 0 đã enforce
```

## 4. Evidence pack (CDO-237)
- Ảnh Grafana SLO/latency trong lúc chaos (khách không bị ảnh hưởng).
- Output phân bố AZ (≥2 zone) + `kubectl get networkpolicy`.
- Output `attacker-check` (bị chặn lateral + egress + K8s API).
- Output [V1] enforce ON + [V2] Prometheus targets UP.

## Rollback nhanh nếu app gãy do NetworkPolicy
```bash
# đặt networkPolicy.enabled: false trong platform/charts/application/values.yaml -> commit -> sync
# (không cần đụng terraform; enforce bật vẫn vô hại khi không có policy nào chọn pod)
```
