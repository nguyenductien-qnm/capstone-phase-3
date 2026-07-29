# CDO-79 — Audit hiện trạng Deploy Safety (Probe / PDB / Strategy / Graceful)

> **Owner:** Nguyen Dinh Thi · **Ngày:** 2026-07-14 · **Mandate-03**
> Mục tiêu: quét toàn bộ Helm values / template, lập ma trận hiện trạng để xác định gap thật, feed vào CDO-80/81/29/34. Tránh làm lại việc đã có.
> Nguồn: `platform/charts/application/values.yaml`, `platform/charts/application/templates/_objects.tpl`.

## 1. Ma trận service × deploy-safety

| Service | Critical path | Readiness | Liveness | Startup | PDB | Deploy strategy | preStop + grace | Replica/HPA | Ref `values.yaml` |
|---|---|:---:|:---:|:---:|:---:|---|:---:|---|---|
| frontend-proxy (Envoy edge) | ✅ cửa ngõ | ✅ tcp:8080 | ✅ tcp | – | ✅ maxUnavail=1 | RollingUpdate 0/1 | ✅ 5s/30s | HPA 2–6 | 655-666 |
| frontend | ✅ browse | ✅ http `/` | ✅ | ✅ http | ✅ | RollingUpdate 0/1 | ✅ | HPA 2–6 | 561-572 |
| checkout | ✅ ra tiền | ✅ grpc | ✅ grpc | ✅ ~150s | ✅ | RollingUpdate 0/1 | ✅ | HPA 2–5 | 385-411 |
| cart | ✅ | ✅ grpc | ✅ grpc | ✅ | ✅ | RollingUpdate 0/1 | ✅ | HPA 2–6 | 310-336 |
| product-catalog | ✅ browse | ✅ grpc | ✅ grpc | ✅ ~120s | ✅ | RollingUpdate 0/1 | ✅ | HPA 2–6 | 852-878 |
| currency / recommendation / ad | phụ | ❌ | ❌ | ❌ | ❌ | default | ❌ | HPA 1–4 | – |
| shipping / quote / email / payment | phụ | ❌ | ❌ | ❌ | ❌ | default | ❌ | 1 | – |
| accounting / fraud-detection | async (Kafka) | ❌ | ❌ | ❌ | ❌ (chủ ý) | default | ❌ | 1 | – |
| valkey-cart | state giỏ | in-cluster `enabled:false` (1272) → **ElastiCache HA** (2 node/2 AZ, auto-failover — xem ADR-REL-004) | | | | | | | – |

Template `_objects.tpl` render đầy đủ: `strategy` (17-20), `terminationGracePeriodSeconds` (42-44), `topologySpreadConstraints` (45-53), `lifecycle/preStop` (91-94), `startup/liveness/readinessProbe` (95-106), `techx-corp.pdb` (341-356).

## 2. Kết luận & gap

- **Critical path (5 service):** đã có ĐỦ readiness/liveness/startup + PDB + RollingUpdate(0/1) + preStop/grace + topologySpread. **Không còn gap config.** → CDO-80/81/29/34 chỉ cần **verify runtime**, không code lại.
- **Service phụ:** không probe/PDB — chấp nhận (ngoài luồng ra tiền, gián đoạn ngắn không breach SLO). accounting/fraud async → gián đoạn được Kafka đệm.
- **SPOF:** không còn `Recreate` nào trên critical path. valkey SPOF đã chuyển sang ElastiCache HA (ADR-REL-004).
- **Gap thật còn lại (ngoài phạm vi "config service"):**
  1. Không có SLO dashboard → **CDO-27** (đã dựng `grafana/provisioning/dashboards/slo-dashboard.json`).
  2. Chưa verify E2E + evidence → **CDO-83**.
  3. topologySpread cũ dùng `ScheduleAnyway` (soft) → 2 pod có thể chụm 1 node → đã siết `DoNotSchedule` (CDO-34, `_objects.tpl:49`).

## 3. Bằng chứng runtime (14/07/2026, cluster `ecommerce-dev-eks`, ns `techx-tf1`)

- 3 node Ready (3 AZ).
- Endpoints critical service loại pod NotReady (readiness hoạt động).
- checkout success 100%, frontend p95 76ms — SLO baseline khỏe trước khi test.
