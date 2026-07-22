# Mandate-19 — Evidence checklist (chụp cho mentor)

> Map đúng phần **"Phải nộp"** của Directive #19. Mỗi mục ghi rõ: **chụp gì**, **ở đâu**,
> **số đã đo để đối chiếu**. Screenshot cần bạn thao tác (Grafana/Locust UI). Số đã có trong
> `README.md`; file này chỉ nói **ảnh nào cần chụp**.

Cụm: develop `ecommerce-develop-dev-eks`, ns `techx-develop`. Grafana đã port-forward `localhost:3000`.

---

## E1 — RPS đỉnh giữ SLO: TRƯỚC (deliverable "before")

**Chụp:** Grafana panel **CPU throttle của frontend** trong lúc chạy BEFORE (limit 200m), ở bậc 40u.
- Grafana → Explore → dán:
  ```
  sum(rate(container_cpu_cfs_throttled_periods_total{namespace="techx-develop",pod=~"frontend-.*"}[2m]))
  / sum(rate(container_cpu_cfs_periods_total{namespace="techx-develop",pod=~"frontend-.*"}[2m]))
  ```
- **Số đối chiếu:** @40u throttle **9.3%**, p99 341ms, p100 810ms, frontend kịch 6 replica.
- ⚠️ BEFORE đã đo xong (limit giờ là 500m). Muốn chụp lại throttle cao phải xem **lịch sử** trong
  Grafana (time range về ~02:35–02:51 UTC 21/07) hoặc chấp nhận dùng bảng số trong README.

## E2 — RPS đỉnh giữ SLO: SAU (deliverable "after, đã nâng trần")

**Chụp:** cùng panel throttle, time range AFTER (~03:20–03:37 UTC 21/07).
- **Số đối chiếu:** @40u throttle **2.1%** (↓4.4×), p99 122ms (↓2.8×), p100 260ms (↓3.1×), rps giữ 19.8→19.9.
- **Ảnh mạnh nhất:** đặt 2 panel throttle BEFORE vs AFTER cạnh nhau (cùng trục) → thấy rõ sập throttle.

## E3 — requests-per-node tăng, NODE KHÔNG ĐỔI (ràng buộc cốt lõi)

**Chụp 2 thứ:**
1. **Terminal** `kubectl get nodes` — đầu bài và cuối bài, đều **3 primary + 1 ops**:
   ```
   kubectl get nodes -L eks.amazonaws.com/nodegroup
   ```
   → 3 node `...-primary-...` + 1 node `...-ops`. Số này KHÔNG đổi suốt mọi phép đo = bằng chứng
   "nâng trần bằng hiệu suất, không thêm node".
2. **Grafana "Kubernetes Scaling - Pods & Nodes"** dashboard — lúc loadtest: đường **pod frontend
   scale 2→6**, đường **node count phẳng = 3**. Đây là ảnh "một khung hình nói hết".

- **Số đối chiếu:** density = RPS phục vụ / node. AFTER giữ SLO ở ~120rps trần hệ (20rps/pod × 6) trên
  cùng 3 node → requests-per-node tăng vì mỗi pod hết bị throttle, không phải vì thêm node.

## E4 — Nút thắt thông lượng đã tìm & nới (deliverable "1 bottleneck")

**Chụp:** Grafana panel CPU/pod của **frontend vs product-catalog** cùng lúc (Phase 3, 1 pod frontend).
- **Số đối chiếu (Phase 3, frontend ghim 1 pod):**
  - Bậc gãy SLO = 80u: p95 226ms, nhưng frontend CPU chỉ **83m/500m (17%), throttle 5.2%** → pod
    CHƯA chạm limit. Nút thắt = **concurrency Next.js SSR** (đơn event loop), KHÔNG phải CPU.
  - product-catalog throttle **0%** suốt — không phải nút thắt.
  - **RPS_per_pod_at_SLO ≈ 20 rps/pod.**
- **Cách nới:** scale-out pod (HPA), + limit 500m để hạ tail throttle. (Chi tiết README mục Phase 3.)

## E5 — Demo xuống mềm (deliverable "load-shedding, checkout được bảo vệ, không sập")

**Chụp — ảnh đắt nhất cho YC4:**
1. **Locust log/UI** bảng kết quả demo: browse fail ~70% (429) vs cart 0% fail. Từ CSV:
   ```
   kubectl exec <locust-pod> -- cat /data/shed_failures.csv
   ```
