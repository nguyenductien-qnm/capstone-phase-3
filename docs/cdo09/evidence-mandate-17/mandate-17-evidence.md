# Mandate 17 — Resilience & Containment — EVIDENCE PACK

> **TF:** CDO-09 · **Người thực hiện:** Nguyen Dinh Thi
> **Cluster test:** `ecommerce-develop-dev-eks` (account 458580846647) · namespace `techx-develop`
> **Nhánh:** `feat/mandate-17-resilience-containment` · **PR:** #259
> **Ngày test:** ______ · **Người chứng kiến:** ______

---

## 0. Tóm tắt cho mentor

| Yêu cầu | Trạng thái | Bằng chứng số |
|---|---|---|
| **R1** — Sống qua 1 dependency chết | ☐ Pass ☐ Fail | SS-1, SS-2 |
| **R2** — Chịu mất cả 1 AZ | ☐ Pass ☐ Fail | SS-3, SS-4, SS-5 |
| **R3** — Khoanh mạng (NetworkPolicy) | ☐ Pass ☐ Fail | SS-6, SS-7, SS-8 |
| **R4** — Least-privilege K8s | ☐ Pass ☐ Fail | SS-9, SS-10 |

**Nguyên tắc:** mọi ô "Kết quả" phải điền bằng output THẬT. Không có screenshot = coi như chưa chứng minh.

---

## 1. R1 — Sống qua một dependency chết

> **Mandate:** *"Một service downstream (ad / recommendation / payment-provider…) lỗi hoặc chậm → luồng browse → cart → checkout **vẫn giữ SLO** nhờ timeout + fallback + degrade graceful; lỗi không lan ngược."*

### Đã implement gì
| Cơ chế | File:dòng |
|---|---|
| Circuit breaker (closed/open/half-open) | `src/frontend/utils/resilience/CircuitBreaker.ts:5, 21` |
| Ngưỡng lỗi / thời gian mở / timeout | `CircuitBreaker.ts:23-25, 37` |
| Single-flight half-open (chống dội burst khi hồi phục) | `CircuitBreaker.ts:30-33` |
| Log khi mạch đổi trạng thái | `CircuitBreaker.ts` → `transitionTo()` |
| `ad`: breaker + gRPC deadline + fallback `{ads:[]}` | `gateways/rpc/Ad.gateway.ts:15,19,26-27,32` |
| `recommendation`: breaker + deadline + fallback `{productIds:[]}` | `gateways/rpc/Recommendations.gateway.ts:15,19,27,32` |
| Đưa file vào image | `src/frontend/Dockerfile:27` |

### Cách chứng minh
```bash
# LƯU Ý: ad/recommendation có HPA minReplicas=2 -> scale 0 sẽ bị HPA kéo lại.
# Cách A (trước khi bật NP): xoá HPA tạm
kubectl -n techx-develop delete hpa ad
kubectl -n techx-develop scale deploy ad --replicas=0
kubectl -n techx-develop get pods -l opentelemetry.io/name=ad     # kỳ vọng: 0 pod

# Bấm thử storefront: browse -> add to cart -> checkout
# Khôi phục: sync lại ArgoCD (HPA + replicas trở lại)
```

### 📸 Screenshot cần chụp
- **SS-1** — `kubectl get pods -l opentelemetry.io/name=ad` cho thấy **0 pod** (dependency đã chết) **đặt cạnh** trang storefront vẫn load HTTP 200 (block quảng cáo trống — degrade graceful, không phải lỗi 500).
- **SS-2** — Hoàn tất **checkout thành công** trong lúc `ad` đang chết (ảnh trang xác nhận đơn) **+** dashboard Grafana SLO khoảng thời gian đó **không gãy**.
- *(Bonus)* log frontend có dòng `[circuit-breaker:ad] state closed -> open` — chứng minh mạch mở đúng.

### Kết quả
```
Thời điểm:            ______
ad pods sau khi giết: ______
HTTP code trang chủ:  ______   (kỳ vọng 200)
Checkout:             ☐ thành công  ☐ thất bại
Lỗi 500 do ad?:       ☐ không  ☐ có
```

---

## 2. R2 — Chịu được mất cả một AZ

