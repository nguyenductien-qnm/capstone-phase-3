# ADR-021: Real zone-level anti-affinity cho luồng ra tiền + observability (Mandate-21)

- **Status:** Accepted (partial — xem "Còn thiếu" bên dưới)
- **Date:** 2026-07-31
- **Owner (ký):** Auzema
- **Deciders:** Task Force CDO (CDO-05)
- **Evidence:** `docs/03_platform/mandate-21/evidence/` (`az-nodes-before.txt`,
  `az-concentration-before.txt`, `az-verdict-before.txt`, `az-concentration-after.txt`,
  `az-verdict-after.txt`, `observability-az-before.txt`)
- **PR:** #520 (`fix/mandate-21-az-topology-spread`)

---

## Context

Mandate-21 yêu cầu luồng ra tiền sống sót khi mất nguyên 1 AZ, dưới tải, không mất dữ liệu, phục
hồi trong RTO cam kết — tiên quyết Mandate-20 (backup/restore) đã đạt. Trước khi làm ADR này, audit
lại toàn bộ 28 mandate cho thấy tầng dữ liệu managed (RDS Multi-AZ, ElastiCache Valkey Multi-AZ,
MSK) đã đúng chuẩn, nhưng **Mandate-21 tự nó (drill AZ-loss + đo RTO/RPO) chưa từng được làm** —
gap lớn nhất trong đợt audit.

Trong lúc kiểm tra hạ tầng để chuẩn bị làm ADR, phát hiện một lớp bug khác đứng trước cả câu chuyện
drill: **cấu hình trải AZ tưởng đã đúng nhưng không thật sự có hiệu lực trên pod đang chạy.**

## Vấn đề phát hiện (live, không phải suy đoán)

Chạy lệnh `kubectl get pods -o wide` join với AZ của node, phát hiện:

1. **`quote` và `email` thiếu hoàn toàn** `podDisruptionBudget` + `topologySpread` trong
   `platform/charts/application/values.yaml` — khác với mọi service luồng ra tiền khác
   (checkout/currency/payment/shipping đều có).
2. **`checkout`, `currency`, `frontend`, `email` đang chạy live với cả 2 replica dồn chung 1 AZ**
   — dù `checkout`/`currency`/`frontend` **đã có** `topologySpreadConstraint` đúng
   (`minDomains: 2`, `whenUnsatisfiable: DoNotSchedule`) trong spec. Nguyên nhân: constraint chỉ
   được scheduler xét **tại thời điểm tạo pod**, dựa trên tập pod đang sống lúc đó — nó không "nhìn
   trước" việc pod cũ (ở AZ khác) sắp bị xoá. Trong một rolling-restart kiểu
   `maxSurge:1/maxUnavailable:0`, cả 2 pod mới có thể lần lượt được tạo trong lúc pod cũ ở AZ khác
   vẫn còn sống (mỗi lần tạo đều "hợp lệ" tại thời điểm đó) — rồi pod cũ bị xoá sau, để lại 2 pod
   mới vô tình chung 1 AZ.
3. **Observability (Jaeger, Grafana, Thanos query/receive/storegateway) chỉ có anti-affinity mức
   `kubernetes.io/hostname`** (khác node, không bắt buộc khác AZ). Chúng đang trải đúng 3 AZ hiện
   tại chỉ vì managed nodegroup `primary` tình cờ có đúng 1 node/1 AZ — trùng hợp cấu trúc, không
   phải rule ép. Riêng **Prometheus đã làm đúng từ trước**
   (`podAntiAffinity: hard` + `podAntiAffinityTopologyKey: topology.kubernetes.io/zone`).

## Decision

**1. Thêm PDB + topologySpread cho `quote`/`email`** (`platform/charts/application/values.yaml`),
khớp pattern các service luồng ra tiền khác:
```yaml
podDisruptionBudget:
  maxUnavailable: 1
topologySpread: true
```

**2. Thêm anti-affinity mức zone cho 5 component observability**
(`platform/gitops/environments/sandbox/values-ops-observability.yaml`), copy đúng cơ chế
Prometheus đã dùng:
- Jaeger, Grafana: thêm entry thứ 2 vào `topologySpreadConstraints` với
  `topologyKey: topology.kubernetes.io/zone`, `minDomains: 2`, `whenUnsatisfiable: DoNotSchedule`.
- Thanos query/receive/storegateway: thêm `podAntiAffinityTopologyKey: topology.kubernetes.io/zone`
  cạnh `podAntiAffinityPreset: hard` đã có sẵn.

**3. Áp live ngay trên cluster trước khi PR merge** (tạo PDB + `kubectl patch` trực tiếp cho
`quote`/`email`), rồi `kubectl rollout restart` 5 deployment (`checkout`, `currency`, `frontend`,
`email`, `quote`) — để lấy bằng chứng before/after thật, không chờ ArgoCD sync.

**4. Xử lý đúng lỗi rolling-restart nêu ở mục 2:** sau restart, `frontend` và `quote` vẫn dồn 1 AZ
(đúng kịch bản đã phân tích). Fix: xoá 1 trong 2 pod đang chung AZ — lúc đó chỉ còn 1 pod neo ở 1
AZ, buộc scheduler đặt pod thay thế vào đúng AZ còn thiếu (vì `minDomains:2` giờ không thể thoả
mãn nếu đặt cùng AZ với pod đang sống). Xác nhận lại: **9/9 service luồng ra tiền trải đúng 2 AZ**
(xem `az-verdict-after.txt`).

