# Mandate 13 — Evidence Index (Sandbox)

> Bằng chứng thật, thu thập **2026-07-28 & 2026-07-30** trên cluster sandbox (cluster `ecommerce-dev-eks`, namespace `techx-tf1`).

## Bảng Evidence

| # | Yêu cầu Directive | Kết quả | File / Bằng chứng |
|---|---|---|---|
| 1 | **#1** Spot ratio (Karpenter-managed) | ✅ **63.9%** (2300m/3600m CPU requests) — chi tiết §1 | Video Live / CPU breakdown |
| 2 | **#2** Cost Explorer — Spot vs On-Demand | ✅ Spot 63.91h/$0.21, On-Demand 151.77h/$5.00 — ảnh §1 | [`screenshots/after-cost-explorer-usage.png`](screenshots/after-cost-explorer-usage.png) |
| 3 | **#2,#5** Node-hours giảm ≥30% | ❌ **KHÔNG ĐẠT** — 0% chênh lệch trên pool `default` qua 2 lần load test thật (28-07 đỉnh 450u, 30-07 đỉnh 700u sau khi nới `maxReplicas`) | Xem ADR §"Đo lường thực tế (30-07-2026)" |
| 4 | **#2** Karpenter tự consolidate node underutilized | ✅ 1 sự kiện thật (Underutilized→delete) trên pool `spot`, ~6 phút (30-07) | Karpenter event log 30-07 |
| 5 | **#3** Live spot-kill — 0 request rớt | ✅ Node mới trong ~34s, pod Running trong ~118s, 0 pod Error/CrashLoop | Test live spot-kill |
| 6 | **#3** Karpenter interruption-queue log | ✅ Interrupt → CordonAndDrain <1s → node mới registered 22-24s | Event log |
| 7 | **#1,#5** `kubectl get nodes`/`nodeclaims` | ✅ Snapshot 2026-07-28T04:32 UTC | `kubectl get nodes` |
| 8 | **#5** Graviton (arm64) | ❌ **Deferred có chủ ý** — CI hiện chỉ build `linux/amd64` — xem ADR Decision 4 | ADR §"Quyết định (Develop)" mục 4 |

## 🔗 Link Video Live Chứng Minh Bằng Chứng (Google Drive)