> **Mandate:** *"…một **vùng khả dụng (AZ) sập bất ngờ**: workload **trải đủ nhiều AZ** để luồng ra tiền vẫn giữ SLO khi mất trọn một AZ."*
> ⚠️ Mandate **không** yêu cầu Karpenter/autoscaling — chỉ yêu cầu **trải AZ** + **giữ SLO**.

### Đã implement gì
| Cơ chế | File:dòng |
|---|---|
| Zone topologySpread (soft `ScheduleAnyway`) | `charts/application/templates/_objects.tpl:60-63` |
| PDB template | `_objects.tpl:357, 361` |
| ≥2 replica + PDB + spread cho money-path | `values.yaml`: frontend(746), frontend-proxy(843), cart(368), checkout(477), product-catalog(1136), currency(599), payment(1091), shipping(1454), ad(327), recommendation(1319), ml-guard(1043) |

### Cách chứng minh
```bash
# (a) Pod trải >=2 AZ
for s in frontend cart checkout product-catalog currency payment shipping; do
  echo "== $s =="
  for p in $(kubectl -n techx-develop get pods -l opentelemetry.io/name=$s -o name); do
    n=$(kubectl -n techx-develop get $p -o jsonpath='{.spec.nodeName}')
    z=$(kubectl get node "$n" -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}')
    echo "  $p -> $z"
  done
done

# (b) PDB
kubectl -n techx-develop get pdb

# (c) DRAIN AZ us-east-1a — CHỈ node ip-10-60-11-81 (KHÔNG đụng node ops/observability ở 1b)
kubectl cordon ip-10-60-11-81.ec2.internal
kubectl drain ip-10-60-11-81.ec2.internal --ignore-daemonsets --delete-emptydir-data --timeout=180s
kubectl uncordon ip-10-60-11-81.ec2.internal     # BẮT BUỘC khôi phục
```

### 📸 Screenshot cần chụp
- **SS-3** — Output (a): mỗi service money-path có pod ở **2 AZ khác nhau** (`us-east-1a` và `us-east-1b`).
- **SS-4** — `kubectl get pdb`: cột **ALLOWED DISRUPTIONS = 1** cho money-path.
- **SS-5** — **Trong lúc drain**: `kubectl get pods -l opentelemetry.io/name=checkout -w` cho thấy **luôn ≥1 pod Running** (không bao giờ về 0) **+** Grafana SLO không gãy **+** checkout trên web vẫn thành công.

### Kết quả
```
Node bị drain:        ip-10-60-11-81.ec2.internal (us-east-1a)
Node observability:   ip-10-60-12-28 (us-east-1b) — KHÔNG bị đụng ☐ xác nhận
Service trải 2 AZ:    ______ / 7
checkout min Running: ______   (kỳ vọng >= 1, KHÔNG BAO GIỜ = 0)
Pod Pending sau drain: ______
Đã uncordon:          ☐ rồi
```

### Ghi chú phạm vi (nêu rõ với mentor)
- **Develop KHÔNG chạy Karpenter** (verify: `crd nodepools.karpenter.sh` NotFound, 4 node đều từ Managed Node Group). Node bị drain **không được thay thế tự động**.
- Điều này **không ảnh hưởng yêu cầu mandate** vì mandate chỉ đòi *trải AZ* + *giữ SLO*, do scheduler lo.
- Cấu hình Karpenter `zone minValues:2` đã có sẵn trong repo (`platform/karpenter/` cho sandbox, `environments/develop/karpenter/` cho develop) — sẽ có tác dụng khi env bật Karpenter.
- 7 service chưa HA (1 replica): email, quote, product-reviews, shopping-copilot, llm, accounting, fraud-detection — đều async/không-thiết-yếu, **không nằm trên luồng ra tiền đồng bộ**.

---

## 3. R3 — Khoanh mạng (NetworkPolicy)

> **Mandate:** *"Mỗi pod chỉ nói được với đúng thứ nó cần; một pod bị chiếm **không quét / kết nối được khắp cluster**; egress bị khóa."*
> **Phải nộp:** *"Cho mentor xem NetworkPolicy khoanh **đang bật**, và thử một **pod 'kẻ tấn công'**… chứng minh containment, không phải mô tả trên slide."*