2. **failures.csv** dòng: `429 Too Many Requests × 45372` cho browse → chứng minh **shed đúng**,
   không phải lỗi hệ thống.
- **Số đối chiếu (demo 631 rps, 120s):**

  | Route | reqs | 429 shed | % | Kết luận |
  |---|---|---|---|---|
  | browse `/api/products` | 64448 | 45378 | **70.4%** | shed phần vượt bucket 80rps |
  | cart (checkout-path) | 10803 | **0** | **0%** | ưu tiên tuyệt đối, qua hết |

- **Điểm nhấn kể mentor:** tách route `/api/checkout`+`/api/cart` lên trên catch-all (không rate-limit),
  chỉ shed `/api/products`+`/`. Hệ KHÔNG sập — vẫn phục vụ, chỉ từ chối browse dư.

## ⚠️ Lỗi hạ tầng có sẵn phát hiện khi test (không do loadtest, cần fix riêng)

- **product-reviews CrashLoopBackOff** (18 restart/73min) → `/api/product-reviews/:id` trả **500**.
  Nguyên nhân: **protobuf version mismatch** (gencode 7.35.0 vs runtime 5.29.6) — lỗi build image
  Python, KHÔNG liên quan throughput/tải. Trong mixed test flow reviews fail 100% vì lý do này.
  → Loại reviews khỏi số concurrency Phase 4. **Cần fix build image product-reviews riêng** (bump
  protobuf runtime hoặc regenerate gencode). Directive #19 nhấn "độ tin cậy" → đây là 1 điểm cần vá.

## E7 — Nút thắt checkout chain + HPA checkout-path (before/after thứ hai)

**Chụp:** panel throttle của email/quote/shipping/payment quanh các mốc đo 21/07 (09:07 trước,
09:39 sau khi nới limit, và sau khi thêm HPA).
- **Số đối chiếu (nới limit chain):** email throttle **95.7% → 6.7%** (100m→400m), payment
  34.2%→4.6%, currency 29.1%→8.6%. Trần checkout SLO<1s: **~27 rps → ~76 rps (2.8×)**.
- **Số đối chiếu (thêm HPA min2/max4 cho email/quote/shipping/payment):** email throttle
  **43% → 2.1%**, quote 58%→8%, shipping →0.4% — trước đó cả 4 service kẹt 1 replica, không HPA.
- Bảng chi tiết trong README mục "Checkout flow" và "Sizing SAU-SHED".

## E8 — Trần user-facing qua NLB + flood test hệ đã tuning

- **Trần user-facing (EC2 c6i.2xlarge ngoài cụm bắn qua NLB, 21/07):** **98 rps @200u** giữ SLO
  (checkout p99 970ms <1s, fail 0%), gãy ở 280u (frontend throttle 9.4%, payment 8.8%), node giữ 4,
  baseline mạng 1u = 16ms. Chi tiết README mục PHASE 6.5 (EC2 đã terminate — bằng chứng là số liệu
  đã ghi, không chụp lại được).
- **Flood test YC4 trên hệ đã tuning (cờ flagd thật):** checkout SLI **100%** khi flood, node giữ
  4, frontend scale 2→10 hấp thụ. Verify shed bắn thẳng pod IP: GET / shed 41%, /api/products 53%.
  Chi tiết: `flood-test-tuned-system.md`, `shed-verification-clusterip-vs-podip.md`.

## E6 — ADR ký tên (deliverable #6)

**Nộp:** file ADR trong repo (`docs/mandate-19/ADR-mandate19-throughput-ceiling.md`) — trần cũ/mới,
nút thắt ở đâu, nâng bằng gì, cơ chế load-shedding, ký tên `lken1514`. ✅ Đã viết, kèm cập nhật 22/07.

---

## Phụ: lệnh chụp nhanh trạng thái cluster (terminal evidence)

```bash
export AWS_PROFILE=sso-develop
CTX=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
# node không đổi
kubectl --context "$CTX" get nodes -L eks.amazonaws.com/nodegroup
# HPA trạng thái (sau PR sizing: frontend 2/10, email/quote/shipping/payment 2/4, target 70%)
kubectl --context "$CTX" get hpa -n techx-develop
# frontend limit 500m (đã nâng)
kubectl --context "$CTX" get deploy frontend -n techx-develop \
  -o jsonpath='{.spec.template.spec.containers[0].resources}'
```