**5. Giữ `minDomains: 2`, không nâng lên 3.** Mọi service ở đây chạy đúng 2 replica
(`minReplicas: 2` / `replicaCount: 2`) — không thể trải 2 pod ra 3 AZ (luôn có 1 AZ trống). Với 2
replica ở 2 AZ khác nhau (bất kể cặp nào), mất **bất kỳ 1 trong 3 AZ** chỉ đánh trúng tối đa 1
replica của 1 service — replica còn lại (ở AZ nào cũng được, miễn khác AZ vừa mất) vẫn sống. Đã xác
nhận thực tế: các service không cùng dùng 1 cặp AZ cố định (vd `email` hiện đang ở cặp `1b/1c`
trong khi `checkout/cart/payment/quote` ở cặp `1a/1b`) — không sao, vì đảm bảo là *per-service*, không
phải toàn cụm phải đồng bộ cùng 1 cặp.

## Phương án khác đã cân

- **Nâng `minDomains` lên 3 cho mọi service** — loại, vì vô nghĩa với 2 replica (không đổi kết quả
  scheduling, xem lý luận mục 5) và muốn có tác dụng thật phải tăng lên 3 replica/service, tốn thêm
  node liên tục — mâu thuẫn với Mandate-13/18 (đang cắt chi phí).
- **Ép Karpenter luôn giữ ≥1 node ở cả 3 AZ cho tầng workload (floor cứng)** — loại tạm thời, vì
  Karpenter `NodePool` đã cho phép cả 3 AZ trong `requirements` và **tự động** mở node ở AZ cần thiết
  khi có áp lực tải (xác nhận live: một node spot mới xuất hiện ở `us-east-1c` giữa lúc audit, tự
  Karpenter quyết định) — ép cứng thêm node rảnh 24/7 là chi phí không cần thiết khi cơ chế elastic
  đã tự lo được.
- **Dựa vào sự trùng hợp cấu trúc hiện tại (host-spread = zone-spread nhờ primary nodegroup 1
  node/AZ)** — loại, vì đây chính là gốc rễ bug: không có gì đảm bảo mãi mãi đúng, và độc lập với
  Karpenter (nơi node/AZ thay đổi linh động theo capacity spot).

## Cost Δ

`$0` — không thêm resource nào. Số replica giữ nguyên (2/service); chỉ sửa lại field
`topologySpreadConstraints`/`podAntiAffinityTopologyKey` và thêm 2 object `PodDisruptionBudget`
(miễn phí) cho `quote`/`email`.

## Ảnh hưởng SLO

Rollout restart dùng chiến lược `RollingUpdate` (`maxUnavailable:0`, `maxSurge:1`) sẵn có +
readinessProbe gating (đã chứng minh zero-downtime ở Mandate-3) — không quan sát request khách bị
rớt trong lúc thao tác. Chưa chạy load-test chính thức song song lúc fix (out of scope ADR này, để
lúc drill AZ thật ở mục "Còn thiếu").

## Rollback

Revert 2 commit trên branch `fix/mandate-21-az-topology-spread`
(`b44696db`, `c3c67d05`) / đóng PR #520 mà không merge. Toàn bộ thay đổi là declarative
(Helm values) — ArgoCD re-sync về trạng thái git trước đó sẽ tự phục hồi cấu hình cũ. Các thao tác
`kubectl patch`/`kubectl create pdb` live đã làm trước khi PR merge sẽ bị ArgoCD ghi đè lại đúng
theo git một khi Application sync (không cần rollback tay riêng cho phần live).

## Hệ quả

✅ 9/9 service luồng ra tiền + 5/6 component observability (trừ Prometheus vốn đã đúng, trừ
compactor 1-replica không cần) giờ có đảm bảo zone-level thật, không còn dựa may rủi lịch schedule.
✅ Phát hiện thêm: Karpenter `NodePool` đã cho phép cả 3 AZ, tự mở node theo nhu cầu — không cần ép
cứng floor 3-AZ tốn kém.
⚠️ Phân bố AZ cụ thể (cặp nào dùng cặp nào) là **động**, đổi theo capacity spot tại từng thời điểm —
ADR này không cố định layout, chỉ đảm bảo tính chất "2 replica của 1 service không bao giờ chung 1
AZ".

## Còn thiếu (chưa xong, ngoài phạm vi ADR này)

- **Chưa merge PR #520** — cluster live đã đúng nhờ patch thủ công trước, nhưng git/ArgoCD cần
  merge để tránh drift nếu Application tự sync lại từ `develop`.
- **Chưa đo RTO/RPO cho drill mất nguyên 1 AZ thật, dưới tải, do mentor chủ động gây ra bất chợt**
  — đây là phần lõi còn lại của Mandate-21, ADR này chỉ giải quyết phần nền tảng (đảm bảo pod thật
  sự trải AZ) để drill có ý nghĩa.
- **Chưa load-test song song lúc fix** để có số liệu SLO trong lúc thao tác (chỉ quan sát định
  tính qua `kubectl rollout status` + readinessProbe).