### Đã implement gì
| Rule | `templates/networkpolicy.yaml` |
|---|---|
| default-deny ingress + egress | L20 |
| allow DNS egress | L31 |
| intra-namespace egress (caller→callee) | L52 |
| flagd ingress :8013 | L67 |
| public edge (frontend-proxy) | L85 |
| **per-service ingress** (17 service, theo đồ thị `*_ADDR` thật) | L100 · config `values.yaml:100+` |
| metrics scrape (prometheus, otel) | L121 |
| egress API-server cho observability | L141 |
| observability sinks | L166 |
| **egress managed datastore** (ElastiCache 6379 / MSK 9092-9096 / RDS 5432) | L186 |
| egress Internet chỉ pod có label `egress-internet` | L213 |
| **CNI enforce** (điều kiện tiên quyết) | `terraform/modules/eks/{variables.tf:231, main.tf:363}` + `environments/develop/main.tf:75` |

### ⚠️ Điều kiện tiên quyết — KHÔNG BỎ QUA
1. `terraform apply` develop (dispatch `infra-develop`: `apply=true`, `bootstrap_argocd=false`, `confirm=apply-develop`) → bật **VPC CNI NetworkPolicy enforcement**.
2. Flip `networkPolicy.enabled: true` → sync ArgoCD.

> Nếu bỏ qua bước 1, NetworkPolicy **tồn tại nhưng KHÔNG được thực thi** → attacker pod sẽ kết nối được mọi thứ và ta hiểu nhầm là "fail".

### Cách chứng minh
```bash
# (a) Xác nhận CNI ĐANG enforce
kubectl -n kube-system get ds aws-node \
  -o jsonpath='{range .spec.template.spec.containers[?(@.name=="aws-eks-nodeagent")]}{.args}{end}' \
  | tr ',' '\n' | grep -i network-policy      # kỳ vọng: --enable-network-policy=true

# (b) NetworkPolicy đang bật
kubectl -n techx-develop get networkpolicy    # kỳ vọng ~31 policy

# (c) Attacker pod
kubectl -n techx-develop run attacker --image=nicolaka/netshoot --restart=Never \
  --overrides='{"spec":{"automountServiceAccountToken":false}}' -- sleep 3600

kubectl -n techx-develop exec attacker -- nc -zv -w5 cart 8080        # PHẢI timeout
kubectl -n techx-develop exec attacker -- nc -zv -w5 checkout 8080    # PHẢI timeout
kubectl -n techx-develop exec attacker -- curl -m5 https://google.com # PHẢI fail
kubectl -n techx-develop exec attacker -- nslookup cart               # DNS vẫn OK (được phép)
kubectl -n techx-develop delete pod attacker
```

### 📸 Screenshot cần chụp
- **SS-6** — Output (a): `--enable-network-policy=true` (chứng minh enforce **đang bật**, không phải chỉ có file YAML).
- **SS-7** — Output (b): `kubectl get networkpolicy` liệt kê ~31 policy (default-deny-all, allow-ingress-*, allow-datastore-egress-*, …).
- **SS-8** — ⭐ **BẰNG CHỨNG MẠNH NHẤT**: terminal attacker pod cho thấy **`nc cart` timeout** + **`curl google.com` fail** + **`nslookup` OK** trong CÙNG một ảnh. Kèm ảnh storefront vẫn mua hàng bình thường (chứng minh khoanh mạng mà không gãy app).

### Kết quả
```
CNI enforce:              ☐ true  ☐ false
Số NetworkPolicy:         ______  (kỳ vọng ~31)
nc cart:                  ☐ timeout/refused  ☐ kết nối được
nc checkout:              ☐ timeout/refused  ☐ kết nối được
curl google.com:          ☐ fail  ☐ thành công
nslookup (DNS):           ☐ OK    ☐ hỏng
Money-path vẫn chạy:      ☐ có    ☐ không
```

---

## 4. R4 — Least-privilege ở tầng Kubernetes

> **Mandate:** *"Mỗi service dùng service account riêng, quyền RBAC tối thiểu, không mount token quá rộng — pod bị chiếm **không gọi được K8s API ngoài quyền tối thiểu**, không leo ra quyền cluster."*

