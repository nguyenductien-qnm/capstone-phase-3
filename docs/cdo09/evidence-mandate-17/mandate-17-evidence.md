# Mandate 17 — Resilience & Containment — EVIDENCE PACK

> **TF:** CDO-09 · **Người thực hiện:** Nguyen Dinh Thi
> **Cluster test:** `ecommerce-develop-dev-eks` (account 458580846647) · namespace `techx-develop`
> **Nhánh:** `feat/mandate-17-resilience-containment` · **PR:** #259 (R1/R2/R4, đã merge 22/07) → **#287** (R3 + vá + hồ sơ này)
> **Ngày test:** **22/07/2026**, 10:20–11:50 UTC (17:20–18:50 GMT+7)

---

## 0. Tóm tắt cho mentor

| Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|
| **R1** — Sống qua 1 dependency chết | ✅ **Pass** | `logs/R1-*` · SS-02, SS-01c |
| **R2** — Chịu mất cả 1 AZ | ✅ **Pass** (có 1 gap khai báo ở §5) | `logs/R2-*` · SS-06 |
| **R3** — Khoanh mạng (NetworkPolicy) | ✅ **Pass** sau khi vá 3 lỗ hổng | `logs/R3-*` · SS-08 |
| **R4** — Least-privilege K8s | ✅ **Pass** | `logs/SS-09/10/11-*` |

**Nguyên tắc:** mọi ô "Kết quả" dưới đây điền bằng output THẬT, trích từ `logs/`. Mỗi dòng đều truy ngược được về một file log cụ thể.

### Điều đáng nói nhất của buổi test

Bật `default-deny` trên cluster thật làm lộ **3 lỗ hổng mà đọc YAML không thể thấy** — cả ba đều đã vá và kiểm chứng lại (chi tiết §3):

1. **VPC CNI đối chiếu policy với đích GỐC, TRƯỚC khi kube-proxy DNAT.** Mở `ipBlock` bằng CIDR của ENI control-plane là *không đủ*: client gọi `kubernetes.default` đi qua ClusterIP `172.20.0.1` nên không khớp và bị drop. `kube-state-metrics` CrashLoopBackOff vì lý do này.
2. **Scraper cần egress ra ngoài namespace** (kubelet `:10250`, CoreDNS `:9153` ở kube-system) — thiếu thì 10/17 target Prometheus DOWN, dashboard tài nguyên trống.
3. **Grafana có 3 container `k8s-sidecar`** watch ConfigMap qua API server — cũng dính đúng bẫy pre-DNAT ở mục 1. Đây là ca **hỏng im lặng** nguy hiểm nhất: sidecar retry vô hạn chứ không crash, pod vẫn `4/4 Running`, dashboard cũ vẫn hiện vì đã nằm trên đĩa. **Bài kiểm tra "0 pod không khỏe" KHÔNG bắt được ca này** — chỉ đọc log sidecar mới thấy.

Bài học: **một NetworkPolicy "trông đúng" khi review vẫn có thể sai ở runtime.** Chỉ chạy thật mới phát hiện được.

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

### Kết quả — ✅ PASS

| Hạng mục | Kết quả thật | Nguồn |
|---|---|---|
| Thời điểm | `ad` bị giết 10:23:34Z → khôi phục 10:26:24Z | `R1-01`, `R1-05` |
| `ad` pod sau khi giết | **0** (`No resources found`); HPA đã xoá trước để nó không kéo lại | `R1-01-ad-down.txt` |
| `/api/data` khi `ad` chết | **12/12 request HTTP 200 + body `[]`** — fallback, **không có 5xx** | `R1-02-fallback-http.txt` |
| Checkout khi `ad` chết | ✅ **thành công** — `orderId=a07c3cd8-85b7-11f1-a180-7e04759d1d47` | `R1-04-money-path-ok.txt` |
| Lỗi 500 do `ad`? | **Không.** Grafana: error rate **0 req/s ở MỌI service** suốt cửa sổ sự cố | SS-01c |
| Trang sản phẩm | Render đủ giá + nút Add To Cart, chỉ thiếu banner quảng cáo | SS-02 |

**Vòng đời mạch — bắt được đầy đủ trong log frontend** (`R1-03`, `R1-06`, `R1-07`):
```
[circuit-breaker:ad] state closed    -> open      (failures=5)   <- đúng ngưỡng cấu hình
[circuit-breaker:ad] state open      -> half-open (failures=5)
[circuit-breaker:ad] state half-open -> open      (failures=6)   <- probe khi ad còn chết
[circuit-breaker:ad] state open      -> half-open (failures=9)
[circuit-breaker:ad] state half-open -> closed    (failures=0)   <- tự phục hồi
```

