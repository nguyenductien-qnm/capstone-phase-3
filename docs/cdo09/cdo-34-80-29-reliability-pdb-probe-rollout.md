# CDO-34 / CDO-80 / CDO-29 — Reliability: PDB + Probes + RollingUpdate (Evidence + ADR)

> **Tasks:**
> - **CDO-34** — PodDisruptionBudget: service sống khi Karpenter thu hồi node.
> - **CDO-80** — readiness/liveness/startup Probe: không route traffic vào pod chưa sẵn sàng.
> - **CDO-29** — Deployment strategy → RollingUpdate: zero-downtime khi đổi cấu hình Envoy/Infra.
>
> **Assignee:** Nguyen Dinh Thi / CDO-09 · **Status Jira:** In Progress
> **Driver:** MANDATE-01 (cắt chuyển mạng/Envoy KHÔNG sập storefront) + MANDATE-02 (chịu tải + Karpenter scale-in/out, giữ SLO zero-downtime).

---

## 1. Đã làm gì (deliverable)

Tất cả quản lý bằng Helm để **ArgoCD tự sync** (GitOps), không apply thủ công. Chart: `platform/charts/application`.

| # | Thành phần | File |
|---|---|---|
| 1 | **PodDisruptionBudget** (`maxUnavailable: 1`) + template `techx-corp.pdb` | `templates/_objects.tpl`, `templates/component.yaml` |
| 2 | **topologySpreadConstraints** (trải pod ra khác node) | `templates/_objects.tpl` (auto selector `opentelemetry.io/name`) |
| 3 | **startupProbe/readinessProbe/livenessProbe** per-service | `templates/_objects.tpl` (thêm block startupProbe + lifecycle) + `values.yaml` |
| 4 | **deploymentStrategy RollingUpdate** `maxUnavailable:0/maxSurge:1` + `preStop` + `terminationGracePeriodSeconds` | `templates/_objects.tpl` + `values.yaml` |
| 5 | **gRPC health tách `liveness`/`readiness`** (Option C — code app) | `techx-corp-platform/src/{checkout/main.go, product-catalog/main.go, cart/src/Program.cs}` |
| 6 | Guard `replicas` theo `.hpa.enabled` + schema | `templates/_objects.tpl`, `values.schema.json` |

**Services có PDB + spread + strategy + probe (storefront-critical):** frontend-proxy, frontend, checkout, cart, product-catalog.
**Services KHÔNG áp** (quyết định có chủ đích): fraud-detection, accounting (consumer Kafka async, ngoài critical path — xem §7).

## 2. Ba ticket — thiết kế & lý do số

### CDO-34 — PodDisruptionBudget + chống co-location
- **`maxUnavailable: 1`** (không `minAvailable`): với replicas thay đổi theo HPA, `maxUnavailable:1` giữ **đúng 1 disruption đồng thời** bất kể scale 2 hay 6 pod → Karpenter luôn drain được từng pod, không deadlock. `minAvailable:1` khi scale cao lại cho hạ tới n-1 pod (quá lỏng); `minAvailable:2` ở 2 replica lại khóa cứng drain (deadlock).
- **`topologySpreadConstraints` (maxSkew:1, hostname, `ScheduleAnyway`)** — BẮT BUỘC: nếu không, Karpenter bin-pack 2 replica lên **cùng 1 node** → node đó consolidate/chết = mất cả 2 pod (đúng INC-2), PDB vô nghĩa. `ScheduleAnyway` (không `DoNotSchedule`) vì cluster chỉ 2 node + budget chặt → tránh pod Pending/kẹt rollout. (Nâng `DoNotSchedule` khi ≥2 node ổn định.)
- **Phụ thuộc CDO-42:** PDB chỉ có nghĩa khi `HPA.minReplicas ≥ 2`. Kien (CDO-42) đã set min=2 cho đúng 5 service này.

### CDO-80 — Probe (Option C: tách gRPC health endpoint)
- **Vấn đề:** OTel image chỉ có 1 gRPC health endpoint trộn trạng thái dependency → nếu liveness & readiness dùng chung, Kafka/Valkey/Postgres giật → **cả hai fail → K8s restart pod hàng loạt (cascade-restart)**.
- **Option C:** sửa code app đăng ký **2 health service riêng**:
  - `liveness` = luôn SERVING khi process sống (độc lập dependency) → dep giật KHÔNG restart.
  - `readiness` = **động**, phản ánh dependency: checkout dial TCP Kafka mỗi 10s, product-catalog ping Postgres mỗi 10s, cart theo flagd flag. Dep mất → NOT_SERVING (kéo khỏi Endpoints) → không restart; dep hồi → SERVING lại.