### Đã implement gì
| Cơ chế | File:dòng | Trạng thái |
|---|---|---|
| `automountServiceAccountToken: false` mặc định | `_objects.tpl:44` + `values.yaml:51` | ✅ |
| Override per-component khi service thực sự cần API | `_objects.tpl:44` (`hasKey`) | ✅ |
| SA riêng cho service cần IRSA | `values.yaml:1223` (product-reviews), `1390` (shopping-copilot) | ✅ |
| SA riêng cho 22 service còn lại | — | ⚪ **CÓ CHỦ ĐÍCH KHÔNG LÀM** — xem §4.1 |
| RBAC Role/RoleBinding per-SA | — | ⚪ **CÓ CHỦ ĐÍCH KHÔNG LÀM** — xem §4.1 |

### 4.1 — Vì sao KHÔNG tách SA riêng / KHÔNG thêm Role cho 22 service còn lại

> **Đây là quyết định kỹ thuật có chủ đích, không phải thiếu sót.**

Mandate viết: *"Mỗi service dùng service account riêng, quyền RBAC tối thiểu, không mount token quá rộng —
**pod bị chiếm không gọi được K8s API ngoài quyền tối thiểu, không leo ra quyền cluster**."*

Vế in đậm là **mục tiêu**; ba vế trước là **phương tiện** thường dùng để đạt nó. Ở hệ này mục tiêu đã đạt
bằng đường khác **chặt hơn**:

| Lớp phòng thủ | Trạng thái | Hệ quả |
|---|---|---|
| Token SA trong pod | **KHÔNG mount** (`automount=false`) | Pod **không thể xác thực** vào K8s API |
| RoleBinding cho app service | **KHÔNG có** | K8s deny mặc định ⇒ quyền = **0** |
| ClusterRoleBinding trỏ SA app | **KHÔNG có** | Không có đường **leo quyền cluster** |

⇒ **Quyền hiệu dụng của app service hiện là ZERO** — mức chặt nhất có thể.
Tách SA riêng chỉ đổi *tên* một object mà pod **không bao giờ mount tới** ⇒ **không thay đổi quyền hiệu dụng**.
Thêm Role/RoleBinding chỉ có thể làm quyền **rộng ra**, không thể chặt hơn 0.

**Chi phí nếu vẫn làm:** sửa tay 22 khối values (helper đặt tên SA theo `Release.Name`, thiếu `name:` là
**trùng tên SA** giữa các component), rollout lại 26 pod, tăng rủi ro ngay trước buổi demo — đổi lấy **0 lợi ích bảo mật**.

**Khi nào sẽ làm:** khi có service thực sự cần gọi K8s API (lúc đó bật `automountServiceAccountToken: true`
per-component + tạo SA riêng + Role tối thiểu cho đúng service đó). Khuôn đã sẵn trong chart
(`component-serviceaccount.yaml`, `_objects.tpl:44` dùng `hasKey`).

### 📸 Screenshot bổ sung — chứng minh lập luận trên
- **SS-11** — 3 lệnh dưới đây chạy liền nhau trong 1 ảnh (mentor có thể tự gõ lại tại chỗ):
```bash
# 1) Pod KHÔNG có token
kubectl -n techx-develop exec <pod-payment> -- ls /var/run/secrets/kubernetes.io/serviceaccount/
#    -> No such file or directory

# 2) KHÔNG RoleBinding nào cho app service
kubectl -n techx-develop get rolebinding
#    -> chỉ grafana + reloader (do subchart tạo), KHÔNG có app service

# 3) KHÔNG SA app nào có quyền cluster-wide
kubectl get clusterrolebinding -o json \
  | jq '[.items[] | select(.subjects[]?; .kind=="ServiceAccount" and .namespace=="techx-develop") | .metadata.name]'
#    -> chỉ observability (prometheus, otel-collector, grafana, kube-state-metrics)
```