> **Chi tiết kỹ thuật đáng lưu ý.** Sau khi `ad` sống lại, probe vẫn hỏng **tức thì (~0.7 ms, không phải timeout 2 s)** trong khoảng 1 phút — đó là gRPC channel đang ở backoff `TRANSIENT_FAILURE`, **không phải lỗi circuit breaker**. Ngoài ra mạch là **per-pod**, mà NLB hash theo source IP nên curl từ ngoài luôn rơi vào cùng một pod. Phải bắn traffic từ trong cluster vào **đúng pod đang mở mạch** mới bắt được dòng `-> closed` (`R1-07`).

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

### Kết quả — ✅ PASS (kèm 1 gap khai báo minh bạch)

| Hạng mục | Kết quả thật | Nguồn |
|---|---|---|
| Node bị drain | `ip-10-60-11-81.ec2.internal` (us-east-1a) — node **duy nhất** ở 1a | `R2-02` |
| Node observability | `ip-10-60-12-28` (1b) — ✅ **KHÔNG bị đụng**, đúng yêu cầu tech lead | `R2-00` |
| PDB có chặn eviction không | ✅ **Có** — hàng loạt `Cannot evict pod as it would violate the pod's disruption budget`, drain bị tiết chế đúng ý đồ | `R2-02-drain.txt` |
| Pod còn lại trên node sau drain | Chỉ **DaemonSet** (`otel-collector-agent`) — sạch | `R2-03` |
| Deployment sống sót | **25/25** healthy, dồn hết về us-east-1b | `R2-03` |
| Pod Pending sau drain | **0** | `R2-03` |
| Service ≥2 replica trải 2 AZ (sau khôi phục) | **12/13** | `R2-07` |
| Uptime trong lúc drain | **194/200 (97%)** — xem gap bên dưới | `R2-01` |
| Đã uncordon | ✅ rồi, + `rollout restart` để trải lại AZ | `R2-06` |

**Vì sao 12/13 chứ không phải 13/13:** `product-reviews` còn nằm 1 AZ vì tôi **cố ý không restart** nó — đó là service của team AI, mandate cấm đụng. Nó sẽ tự trải lại ở lần rollout kế tiếp.

> **⚠️ Gap phải nói thẳng với mentor: uptime 97%, không phải 100%.**
> 5 request lỗi dồn trong cửa sổ **67 giây** (10:47:43 → 10:48:50). **Không phải do pod chết** — mọi deployment đều Available suốt quá trình. Nguyên nhân đã truy được: `frontend-proxy` dùng NLB `target-type=ip` với `preStop: sleep 5` + `terminationGracePeriodSeconds: 30`, **ngắn hơn** thời gian NLB đánh dấu target unhealthy → NLB vẫn đẩy traffic vào pod đã terminate (`R2-04-gap-analysis.txt`).
> Khắc phục là tăng `preStop` hoặc đặt `deregistration_delay` — **thuộc cấu hình LB, ngoài phạm vi Mandate 17**, đã ghi vào §5 để xử lý riêng.
>
> **Cách đo:** tôi đo bằng vòng HTTP 3 giây/lần vào `/api/products` qua NLB (đường người dùng thật), **không phải** `kubectl get pod -w`. Cách này khắt khe hơn vì bắt được cả lỗi tầng LB mà nhìn pod không thấy — và đó chính là lý do phát hiện được gap trên.

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
kubectl -n techx-develop get networkpolicy    # kỳ vọng 32 policy (31 + allow-scraper-egress-cluster)

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

### Kết quả — ✅ PASS (sau khi vá 3 lỗ hổng, xem dưới)

| Hạng mục | Kết quả thật | Nguồn |
|---|---|---|
| CNI enforce | ✅ **true** — `aws-eks-nodeagent` chạy `--enable-network-policy=true` | `R3-00-cni-enforce.txt` |
| Số NetworkPolicy | **32** (31 ban đầu + `allow-scraper-egress-cluster` thêm khi vá) | `R3-13-policies-live.txt` |
| Pod lạ → `cart:8080` | ✅ **000 bị chặn** | `R3-12` |
| Pod lạ → `payment:50051` | ✅ **000 bị chặn** | `R3-12` |
| Pod lạ → `checkout`, `product-catalog`, `llm`, `valkey-cart` | ✅ **000 bị chặn cả 4** | `R3-12` |
| Pod lạ → Internet (`example.com`) | ✅ **000 bị chặn** | `R3-12` |
| Pod lạ → API server ClusterIP | ✅ **000 bị chặn** | `R3-12` |
| DNS (`nslookup cart...`) | ✅ **OK** — trả `172.20.242.234`, đúng thiết kế `allow-dns-egress` | `R3-04` |
| Money-path dưới policy | ✅ **chạy** — `orderId=4044e116-85c3-11f1-a01d-2aacf2a180bf` | `R3-12` |
| Prometheus target | **16/17 UP** | `R3-11` |
| Pod không khỏe | **0** | `R3-12` |

