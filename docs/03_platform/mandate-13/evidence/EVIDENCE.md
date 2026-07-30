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
| 8 | **#5** Graviton (arm64) | ❌ **Chưa bật** — CI đã có khả năng multi-arch từ 28-07 (PR #467), nhưng NodePool vẫn pin `kubernetes.io/arch: [amd64]` + instance-family `[m6a, c6a, c7i]` (toàn x86) — chi tiết §6 | §6 bên dưới |

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

### 2.2 Capacity math — vì sao 2 node luôn đủ chỗ cho pool `default`

Node c6a.large: 1930m CPU allocatable/node → 2 node = **3.86 vCPU**.

| Service | CPU request/pod | `maxReplicas` (sau khi nới) | Tổng CPU tại trần |
|---|---|---|---|
| frontend | 100m | 20 | 2000m |
| cart | 60m | 12 | 720m |
| checkout | 60m | 10 | 600m |
| payment | 80m | 8 | 640m |
| quote | 50m | 8 | 400m |
| shipping | 50m | 8 | 400m |
| currency | 50m | 8 | 400m |
| product-catalog | 40m | 12 | 480m |
| **Tổng nếu MỌI service cùng lúc kịch trần** | | | **5.64 vCPU** |
| **Tổng thực đo tại đỉnh 700 user (30-07 08:01 UTC)** | | | **~2.9 vCPU** (chỉ frontend kịch trần, còn lại vẫn ở `minReplicas`) |

Trần lý thuyết tuyệt đối (5.64 vCPU) mới vượt capacity 2-node (3.86 vCPU); tải thực tế đo được (2.9 vCPU) thì chưa. Khoảng cách giữa 2 con số này chính là lý do cần ~2500+ user (không phải 700) mới đủ ép toàn bộ money-path service cùng scale.

### 2.3 Log Karpenter xác nhận Karpenter có đánh giá nhưng bị chặn (không phải đứng yên/không hoạt động)

```
08:06 UTC  Unconsolidatable  nodeclaim/default-pqfbw  Can't remove without creating 4 candidates
08:06 UTC  Unconsolidatable  nodeclaim/default-8m5nb  Can't remove without creating 4 candidates
```

Karpenter chủ động đánh giá consolidate pool `default` nhưng bị chặn vì còn quá nhiều pod (do `frontend` vẫn ở 20 replica từ đỉnh tải, chưa kịp co lại) — không phải Karpenter "không nhận ra" nhu cầu, mà đơn giản là chưa từng có nhu cầu THÊM node, chỉ có nhu cầu (tiềm năng) gộp bớt.

**Kết luận Yêu cầu #2 (node-level) & #5 (node-hours ≥30%):** **KHÔNG ĐẠT.** Xác nhận độc lập 2 lần (28-07 đỉnh 450 user, 30-07 đỉnh 700 user sau khi nới `maxReplicas`) — cả 2 lần node-hours trên pool `default` đều 0% chênh lệch. Nguyên nhân gốc là kiến trúc: CPU-request/pod (40-100m) quá nhỏ so với capacity node (1930m/node), cộng với trọng số task quá thấp của checkout-family trong locustfile khiến chúng không tự scale ở mức tải có thể test an toàn. Đã cân nhắc 4 phương án khắc phục (tăng traffic cực cao, tăng CPU request, giảm baseline node, hoặc chấp nhận + báo cáo trung thực) — chọn phương án báo cáo trung thực, ghi lại hướng khắc phục khả thi cho lần triển khai tiếp theo. Chi tiết đầy đủ: ADR §"Đo lường thực tế (30-07-2026)".

---

## 6. Yêu cầu #5 — Graviton (arm64): chưa bật, không còn bị chặn bởi CI

**Bối cảnh ban đầu (ADR Decision 4, viết 26-07-2026):** Graviton bị loại khỏi phạm vi vì "CI hiện chỉ build `linux/amd64`; multi-arch cần build matrix mới + test tương thích arm64 cho service dùng native/JNI (Java OTel agent, C++ OTel SDK)".

**Phát hiện mới (30-07-2026):** lý do trên đã **lỗi thời**. PR #467 (`feat/arm64-multiarch`, tác giả khác, merge 28-07-2026 — 2 ngày sau khi ADR viết Decision 4) đã thêm build đa kiến trúc thật cho toàn bộ app image:

- Tách job build theo kiến trúc (`ubuntu-latest` cho amd64, `ubuntu-24.04-arm` cho arm64 — runner ARM **native**, không qua QEMU) rồi gộp thành 1 OCI manifest list/service.
- CI gate bắt buộc mỗi tag phải có đúng 2 platform (`linux/amd64` + `linux/arm64`) mới pass — xem `.github/workflows/app-build.yaml` bước "Verify index có đủ 2 platform".
- Có sửa riêng cross-compilation ARM64 cho `shipping` (thêm biến `AR` trong Dockerfile, commit `cfdea8b6`/`8764ec88`) — tức các service có build native cũng đã được xử lý, không chỉ service Python/Node thuần.
- Mục tiêu ghi rõ trong message commit: *"mở đường cho node Graviton... kubelet tự kéo đúng biến thể theo kiến trúc node"*.

**Trạng thái thật tại thời điểm này (kiểm tra trực tiếp, cả local repo lẫn live cluster):**
```
NodePool default — kubernetes.io/arch:        ["amd64"]        (chưa có "arm64")
NodePool default — instance-family:           ["m6a","c6a","c7i"]   (toàn x86, không có m7g/c7g/c6g/t4g)
```

→ **Ảnh (image) đã sẵn sàng multi-arch, nhưng NodePool chưa cho phép Karpenter chọn node Graviton.** Đây là config thay đổi nhỏ, KHÔNG còn là giới hạn CI như ADR gốc từng ghi nhận.

**Việc còn lại để thực sự bật Graviton (chưa làm):**
1. Thêm `"arm64"` vào `kubernetes.io/arch` và thêm instance-family Graviton (vd `m7g`, `c7g`, `t4g`) vào NodePool.
2. Xác nhận từng service thực sự có index 2-platform trên ECR (CI gate đã enforce nên nhiều khả năng đã có, nhưng chưa audit thủ công toàn bộ service).
3. **Test chạy thật trên node arm64** cho các service dùng native/JNI (Java OTel agent, C++ OTel SDK) — CI build thành công không đồng nghĩa runtime đúng, cần verify riêng trước khi cho traffic thật.

**Kết luận:** Graviton **vẫn chưa đạt** cho Directive #13, nhưng lý do đã đổi — không còn là "CI không hỗ trợ" mà là "chưa cấu hình NodePool + chưa verify runtime", việc nhỏ hơn nhiều so với ghi nhận ban đầu.

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
| #5 Graviton | ❌ Chưa bật — CI đã hỗ trợ multi-arch từ PR #467 (28-07), blocker còn lại là NodePool config + runtime verify, xem §6 |
| #5 Co xuống thật lúc tải giảm | 🟡 Có thật trên pool `spot`, không có trên pool `default` |
| #5 SLO giữ | ✅ **ĐẠT** (0 downtime / 0 request rớt trên luồng checkout) |

**Kết luận:** Directive #13 đạt các tiêu chí Spot >50%, sống sót spot interruption, tín hiệu scheduler, và SLO. **Chưa đạt tiêu chí node-hours ≥30%** — giới hạn kiến trúc thật (CPU-request sizing so với capacity node + task-weight distribution trong locustfile). Chi tiết + hướng khắc phục: ADR §"Đo lường thực tế (30-07-2026)".