- **Link Video Live (Mandate 13 — Evidence #1 & #2)**: 
  - [Google Drive Live Video Demonstration](https://drive.google.com/file/d/1bGhNfVVV_SvJ6HbTT46vecP1LDFvSLzH/view?usp=sharing)

---

## 1. Yêu cầu #1 — Spot Ratio (> 50% Compute trên Spot Capacity) [Đã chứng minh qua Video Live]

> **Trạng thái**: ✅ **ĐẠT CHUẨN** (Đạt **63.9%** compute trên Spot nodes)  
> **Video chứng minh**: [Live Video Demo](https://drive.google.com/file/d/1bGhNfVVV_SvJ6HbTT46vecP1LDFvSLzH/view?usp=sharing)

### Chi tiết bằng chứng thu thập từ Video & Cluster:

1. **Phân bổ Compute theo CPU Requests (`techx-tf1`)**:
   - **Spot Capacity (Karpenter Spot Pool)**: **2300m CPU requests** (**63.9%**)
   - **On-Demand Capacity (Karpenter Default Pool)**: 1300m CPU requests (36.1%)
   - **MNG Baseline Floor (Cố định cho system/control plane)**: 1115m CPU requests (Không thể chuyển sang Spot)
   - **Tổng Karpenter Compute**: 3600m CPU requests → **Spot chiếm 63.9% (Vượt chỉ tiêu > 50%)**.

2. **Danh sách 10 Services đã Opt-in chạy trên Spot**:
   - `accounting` · `ad` · `cart-consumer-worker` · `email` · `fraud-detection` · `image-provider` · `llm` · `ml-guard` · `product-reviews` · `recommendation`.
   - Tất cả 10 service này đều có cấu hình an toàn: `PDB maxUnavailable=1` + `replicas ≥ 2` + `preStop sleep 5s` / `terminationGracePeriodSeconds: 30`.

3. **Bằng chứng từ AWS Cost Explorer**:
   - Usage Quantity (EC2 Running Hours): **Spot 63.91 hours ($0.21)** vs **On-Demand 151.77 hours ($5.00)**.
   - Ảnh minh họa Cost Explorer:

![AWS Cost Explorer — Usage Quantity by Purchase Option](screenshots/after-cost-explorer-usage.png)

---

## 2. Yêu cầu #2 — Elastic Compute, Node-Hours Scale Down (≥ 30%) & Co xuống thật lúc tải giảm

> **Trạng thái Node-level Pay per Demand**: ✅ ĐẠT ở mức pod (HPA scale đúng tải) — ❌ KHÔNG ĐẠT ở mức node trên pool `default`
> **Trạng thái Node-Hours Savings**: ❌ **KHÔNG ĐẠT** (0% chênh lệch trên pool `default`)
> **Trạng thái Co xuống thật lúc tải giảm**: 🟡 Có xảy ra trên pool `spot` (~6 phút), không có trên pool `default`

### 2.1 Diễn biến thực tế (load test 30-07-2026, 07:00–09:01 UTC, đỉnh 700 user qua Locust Web UI)

| Thời điểm (UTC) | Node tổng | Node pool `default` | Node pool `spot` | HPA `frontend` |
|---|---|---|---|---|
| 07:00 (baseline) | 7 | 2 | 2 | 2 replica |
| 07:41 | 8 | 2 | 3 (+1 launch) | 4 replica, 116%/70% |
| 07:47 | 7 | 2 | 2 (Karpenter tự consolidate: Underutilized→delete) | — |
| 08:01 | 7 | 2 | 2 | **20/20 replica (kịch trần), vẫn 74%/70%** |
| 09:01 (về baseline) | 7 | 2 | 2 | 3 replica |

**Kết quả:** pool `default` (money-path: frontend/cart/checkout/currency/quote/shipping/payment/product-catalog) giữ nguyên 2 node trong suốt bài test, kể cả khi `frontend` đạt tuyệt đối trần `maxReplicas` mới (20). Tổng CPU request tại đỉnh (~2.9 vCPU) vẫn dưới capacity 2-node (3.86 vCPU) vì các service còn lại (checkout/payment/quote/shipping/currency/product-catalog) chưa vượt 70% utilization ở mức 700 user để tự sinh thêm replica — ước tính cần ~2500+ user đồng thời mới đủ. Pool `spot` có 1 chu kỳ launch→consolidate thật (~6 phút) nhưng quá ngắn để đại diện cho node-hours.

**Kết luận Yêu cầu #2:** Node-hours **KHÔNG ĐẠT** yêu cầu ≥30% của Directive #13. Nguyên nhân: CPU-request sizing hiện tại quá nhỏ so với capacity node, kết hợp task-weight distribution trong locustfile khiến checkout-family khó tự scale. Chi tiết + hướng khắc phục còn lại: ADR §"Đo lường thực tế (30-07-2026)".

---

## 3. Yêu cầu #3 — Sống sót Spot Interruption (0 request rớt)

> **Trạng thái**: ✅ **ĐẠT CHUẨN** — 0 pod Error/CrashLoop, PDB giữ đúng `maxUnavailable=1`

`aws ec2 terminate-instances` trên 1 spot node đang chạy pod của luồng browse→cart→checkout. Karpenter (qua interruption queue SQS + EventBridge) phát hiện, cordon+drain, và launch node thay thế; toàn bộ pod reschedule thành công, không pod nào rơi vào Error/CrashLoop. 17 service trên luồng browse→cart→checkout đều có PDB `maxUnavailable=1` áp dụng đúng lúc kill.

---

## 4. Yêu cầu #4 — Đủ tín hiệu cho Scheduler (request "vừa đủ")

> **Trạng thái**: ✅ **ĐẠT CHUẨN** — Đã đạt từ trước, không đổi ở Mandate-13

Right-sizing request/limit cho HPA/autoscaler đã thực hiện ở Mandate-19 — Mandate-13 kế thừa cấu hình này. HPA scale đúng theo tải, xác nhận tín hiệu request hiện tại đủ để scheduler quyết định đúng.

---

## 5. Tổng hợp theo "Cách đo & nộp" (3 màn hình console)

| Màn hình | Yêu cầu directive | Trạng thái |
|---|---|---|
| ① EC2 → Instances (Lifecycle + Instance type + Architecture) | Video live cho thấy node spot/on-demand, x86/arm64 | ✅ Đã chứng minh qua [Video Live](https://drive.google.com/file/d/1bGhNfVVV_SvJ6HbTT46vecP1LDFvSLzH/view?usp=sharing) |
| ② Cost Explorer → Usage Quantity (Purchase Option, Instance Type, Daily/Hourly) | Spot vs On-Demand, giờ-node tụt lúc tải thấp | ✅ Screenshot có — [`after-cost-explorer-usage.png`](screenshots/after-cost-explorer-usage.png) (Spot 63.91h/$0.21 vs On-Demand 151.77h/$5.00) |
| ③ Grafana (node count + SLO panel) live trong lúc chạy load-curve | Node theo tải, checkout ≥99% / browse-cart ≥99.5% / p95<1s | ✅ Đã ghi nhận qua Video Live |

## Kết luận tổng thể

| Yêu cầu Directive | Trạng thái |
|---|---|
| #1 Spot > 50% | ✅ **ĐẠT** (63.9% CPU requests) |
| #2 Trả tiền theo demand — pod-level | ✅ **ĐẠT** (HPA scale đúng tải) |
| #2 Trả tiền theo demand — node-level | ❌ **KHÔNG ĐẠT** trên pool `default`; pool `spot` có 1 chu kỳ scale thật nhưng ngắn (~6 phút) |
| #3 Sống sót spot interruption | ✅ **ĐẠT** (0 request rớt, pod reschedule trong ~118s) |
| #4 Tín hiệu cho scheduler | ✅ **ĐẠT** (kế thừa Mandate-19) |
| #5 Node-hours ≥30% | ❌ **KHÔNG ĐẠT** (0% chênh lệch trên pool `default`) |
| #5 Spot ≥50% | ✅ **ĐẠT** (63.9%) |
| #5 Graviton | ❌ Deferred có chủ ý (CI build `linux/amd64`) |
| #5 Co xuống thật lúc tải giảm | 🟡 Có thật trên pool `spot`, không có trên pool `default` |
| #5 SLO giữ | ✅ **ĐẠT** (0 downtime / 0 request rớt trên luồng checkout) |

**Kết luận:** Directive #13 đạt các tiêu chí Spot >50%, sống sót spot interruption, tín hiệu scheduler, và SLO. **Chưa đạt tiêu chí node-hours ≥30%** — giới hạn kiến trúc thật (CPU-request sizing so với capacity node + task-weight distribution trong locustfile). Chi tiết + hướng khắc phục: ADR §"Đo lường thực tế (30-07-2026)".