> Target còn lại DOWN là `jaeger:8888` với `connection refused` — **endpoint chết sẵn từ trước, không do policy**. Dấu hiệu phân biệt: policy drop luôn biểu hiện **timeout** (`context deadline exceeded`), còn `connection refused` nghĩa là gói tin tới nơi nhưng không có ai lắng nghe.

### 🔬 Ba lỗ hổng phát hiện khi chạy thật — và cách truy vết

**Lỗ hổng 1 — `kube-state-metrics` CrashLoopBackOff.**
Ngay sau khi apply, ksm vào CrashLoop: liveness `:8080/livez` bị `context deadline exceeded`.
*Kiểm chứng nhân quả:* gỡ toàn bộ policy → ksm khỏe lại ngay (`R3-06`). Vậy chắc chắn do policy, không phải trùng hợp.
*Truy nguyên gốc rễ:* dựng 1 pod thử nghiệm, áp **đúng** rule `apiServerEgress` (chỉ mở `10.60.0.0/16:443`), rồi so hai đích:

| Đích | Trước policy | Sau policy |
|---|---|---|
| ClusterIP `172.20.0.1:443` | 401 (tới được) | **000 — bị drop** |
| ENI thật `10.60.11.189:443` | 401 | **401 — vẫn thông** |

⇒ **VPC CNI đối chiếu policy với đích GỐC, TRƯỚC khi kube-proxy DNAT.** Mọi client gọi `kubernetes.default` đều chết dù IP thật của API server nằm trong CIDR đã mở. ksm kẹt list/watch → `/livez` không kịp serve → kubelet giết (`R3-07`).
*Vá:* thêm `observability.apiServerClusterIP: 172.20.0.1/32` — chỉ đúng `/32`, **không** mở cả service CIDR.

**Lỗ hổng 2 — Prometheus mất metrics hạ tầng.**
Sau khi vá lỗ hổng 1, ksm ổn định nhưng kiểm tra sâu thì **10/17 target DOWN**: kubelet `:10250` (6 target node + cadvisor) và CoreDNS `:9153`, ALB controller `:8080` ở namespace `kube-system` — đều nằm **ngoài** namespace nên podSelector không với tới (`R3-10`).
*Vá:* policy mới `allow-scraper-egress-cluster`. Sau vá: **16/17 UP** (`R3-11`).

**Lỗ hổng 3 — Grafana `k8s-sidecar` mất API server (phát hiện khi tự review lại).**
`grafana` chạy **3 container `k8s-sidecar`** (dashboard / datasource / alert) watch ConfigMap qua API server, nhưng **không** có trong `apiServerEgress`. Chúng dính đúng bẫy pre-DNAT ở lỗ hổng 1:
```
ConnectTimeoutError(HTTPSConnection(host='172.20.0.1', port=443)...
  /api/v1/namespaces/techx-develop/configmaps?labelSelector=grafana_dashboard&watch=True
```
*Vì sao suýt lọt:* đây là ca **hỏng im lặng**. `k8s-sidecar` retry vô hạn chứ không crash → pod vẫn `4/4 Running` → bài kiểm tra **"0 pod không khỏe" ở trên KHÔNG bắt được**. Dashboard cũ vẫn hiện bình thường vì đã nằm sẵn trên đĩa; chỉ dashboard/datasource **mới** là không bao giờ xuất hiện. Nếu không đọc log sidecar thì có thể nhiều tuần sau mới có người phát hiện.
*Vá:* thêm `grafana` vào `apiServerEgress`. Sau vá: **0 lỗi timeout** trong 90 s theo dõi, sidecar trở lại `Loading incluster config...` bình thường (`R3-14-grafana-sidecar-fix.txt`).
*Bài học rút ra cho lần sau:* nghiệm thu NetworkPolicy **không được** dừng ở "pod có Running không". Phải liệt kê **mọi** thành phần gọi API server — kể cả **sidecar** — rồi đọc log từng cái.

**Kiểm chứng bản vá KHÔNG nới lỏng containment.** Cho pod lạ thử đúng 3 đường vừa mở:

| Đường vừa mở cho scraper | Pod lạ có lợi dụng được? |
|---|---|
| kubelet `10.60.12.251:10250` | ❌ **000 — bị chặn** |
| CoreDNS `10.60.12.95:9153` | ❌ **000 — bị chặn** |
| API ClusterIP `172.20.0.1:443` | ❌ **000 — bị chặn** |

*(`R3-12`)* — vì các rule đều gắn `podSelector` theo tên scraper, không phải mở toàn namespace.

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

### Kết quả — ✅ PASS

| Hạng mục | Kết quả thật | Nguồn |
|---|---|---|
| Pod `automountServiceAccountToken=false` | **toàn bộ pod app** | `SS-09-automount.txt` |
| Volume `kube-api-access-*` trong pod | **0/27** pod app có — dùng pod observability làm đối chứng (chúng *có* volume này) | `SS-10-no-token-api-denied.txt` |
| RoleBinding / ClusterRoleBinding cho app service | **Không có cái nào** | `SS-11-zero-rbac.txt` |
| Pod lạ gọi K8s API (kiểm chứng lại dưới NetworkPolicy) | **000 — bị chặn ngay tầng mạng**, chưa cần tới tầng xác thực | `R3-12` |

> **Vì sao chứng minh bằng cấu trúc thay vì `exec` vào pod.** Image các service money-path (`payment`…) là **distroless — không có shell, không có `ls`**, nên `kubectl exec ... -- ls` bất khả thi. Thay vào đó tôi chứng minh **không tồn tại volume `kube-api-access-*`** trong pod spec: không có volume ⇒ không có token file ⇒ không có gì để leo quyền. Đây là bằng chứng **mạnh hơn** `ls`, vì nó chứng minh ở tầng khai báo chứ không phải quan sát một thời điểm.
>
> Quyền hiệu dụng của app service = **0 theo hai lớp độc lập**: (1) không mount token, (2) không có binding nào. Chỉ cần một trong hai đã đủ.

---

## 5. Gap đã biết & rủi ro chấp nhận (khai báo minh bạch)

