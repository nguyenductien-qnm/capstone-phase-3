# Mandate-19 — Throughput Ceiling Load Test (Phase 2 artifacts + handoff)

Test chạy trên **Develop (458)** cluster `ecommerce-develop-dev-eks`, ns `techx-develop`,
rồi mang cấu hình sang **Prod (804)** `ecommerce-dev-eks` ns `techx-tf1`.
Master plan: `loadtest-master-plan.md` (ngoài repo, máy user).

## Files

| File | Vai trò |
|---|---|
| `locustfile-catalog.py` | Catalog (browse) flow — 1 class `CatalogFlowUser`, `LoadTestShape` tự step 5/10/20/40 user (mỗi bậc 240s). |
| `locust-catalog-job.yaml` | K8s Job chạy locustfile trên node ops. CSV → emptyDir `/data`, pod `sleep 3600` sau khi shape xong (đọc CSV được). |

## Cách chạy (Job v2)

```bash
export AWS_PROFILE=sso-develop
CTX=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
kubectl --context "$CTX" apply -f locust-catalog-job.yaml
# đọc kết quả (pod sống sau khi xong nhờ sleep):
JPOD=$(kubectl --context "$CTX" get pod -l app=locust-phase2 -n techx-develop -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$CTX" exec $JPOD -n techx-develop -- cat /data/catalog_stats_history.csv
# CSV cột: 0=ts 1=users 2=type 3=name 4=rps 5=fail/s 11=p50 16=p95 18=p99
# lấy dòng ",Aggregated," CUỐI mỗi user_count (steady state)
kubectl --context "$CTX" delete job locust-phase2 -n techx-develop   # dọn sau khi đọc
```

Song song đọc PromQL (ns `techx-develop`, port-forward `svc/prometheus`):
- CPU/pod: `avg(sum by(pod)(rate(container_cpu_usage_seconds_total{namespace="techx-develop",pod=~"$SVC-.*",container!=""}[2m])))`
- throttle: `sum(rate(container_cpu_cfs_throttled_periods_total{...}[2m])) / sum(rate(container_cpu_cfs_periods_total{...}[2m]))`

## Kết quả BEFORE (frontend limits.cpu = 200m) — điền sau khi Job xong

| Bậc | Users | rps | p50 | p95 | p99 | fail | product-catalog CPU/thr | frontend CPU/thr/rep |
|---|---|---|---|---|---|---|---|---|
| idle | 0 | 0 | — | — | — | 0 | 2m / 0% | ~10m / — / 2 |
| 1 | 5 | _TBD_ | | | | | | |
| 2 | 10 | _TBD_ | | | | | | |
| 3 | 20 | _TBD_ | | | | | | |
| 4 | 40 | _TBD_ | | | | | | |

**Phát hiện sơ bộ (từ lần chạy trước, CSV đã mất nhưng đọc live được):**
- rps tuyến tính theo user (~4.9@10u, ~19@40u). **Latency gãy** ~20-40u: p95 160ms→1300ms, **p99 lên 5.2s**.
- **Nút thắt = `frontend` (Next.js SSR), KHÔNG phải product-catalog.** Ở 40u: frontend throttle **13.7%** (8 rep max), `limits.cpu=200m` bóp cổ; product-catalog nhàn (27m, throttle 0.3%).

## Việc CÒN LẠI cho session sau (Mandate-19 YC2)

> **Quyết định (user 21/07):** chạy **BEFORE và AFTER trong CÙNG một session, liền mạch** — tránh
> cluster drift giữa 2 lần đo, đúng chuẩn so sánh cùng điều kiện. BEFORE ở 2 session trước chỉ đọc
> được số rời rạc (đủ để xác định nút thắt, chưa thành bảng chính thức) vì bị gián đoạn resource.

Thứ tự đúng (một mạch):

1. **Verify cluster sạch + baseline**: không locust resource nào; frontend/product-catalog ở min (đọc
   `deploy .spec.replicas` THẬT, không tin `kubectl get hpa` — status cache stale). Đợi HPA co ≥5min nếu vừa có tải.
2. **Chạy BEFORE** (frontend limits.cpu=200m hiện tại): apply `locust-catalog-job.yaml`, để nó chạy hết
   960s, đọc CSV `/data/catalog_stats_history.csv` → điền bảng BEFORE. **KHÔNG tạo/xóa locust resource
   nào khác trong lúc này** (bài học: tự xóa nhầm phá phép đo). Xóa Job sau khi đọc.