### Cách chứng minh
```bash
# (a) Không pod nào mount token
kubectl -n techx-develop get pod \
  -o custom-columns='POD:.metadata.name,AUTOMOUNT:.spec.automountServiceAccountToken'

# (b) Trong pod thật: không có token file, không gọi được K8s API
POD=$(kubectl -n techx-develop get pod -l opentelemetry.io/name=payment -o jsonpath='{.items[0].metadata.name}')
kubectl -n techx-develop exec $POD -- ls /var/run/secrets/kubernetes.io/serviceaccount/  # No such file
kubectl -n techx-develop exec $POD -- sh -c 'curl -sk -m5 https://kubernetes.default.svc/api/v1/namespaces/techx-develop/pods | head -5'
```

### 📸 Screenshot cần chụp
- **SS-9** — Output (a): cột `AUTOMOUNT = false` cho các pod app.
- **SS-10** — Output (b): `ls` báo **No such file or directory** + gọi K8s API trả **Unauthorized/Forbidden** → chứng minh pod bị chiếm không leo quyền được.

### Kết quả
```
Pod automount=false:  ______ / ______
Token file trong pod: ☐ không có  ☐ có
Gọi K8s API:          ☐ Unauthorized/Forbidden  ☐ đọc được
```

---

## 5. Gap đã biết & rủi ro chấp nhận (khai báo minh bạch)

| # | Mục | Mức | Lý do / hướng xử lý |
|---|---|---|---|
| 1 | Không thêm RBAC Role/RoleBinding cho app service | ⚪ **Quyết định có chủ đích** | Quyền hiệu dụng đã = **0** (không token + không binding). Thêm Role chỉ có thể làm **rộng ra**. Chi tiết + bằng chứng: **§4.1**, ảnh **SS-11**. |
| 2 | SA riêng mới 2/24 service (còn lại dùng SA chung) | ⚪ **Quyết định có chủ đích** | `automount=false` ⇒ SA **không được mount** ⇒ tách SA **không đổi quyền hiệu dụng**. Đổi lại tốn 22 sửa tay + rollout 26 pod. Chi tiết: **§4.1**. |
| 3 | 7 service chưa HA (1 replica) | 🟡 | email, quote, product-reviews, shopping-copilot, llm, accounting, fraud-detection — async/không-thiết-yếu. |
| 4 | Develop không có Karpenter | ⚪ | **Không thuộc yêu cầu mandate** (mandate chỉ đòi trải AZ + giữ SLO). |
| 5 | `apiServerCIDR`/`datastoreEgress.vpcCidr` mở tới VPC CIDR | ⚪ | Rộng hơn "chỉ API server/datastore" nhưng giới hạn ở vài pod tin cậy + đúng cổng. IP ENI xoay nên không hardcode được. |
| 6 | NetworkPolicy `enabled: false` mặc định | ⚪ | **Cố ý** — rollout staged, bật ở bước riêng có rollback. |

---

## 6. Checklist nộp

- [ ] SS-1, SS-2 — R1 (dependency chết → checkout vẫn chạy)
- [ ] SS-3, SS-4, SS-5 — R2 (trải AZ + PDB + drain 1 AZ giữ SLO)
- [ ] SS-6, SS-7, SS-8 — R3 (CNI enforce ON + ~31 policy + attacker bị chặn)
- [ ] SS-9, SS-10 — R4 (automount=false + không gọi được K8s API)
- [ ] SS-11 — R4 (không token + không RoleBinding + không ClusterRoleBinding ⇒ quyền = 0)
- [ ] Đã `uncordon` node sau drain
- [ ] Đã khôi phục `ad` (HPA + replicas) sau test R1
- [ ] Đã xoá attacker pod
- [ ] Đã revert ArgoCD về trạng thái gốc (targetRevision `develop`, un-pause `develop-root`)

---

## 7. Ràng buộc mandate đã tuân thủ

- ✅ **Không đụng flagd** — flagd chỉ được thêm allow-rule để tiếp tục hoạt động (ingress :8013, egress giữ nguyên ở develop vì flagd dùng file local).
- ✅ **Không sửa code team AI** — R1 chỉ chạm `src/frontend`; không đụng `aiops/`, `shopping-copilot`, `product-reviews`.
- ✅ **Storefront public, ops private** — `frontend-proxy` có rule public-edge; observability chỉ nhận nội bộ.
- ✅ **Trong ngân sách** — không thêm node/hạ tầng; chỉ +replica cho service nhỏ (~50m CPU) và bật cờ CNI có sẵn.