| # | Mục | Mức | Lý do / hướng xử lý |
|---|---|---|---|
| 1 | Không thêm RBAC Role/RoleBinding cho app service | ⚪ **Quyết định có chủ đích** | Quyền hiệu dụng đã = **0** (không token + không binding). Thêm Role chỉ có thể làm **rộng ra**. Chi tiết + bằng chứng: **§4.1**, ảnh **SS-11**. |
| 2 | SA riêng mới 2/24 service (còn lại dùng SA chung) | ⚪ **Quyết định có chủ đích** | `automount=false` ⇒ SA **không được mount** ⇒ tách SA **không đổi quyền hiệu dụng**. Đổi lại tốn 22 sửa tay + rollout 26 pod. Chi tiết: **§4.1**. |
| 3 | 7 service chưa HA (1 replica) | 🟡 | email, quote, product-reviews, shopping-copilot, llm, accounting, fraud-detection — async/không-thiết-yếu. |
| 4 | Develop không có Karpenter | ⚪ | **Không thuộc yêu cầu mandate** (mandate chỉ đòi trải AZ + giữ SLO). |
| 5 | `apiServerCIDR`/`datastoreEgress.vpcCidr` mở tới VPC CIDR | ⚪ | Rộng hơn "chỉ API server/datastore" nhưng giới hạn ở vài pod tin cậy + đúng cổng. IP ENI xoay nên không hardcode được. |
| 6 | NetworkPolicy `enabled: false` ở **chart default** | ⚪ | **Cố ý.** Bật `true` **chỉ ở values develop** (PR #287). Sandbox auto-sync từ nhánh `develop` nhưng VPC CNI bên đó **chưa** bật `--enable-network-policy`; bật ở chart default sẽ tạo mìn hẹn giờ — 32 policy chưa từng test áp vào cluster không enforce, tới ngày ai đó bật CNI thì mới nổ. Verify: `helm template` với values thật → develop **32** policy, sandbox **0**. |
| 7 | **Uptime 97% khi drain AZ** (5 request lỗi / 67 s) | 🟡 **Gap thật, chưa xử lý** | Không phải pod chết mà là `frontend-proxy` dùng NLB `target-type=ip` với `preStop: sleep 5` + grace 30 s **ngắn hơn** thời gian NLB đánh dấu target unhealthy. Sửa bằng tăng `preStop` / đặt `deregistration_delay` — **cấu hình LB, ngoài phạm vi M17**. Bằng chứng: `R2-04-gap-analysis.txt`. |
| 8 | Mandate 17 **chưa áp dụng cho sandbox** | 🟡 | Chặn bởi điều kiện tiên quyết: VPC CNI sandbox chưa bật `--enable-network-policy`. Bật NetworkPolicy ở đó lúc này là vô nghĩa (policy tồn tại nhưng không được enforce → ảo giác an toàn). Cần `terraform apply` cho sandbox trước. |
| 9 | `product-reviews` còn 1 AZ sau drain | ⚪ | Cố ý không `rollout restart` vì là service team AI (mandate cấm đụng). Tự trải lại ở rollout kế tiếp. |
| 10 | `scraperEgress.infraPorts` mở `:9153` + `:8080` tới **mọi** pod trong `kube-system` | ⚪ **Quyết định có chủ đích** | Đích thật chỉ là CoreDNS và ALB controller, nhưng thêm `podSelector` cho từng cái sẽ khiến values phình và phải sửa mỗi lần đổi hạ tầng. Rủi ro đã bị giới hạn hai lớp: rule **chỉ áp cho pod scraper** (`prometheus`, `otel-collector`), và **chỉ egress**. Đã kiểm chứng pod lạ không lợi dụng được (§3). |
| 11 | `apiServerClusterIP: 172.20.0.1/32` hardcode ở chart default | ⚪ **Đã verify, có rủi ro tồn dư** | Kiểm thật: **cả develop lẫn sandbox đều `172.20.0.1`** → đúng cho hiện tại. Nhưng Terraform **không pin** `service_ipv4_cidr`, để EKS tự chọn; cluster mới có thể ra dải khác (`10.100.0.0/16`). Khi đó chế độ hỏng chính là `kube-state-metrics` CrashLoop khó truy đã mô tả ở §3. **Cách tự kiểm trước khi bật ở env mới:** `kubectl get svc kubernetes -n default -o jsonpath='{.spec.clusterIP}'`. Nên pin `service_ipv4_cidr` ở Terraform để khỏi phụ thuộc mặc định của EKS. |

---

## 6. Checklist nộp

**Bằng chứng đã thu** — 38 log + 14 ảnh trong `logs/` và `screenshots/`:

- [x] **R1** — `R1-00`→`R1-07` + `SS-02` (trang sản phẩm khi `ad` chết), `SS-01c` (Grafana: error 0 req/s toàn bộ cửa sổ)
- [x] **R2** — `R2-00`→`R2-08` + `SS-06` (Grafana cửa sổ drain), `SS-05b`
- [x] **R3** — `R3-00`→`R3-13` + `SS-08` (Grafana khỏe dưới 32 policy), `SS-08b`
- [x] **R4** — `SS-09-automount.txt`, `SS-10-no-token-api-denied.txt`, `SS-11-zero-rbac.txt`
- [x] Baseline đối chứng trước test — `SS-00a/b/c`, `00-baseline-before.txt`

**Đã trả cluster về trạng thái sạch:**

- [x] `uncordon` node `ip-10-60-11-81` sau drain + `rollout restart` để trải lại AZ
- [x] Khôi phục `ad`: HPA dựng lại từ backup + replicas về `2` (`R1-05`)
- [x] Xoá toàn bộ pod thử nghiệm (`m17-attacker`, `m17-probe`, `m17-apitest`) và policy thử nghiệm
- [x] Xác nhận cuối: 4 node Ready, 0 pod không khỏe, storefront HTTP 200 (`99-final-state.txt`)
- [x] **KHÔNG** phải revert ArgoCD — không dùng tới phương án đổi `targetRevision`/pause `develop-root`, vì PR #259 đã merge trước khi test nên nhánh `develop` vốn đã có sẵn thứ cần

**Còn lại (không nằm trong tay người test):**

- [ ] PR #287 được duyệt và merge
- [ ] **Bấm sync ArgoCD** app `develop-techx-corp` — app để **sync thủ công**, merge xong Git chưa tự áp dụng. Chưa sync thì 32 policy trên cluster vẫn là thứ apply bằng tay, Git chưa thành nguồn sự thật.

---

## 7. Ràng buộc mandate đã tuân thủ

- ✅ **Không đụng flagd** — flagd chỉ được thêm allow-rule để tiếp tục hoạt động (ingress :8013, egress giữ nguyên ở develop vì flagd dùng file local).
- ✅ **Không sửa code team AI** — R1 chỉ chạm `src/frontend`; không đụng `aiops/`, `shopping-copilot`, `product-reviews`.
- ✅ **Storefront public, ops private** — `frontend-proxy` có rule public-edge; observability chỉ nhận nội bộ.
- ✅ **Trong ngân sách** — không thêm node/hạ tầng; chỉ +replica cho service nhỏ (~50m CPU) và bật cờ CNI có sẵn.