3. **Nâng `frontend.limits.cpu` 200m → 500m** (GIỮ request 100m → HPA target 70% không đổi).
   Chỗ sửa: `platform/charts/application/values.yaml` component `frontend` (~dòng 660-680) hoặc override
   `platform/gitops/environments/develop/values/`. PR vào `develop` theo `.github/pull_request_template.md`,
   Change owner `lken1514`, KHÔNG Co-Authored-By.
4. **Chạy AFTER** (đúng Job này) sau khi merge + ArgoCD sync + frontend rollout (limit 500m) + HPA co ≥5min.
5. **So sánh before/after** = deliverable Mandate-19 YC2: RPS đỉnh giữ SLO tăng, frontend throttle giảm,
   p99 cải thiện, **CÙNG 3 node** (không thêm node — ràng buộc #19).
6. Sau đó: Phase 3 per-pod, Phase 4 mixed, §12 load-shedding Envoy (demo flood flagd), §14 ADR.

## Bài học / bẫy (đừng lặp lại)

- **Điều khiển Locust qua web `/swarm` API mong manh** (405 nếu thiếu `Content-Type`; `user_classes` list bị urlencode sai → spawn 0 user; `--class-picker` treo không bind port). → Dùng **headless + LoadTestShape** như file này, KHÔNG web API.
- **CSV ở `/tmp` mất khi pod chết** → dùng emptyDir `/data` + `sleep` giữ pod (đã làm trong Job này).
- **Node ops chỉ đủ 1 Locust 500m.** Xóa generator cũ trước khi tạo mới, dùng Recreate/Job.
- **Giữa các lần đo phải đợi HPA co về min ≥5 phút** (scaleDown stabilization 300s), nếu không baseline gồm replica dư từ tải trước. `kubectl get hpa` hiển thị rep **stale** — đọc `deploy .spec.replicas` thật.
- **Admission policy dev** enforce `require-resources` + `deny-privilege-escalation` → pod phải có resources + securityContext đầy đủ.
- **frontend-proxy service port = 80** (sau PR #242, target 8080). Locust host = `http://frontend-proxy:80`.
## ⚠️ CHẶN LỚN: actor `locust-loadtest` tự tái tạo

**Trước khi đo BẤT KỲ thứ gì, session sau PHẢI tắt nguồn này.** Một Deployment `locust-loadtest`
+ ConfigMap `locust-full-flow` (locustfile OTel-demo gốc, WebsiteUser full-flow, `LOCUST_USERS=100`,
`RUN_DURATION=15m`, class-picker) **tự tái tạo mỗi ~3-6 phút** bằng `kubectl-client-side-apply`, bắn
tải full-flow (browse+cart+checkout) vào `frontend-proxy:80` → mọi HPA lên max → **không đo catalog
sạch được**.

Đã điều tra hết mọi nguồn TRUY CẬP ĐƯỢC từ máy này (21/07) — **KHÔNG tìm thấy**:
repo (không manifest/script/CI), ArgoCD (không app), CronJob cluster (không), crontab máy (không),
process shell (không), scheduled routine Claude (chỉ session hiện tại), phiên Claude khác (không active).
→ Nguồn ở NGOÀI máy này: **terminal/máy khác của user, hoặc automation ngoài repo chạy `kubectl apply`.**
`manager=kubectl-client-side-apply` xác nhận ai đó apply bằng tay/script, không phải Helm/ArgoCD.

**Việc user cần làm:** tìm & tắt nguồn (tab terminal khác? máy khác cùng kubeconfig? loop/pipeline ngoài?).
Cho tới khi tắt, mỗi lần scale-0/xóa chỉ hiệu lực vài phút rồi nó quay lại.

> Phân biệt: `locust-phase2`/`locust-mandate19` (catalog flow, cm cùng tên) là resource CỦA plan này —
> lần trước Claude tự xóa nhầm chúng khi dọn, gây Job Failed. `locust-loadtest`/`locust-critical-path`
> (full-flow 100u, cm `locust-full-flow`) là actor NGOÀI, khác hẳn. Đừng lẫn hai nhóm.