- **Probe theo bản chất service:** checkout/cart/product-catalog = gRPC (`grpc: {service: liveness/readiness}`); frontend (Next.js) = `httpGet /`; **frontend-proxy (Envoy) = `tcpSocket:8080`** vì `envoy.tmpl.yaml` KHÔNG bật admin → không có `/ready:10000` (đã kiểm), và tcpSocket không đụng file Envoy của member khác + không cần rebuild image.
- **Số probe:** readiness nhạy (period 5s, threshold 3) để kéo pod xấu khỏi LB nhanh; liveness chậm (period 10s, threshold 6 ≈ 60s) để không restart oan; startupProbe threshold cao (24–30) để dung nạp initContainer chờ dependency (≤120–150s).
- **imageOverride.tag `1.1-<svc>`** cho checkout/cart/product-catalog: bump tag để image mới (có 2 health service) + probe mới vào pod **atomic**, tránh CrashLoop do tag cố định `1.0` + `pullPolicy: Always`.

### CDO-29 — Recreate → RollingUpdate (tường minh hoá)
- Repo **không còn `Recreate`** (template không set strategy → đang RollingUpdate mặc định 25/25). CDO-29 = **khai báo tường minh** `maxUnavailable:0/maxSurge:1`.
- **`maxUnavailable:0`** → luôn giữ đủ pod cũ tới khi pod mới vượt readinessProbe → 0 gián đoạn. **`maxSurge:1`** → dư 1 pod, không phình cost (MANDATE-02).
- **`preStop: sleep 5` + `terminationGracePeriodSeconds: 30`** → chống rơi in-flight request do race endpoint-propagation khi pod terminate (đặc biệt quan trọng cho Envoy).
- Envoy config qua **ENV** (không ConfigMap) → đổi config Mandate 01 = đổi env = pod template đổi → RollingUpdate **tự trigger** (không cần checksum/config).

## 3. Guard replicas theo `.hpa.enabled` (thống nhất với CDO-42)

Bỏ flag `hpaManaged` riêng, đổi guard trong `_objects.tpl` sang **`{{- if not (.hpa).enabled }}`** — dùng chung flag của CDO-42 làm nguồn sự thật:
- Mọi service có HPA **tự bỏ `replicas` cứng** → không fight HPA↔ArgoCD (áp dụng cả ad/currency/recommendation).
- Tránh 2 flag trùng khái niệm.

## 4. Evidence (offline + API thật, 2026-07-13)

**Build (đúng toolchain CI qua Docker):**
```
docker build src/checkout/Dockerfile      → OK   (Go)
docker build src/product-catalog/Dockerfile → OK (Go)
docker build src/cart/src/Dockerfile      → OK   (.NET 10)
```

**Helm render:**
```
$ helm lint platform/charts/application
1 chart(s) linted, 0 chart(s) failed
$ helm template ... --api-versions policy/v1
# 5 × PodDisruptionBudget: checkout, cart, product-catalog, frontend, frontend-proxy
# 5 hot-path Deployment: strategy RollingUpdate(0/1) + topologySpread + preStop + probes
# 8 service có HPA đều KHÔNG render replicas (hết fight)
```

**Server-side dry-run trên `ecommerce-dev-eks` (validate với API thật, KHÔNG persist):**
```
$ kubectl apply --dry-run=server -f <app-render>
poddisruptionbudget.policy/{cart,checkout,frontend,frontend-proxy,product-catalog} created (server dry run)
deployment.apps/{cart,checkout,frontend,frontend-proxy,product-catalog} created (server dry run)
# 0 lỗi field — probe grpc/httpGet/tcpSocket, PDB policy/v1, strategy, topologySpread đều hợp lệ
```

**Cluster fact:** 2 node `t3.large`, AZ `us-east-1a` + `us-east-1c` (đủ 2 AZ cho spread), K8s v1.36 (hỗ trợ gRPC probe).

## 5. Kiểm tra runtime & việc còn lại

- [ ] **Build + push image `1.1-<svc>` lên ECR** cho checkout/cart/product-catalog. **BLOCKER:** repo KHÔNG có CI build image (chỉ script thủ công `scripts/build/build-push-images.sh`), và quyền SSO hiện không push ECR. → cần người có quyền build, hoặc mở ticket **CI build image** (gap hạ tầng chung, xem §7).
- [ ] Merge lên `develop` → ArgoCD sync PDB/probe/strategy.
- [ ] Runtime verify: `grpc_health_probe -service=liveness` SERVING kể cả khi Kafka down; `-service=readiness` → NOT_SERVING khi dep down, RESTARTS không tăng (chống cascade-restart). `kubectl get pdb` ALLOWED DISRUPTIONS=1.
- [ ] (Sau) drain node giả lập Karpenter + load-test 200 user → evidence zero-downtime.

## 6. Ranh giới với task khác

- **CDO-42 (Le Trung Kien, HPA/Quota/LimitRange):** PDB của tôi cần `HPA.minReplicas ≥ 2` → Kien đã set min=2 cho 5 service có PDB. Tôi thống nhất dùng flag `hpa.enabled` của Kien để guard replicas (một nguồn sự thật, không 2 flag).
- **MANDATE-01 / Envoy routing (member khác sửa `src/frontend-proxy/envoy.tmpl.yaml`):** tôi KHÔNG đụng file Envoy; probe frontend-proxy dùng `tcpSocket:8080` (độc lập routes). RollingUpdate + preStop của tôi giúp rollout Envoy của họ zero-downtime. Chỉ cần canh thứ tự PR vì cùng block `frontend-proxy` trong values.yaml.
- **CI build image (gap chung):** đổi code app (80a của tôi) HOẶC đổi routes Envoy (Mandate 01) đều cần rebuild image, nhưng repo chưa có CI build image → đề xuất mở ticket hạ tầng.
- **fraud-detection/accounting:** KHÔNG áp PDB/HPA — consumer Kafka async, scale nên theo lag (KEDA) không phải CPU, và ngoài critical path storefront.

---

## ADR-034 — Zero-downtime reliability layer: PDB + split-health probes + controlled RollingUpdate

> Trạng thái: **Đề xuất**
- **Ngày:** 2026-07-13
- **Người ký:** Nguyen Dinh Thi / CDO-09
- **Trụ:** Reliability / Deploy Safety
- **Bối cảnh:** MANDATE-01 (đổi Envoy/network không sập storefront) + MANDATE-02 (Karpenter scale-in/out giữ SLO). Hệ chưa có PDB, probe, strategy tường minh → node bị thu hồi hoặc rollout config có thể gây downtime (INC-2, INC-3).
- **Quyết định:** (1) PDB `maxUnavailable:1` + topologySpread cho 5 storefront-critical service; (2) tách gRPC health `liveness`/`readiness` (Option C) để dependency-flap không cascade-restart, readiness động gate traffic; (3) RollingUpdate `maxUnavailable:0/maxSurge:1` + preStop cho zero-downtime rollout. Guard replicas theo `hpa.enabled` (dùng chung CDO-42).
- **Phương án khác đã cân:** (A) liveness=readiness chung endpoint — loại vì cascade-restart. (B) Option B `tcpSocket` liveness (không sửa code) — giữ làm fallback nếu không build được image, nhưng mất readiness gating theo dependency. (C) `minAvailable` cho PDB — loại vì deadlock drain khi scale. (D) `DoNotSchedule` spread — loại (tạm) vì 2 node dễ Pending.
- **Cost Δ:** Chỉ thêm 5 PDB (object control-plane, miễn phí). Số pod tăng đến từ `HPA.minReplicas=2` (thuộc CDO-42), không phải ticket này. Không thêm dịch vụ trả phí.
- **Ảnh hưởng SLO:** Kỳ vọng giữ zero-downtime khi drain node & rollout Envoy. Verify bằng drain giả lập + load-test (Pha sau).
- **Rollback:** Gỡ `podDisruptionBudget`/`deploymentStrategy`/probe trong values → ArgoCD tự revert; hoặc git revert PR. Kích hoạt nếu probe sai gây NotReady diện rộng, hoặc PDB kẹt drain.
- **Hệ quả:** ✅ Node consolidate không hạ hết instance, rollout config không rơi request, dependency-flap không restart pod. ⚠️ Phụ thuộc image `1.1` được build/push (chưa có CI build image); phụ thuộc `HPA.minReplicas=2` của CDO-42.
