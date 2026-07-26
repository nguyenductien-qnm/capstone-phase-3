# Mandate 13 — Hướng dẫn nộp bài cho Mentor (Submission Guide)

> **Directive:** [`mandates/MANDATE-13-cost-efficiency-elastic.md`](../../../../mandates/MANDATE-13-cost-efficiency-elastic.md)
> **Branch:** `feat/mandate-13-cost-efficiency-elastic`
> **Cluster:** `ecommerce-develop-dev-eks` (account `458580846647`)
> **ADR:** [`ADR-mandate13-cost-efficiency-elastic.md`](ADR-mandate13-cost-efficiency-elastic.md)
> **Hướng dẫn thực thi (apply + test):** [`EXECUTION-GUIDE.md`](EXECUTION-GUIDE.md)

---

## Mục lục

1. [Tổng quan — Mentor cần xem gì?](#1-tổng-quan--mentor-cần-xem-gì)
2. [Danh sách các thứ phải nộp (Deliverables)](#2-danh-sách-các-thứ-phải-nộp-deliverables)
3. [Thứ tự thực thi — Checklist 8 Phase](#3-thứ-tự-thực-thi--checklist-8-phase)
4. [Hướng dẫn quay video Console](#4-hướng-dẫn-quay-video-console)
5. [Hướng dẫn quay video Grafana Live](#5-hướng-dẫn-quay-video-grafana-live)
6. [Live Spot-Kill — Script chạy từng bước](#6-live-spot-kill--script-chạy-từng-bước)
7. [Cost Explorer — Cách đọc Usage Quantity](#7-cost-explorer--cách-đọc-usage-quantity)
8. [Ký ADR — Checklist nội dung](#8-ký-adr--checklist-nội-dung)
9. [Những điểm cần nhấn mạnh khi trình bày với Mentor](#9-những-điểm-cần-nhấn-mạnh-khi-trình-bày-với-mentor)

---

## 1. Tổng quan — Mentor cần xem gì?

Directive #13 yêu cầu chứng minh 3 điều cốt lõi:

| # | Mentor cần thấy | Cách chứng minh |
|---|---|---|
| **A** | **Chạy trên capacity rẻ hơn** — spot > 50%, không chạy full on-demand | Cột Lifecycle trên EC2 Console + Usage Quantity by Purchase Option trên Cost Explorer |
| **B** | **Scale theo demand** — node tăng khi tải tăng, co LẠI khi tải giảm (không ngâm node) | Panel "Node Count and Scaling" trên Grafana quay live suốt quá trình chạy load curve |
| **C** | **Spot bị thu hồi mà khách không hay biết** — 0 request rớt trên luồng checkout | Chạy live `aws ec2 terminate-instances` lúc có tải + SLO dashboard trên Grafana |

Ngoài ra: **ADR đã ký** giải thích các quyết định kiến trúc.

> **Lưu ý:** Account đang chạy credit nên tiền $ ≈ 0 → TUYỆT ĐỐI KHÔNG dùng cột Cost (tiền). Dùng **Usage Quantity (Hours)** = số giờ-node thực tế.

---

## 2. Danh sách các thứ phải nộp (Deliverables)

### Bắt buộc (Mandatory)

| # | Deliverable | Định dạng | Lưu vào |
|---|---|---|---|
| 1 | **ADR đã ký** (quyết định kiến trúc + lý do) | `.md` | `mandate-13/ADR-mandate13-cost-efficiency-elastic.md` |
| 2 | **Screenshot ① EC2 Instances BEFORE** (Cột Lifecycle = normal/on-demand) | `.png` | `screenshots/before-ec2-instances.png` |
| 3 | **Screenshot ① EC2 Instances AFTER** (Cột Lifecycle = spot) | `.png` | `screenshots/after-ec2-instances.png` |
| 4 | **Screenshot ② Cost Explorer BEFORE** (Usage Qty by Purchase Option) | `.png` | `screenshots/before-cost-explorer-usage.png` |
| 5 | **Screenshot ② Cost Explorer AFTER** (Spot chiếm > 50% số giờ) | `.png` | `screenshots/after-cost-explorer-usage.png` |
| 6 | **Video/Screenshot ③ Grafana live** (node scale up/down theo đường cong tải) | `.mp4`/`.png` | `logs/grafana-node-count-loadcurve.mp4` |
| 7 | **Screenshot ③ Grafana SLO** (checkout ≥ 99%, p95 < 1s xuyên suốt test) | `.png` | `screenshots/slo-dashboard-during-loadtest.png` |
| 8 | **Log live spot-kill** (output terminate + kubectl get pods -w) | `.txt` | `logs/live-spot-kill.txt` |
| 9 | **kubectl outputs** (nodes trước/sau, nodeclaims, PDB, karpenter logs) | `.txt` | `logs/nodes-before.txt`, `logs/nodes-after.txt`, `logs/nodeclaims.txt`, `logs/pdb-status.txt`, `logs/karpenter-interrupt-log.txt` |
| 10 | **Sandbox plan "No changes"** (bằng chứng cô lập môi trường) | `.txt` | `logs/sandbox-plan-no-changes.txt` |

### Khuyến nghị (Nếu có thời gian)

| # | Deliverable | Mục đích |
|---|---|---|
| 11 | Quay màn hình toàn bộ Phase E+F (~30 phút) | Bằng chứng mạnh nhất — quay 1 lần bao trọn cả 3 yêu cầu |
| 12 | Locust CSV report (`/data/loadcurve-mandate13_stats.csv`) | Data dự phòng backup cho Grafana |

---

## 3. Thứ tự thực thi — Checklist 8 Phase

> Mỗi phase có chú thích chéo sang `EXECUTION-GUIDE.md` (ký hiệu §) cho các lệnh cụ thể.

### Phase A — PR + Bằng chứng Sandbox (§3 trong EXECUTION-GUIDE)

- [ ] Merge PR `feat/mandate-13-cost-efficiency-elastic` vào `develop`
- [ ] Đợi CI bot của sandbox comment "No changes" trên PR
- [ ] **Lưu lại:** Copy nội dung comment → `logs/sandbox-plan-no-changes.txt`
- [ ] Xác nhận các static check của `infra-develop.yaml` (fmt/validate) đều xanh

### Phase B — Terraform Apply (§4 trong EXECUTION-GUIDE)

- [ ] `gh workflow run infra-develop.yaml --ref develop -f apply=false` → review cái plan
- [ ] Xác nhận plan khớp với ADR (SQS queue, EventBridge rule, update IAM)
- [ ] `gh workflow run infra-develop.yaml --ref develop -f apply=true -f bootstrap_argocd=true -f confirm=apply-develop`
- [ ] Xác minh: `aws sts get-caller-identity` → `458580846647`

### Phase C — ArgoCD Sync (§5 trong EXECUTION-GUIDE)

- [ ] Sync thủ công theo **ĐÚNG THỨ TỰ**:
  1. `argocd app sync develop-karpenter-crd` → đợi Healthy
  2. `argocd app sync develop-karpenter` → đợi Healthy
  3. `argocd app sync develop-karpenter-nodepool` → đợi Healthy

### Phase D — Xác minh + Baseline Evidence (§6 trong EXECUTION-GUIDE)

- [ ] Chạy lệnh xác minh:
  ```bash
  kubectl get nodes -L karpenter.sh/capacity-type,kubernetes.io/arch,eks.amazonaws.com/capacityType
  kubectl get nodeclaims -o wide
  kubectl -n kube-system logs deploy/karpenter -c controller | grep -i interrupt
  kubectl -n techx-develop get pdb
  ```
- [ ] **Lưu output:** `logs/nodes-before.txt`, `logs/nodeclaims.txt`, `logs/pdb-status.txt`, `logs/karpenter-interrupt-log.txt`
- [ ] **Screenshot ① BEFORE:** EC2 Console → Instances → thêm cột Lifecycle, Instance type, Architecture
- [ ] **Screenshot ② BEFORE:** Cost Explorer → Usage Quantity → Group by Purchase Option
- [ ] **Screenshot ③ BEFORE:** Grafana Node Count panel + SLO dashboard

### Phase E — Load Test + After Evidence (§7 trong EXECUTION-GUIDE)

- [ ] **BẮT ĐẦU QUAY VIDEO Grafana** (hoặc mở OBS/screen recorder)
- [ ] Bắn load curve:
  ```bash
  kubectl -n techx-develop apply -f docs/mandate-19/loadtest/locust-loadcurve-mandate13-job.yaml
  kubectl -n techx-develop logs -f job/locust-loadcurve-mandate13
  ```
- [ ] Theo dõi trong 30 phút, quan sát trên Grafana:
  - Node scale up khi tải từ 40u→80u (scale up ✓)
  - Node scale down khi tải từ 80u→40u→10u (scale down ✓ — **đây là bằng chứng "co xuống thật"**)
  - Checkout success giữ vững ≥ 99%, p95 < 1s
- [ ] Tại lúc đỉnh tải (80u): **Screenshot ① AFTER** — EC2 Console → thấy spot instances
- [ ] **DỪNG QUAY VIDEO** sau khi thấy node đã co xuống xong

### Phase F — Live Spot-Kill (§8 trong EXECUTION-GUIDE) ⚡ PHẦN KHÓ NHẤT

> Làm bước này trong lúc Phase E đang chạy, khi tải đang ở mức 40u-80u.

- [ ] Terminal 1 — tìm spot instance:
  ```bash
  aws ec2 describe-instances \
    --filters "Name=tag:karpenter.sh/cluster,Values=ecommerce-develop-dev-eks" \
              "Name=instance-lifecycle,Values=spot" \
    --query 'Reservations[].Instances[].InstanceId' --output text
  ```
- [ ] Terminal 2 — bắt đầu theo dõi pod **TRƯỚC KHI kill**:
  ```bash
  kubectl -n techx-develop get pods -w
  ```
- [ ] Terminal 3 — **BẮT ĐẦU QUAY VIDEO Grafana SLO dashboard**
- [ ] **KILL:**
  ```bash
  aws ec2 terminate-instances --instance-ids <spot-instance-id>
  ```
- [ ] Quan sát:
  - Terminal 2: các pod bị evict gracefully → pod mới lên Running ở node khác (trong vài phút)
  - Grafana: tỉ lệ checkout success **KHÔNG RỚT** xuống dưới 99%
  - Grafana: p95 **KHÔNG VƯỢT QUÁ** 1s
- [ ] **Lưu lại:**
  - Copy output Terminal 1+2+3 → `logs/live-spot-kill.txt`
  - Screenshot/video Grafana SLO → `screenshots/slo-dashboard-during-loadtest.png`
- [ ] Chạy lại lệnh xác minh sau khi kill:
  ```bash
  kubectl get nodes -L karpenter.sh/capacity-type,kubernetes.io/arch
  ```
  → `logs/nodes-after.txt`

### Phase G — Cost Explorer (24h sau) (§9 trong EXECUTION-GUIDE)

> Cost Explorer bị delay ~24h — **ĐỪNG ĐỢI cái này khi đang quay video**.

- [ ] Ngày hôm sau, mở Cost Explorer:
  - Metric = **Usage Quantity (Hours)** · Filter Service = **EC2 - Compute**
  - Group by **Purchase Option** → screenshot (số giờ Spot vs On-Demand)
  - Group by **Instance Type** → screenshot
  - Granularity **Daily/Hourly** → quan sát node-hours giảm xuống vào các giờ vắng khách
- [ ] **Screenshot ② AFTER** → `screenshots/after-cost-explorer-usage.png`

### Phase H — Đóng gói Evidence

- [ ] Kiểm tra tất cả các file yêu cầu đã có mặt trong `screenshots/` và `logs/` (đối chiếu §2 phía trên)
- [ ] Cập nhật `EVIDENCE-INDEX.md` — điền tên file thật vào cột cuối cùng
- [ ] Cập nhật `README.md` §0 — đổi trạng thái từ 🟡 sang ✅/❌ thật sự
- [ ] ADR: cập nhật Status từ "Proposed" thành "Accepted" (hoặc "Accepted with deferred: Graviton")
- [ ] Commit + push toàn bộ evidence lên branch

---

## 4. Hướng dẫn quay video Console

### ① EC2 → Instances

1. Mở AWS Console → EC2 → Instances
2. Click ⚙️ (Settings) → bật các cột: **Lifecycle**, **Instance type**, **Architecture**
3. Lọc theo tag: `karpenter.sh/cluster = ecommerce-develop-dev-eks`
4. **BEFORE:** Chụp màn hình — toàn bộ Lifecycle = `normal` (on-demand)
5. **AFTER (sau Phase E):** Chụp màn hình — quan sát Lifecycle = `spot` xuất hiện

### Tips

- Sort theo Lifecycle để các node spot được gom lên đầu cho dễ nhìn
- Nếu quay video, hãy di chuột qua từng cột để đảm bảo mentor nhìn thấy rõ

---

## 5. Hướng dẫn quay video Grafana Live

### Các Dashboard cần thiết

| Panel | Dashboard | Cần thấy gì |
|---|---|---|
| **Node Count and Scaling** | `kubernetes-scaling.json` | Số node nhảy lên/xuống theo tải |
| **Checkout Success Rate** | SLO Dashboard | ≥ 99% xuyên suốt |
| **Storefront p95 Latency** | SLO Dashboard | < 1s |

### Cách quay

1. Mở 2 tab Grafana xếp cạnh nhau (hoặc chia đôi màn hình)
2. Chỉnh time range = **Last 1 hour** hoặc **Last 30 minutes** (auto-refresh 10s)
3. Bắt đầu quay video trước khi apply cái load test job
4. Tiếp tục quay xuyên suốt 30 phút load curve chạy
5. **Điểm nhấn:** dùng tính năng annotation/comment khi tải bắt đầu lên/xuống hoặc khi bạn bấm lệnh spot-kill

### Nếu không thể quay video

Hãy chụp màn hình tại 5 mốc thời gian rõ rệt:
1. Trước khi chạy load test (baseline)
2. Tải 40u (bắt đầu scale up)
3. Tải 80u (đỉnh, số node cao nhất)
4. Tải 40u (bắt đầu scale down)
5. Tải 10u + 5 phút (các node đã được gom và tắt bớt)

---

## 6. Live Spot-Kill — Script chạy từng bước

```bash
# ===== CHUẨN BỊ (trước khi kill) =====
DV=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
NS=techx-develop

# 1. Tìm ID của 1 spot instance
SPOT_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:karpenter.sh/cluster,Values=ecommerce-develop-dev-eks" \
            "Name=instance-lifecycle,Values=spot" \
  --query 'Reservations[].Instances[?State.Name==`running`].InstanceId' \
  --output text | head -1)
echo "Spot instance sẽ bị kill: $SPOT_ID"

# 2. Xem có những pod nào đang chạy trên node đó
NODE_NAME=$(aws ec2 describe-instances --instance-ids "$SPOT_ID" \
  --query 'Reservations[].Instances[].PrivateDnsName' --output text)
echo "Tên Node: $NODE_NAME"
kubectl --context "$DV" get pods -n "$NS" --field-selector "spec.nodeName=$NODE_NAME" -o wide

# 3. Mở một terminal khác — theo dõi pod
# kubectl --context "$DV" -n "$NS" get pods -w

# ===== KILL (khi đang có tải) =====
# 4. BẮT ĐẦU QUAY VIDEO GRAFANA TRƯỚC KHI CHẠY LỆNH NÀY
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') — ĐANG KILL $SPOT_ID"
aws ec2 terminate-instances --instance-ids "$SPOT_ID"

# ===== SAU KHI KILL =====
# 5. Đợi 2-3 phút, kiểm tra kết quả
kubectl --context "$DV" get nodes -L karpenter.sh/capacity-type
kubectl --context "$DV" -n kube-system logs deploy/karpenter -c controller \
  --since=5m | grep -i "interrupt\|drain\|evict"
```

### Kết quả kỳ vọng

| Quan sát | Kỳ vọng | Nếu SAI |
|---|---|---|
| `kubectl get pods -w` | Pod bị evict → Pending → Running trên node khác (vài phút) | Kiểm tra PDB + preStop |
| Grafana checkout success | Vẫn giữ ≥ 99% | DỪNG — audit PDB/graceful-drain |
| Grafana p95 | Vẫn < 1s | Có thể spike nhẹ, nhưng không được kéo dài |
| Số lượng node | Rớt 1 node → Karpenter tạo 1 node mới bù vào nếu cần | Kiểm tra NodePool limits |

---

## 7. Cost Explorer — Cách đọc Usage Quantity

### Cách vào

1. AWS Console → Billing → Cost Explorer
2. **CỰC KỲ QUAN TRỌNG:** Chọn **Usage Quantity**, KHÔNG CHỌN Cost (vì dùng credit sẽ bị ẩn $)

### Report 1 — Spot vs On-Demand

- Metric: **Usage Quantity (Hours)**
- Filter: Service = **Amazon Elastic Compute Cloud - Compute**
- Group by: **Purchase Option**
- Date range: chọn ngày bạn chạy load test
- **Kỳ vọng BEFORE:** 100% On-Demand
- **Kỳ vọng AFTER:** Spot chiếm > 50% tổng số giờ

### Report 2 — Instance Type (Chỉ dùng nếu có Graviton)

- Group by: **Instance Type**
- **Kỳ vọng:** bạn sẽ thấy t3/t3a (x86) — Graviton đã bị hoãn, nên bạn SẼ KHÔNG thấy t4g/c7g
- Note với mentor: "Bọn em chủ động defer phần Graviton — xem ADR Decision 4"

### Report 3 — Bằng chứng Scale down

- Granularity: **Hourly** (hoặc Daily)
- **Kỳ vọng:** số giờ-node (node-hours) giảm rõ rệt vào những khung giờ ít tải

---

## 8. Ký ADR — Checklist nội dung

ADR được viết tại `mandate-13/ADR-mandate13-cost-efficiency-elastic.md`. Hãy xác minh các nội dung sau:

- [x] **Context** — baseline (on-demand, Karpenter bị khóa)
- [x] **Decision 1** — Karpenter = autoscaler chính, MNG = on-demand floor
- [x] **Decision 2** — Cơ chế SQS + EventBridge xử lý interruption, rào bằng biến `enable_karpenter_interruption_queue`
- [x] **Decision 3** — Policy gom node + limits + disruption budgets
- [x] **Decision 4** — Cắt scope Graviton (thừa nhận FAIL, không lấp liếm thành pass)
- [x] **Decision 5** — Graceful-drain cho `payment` (preStop + terminationGracePeriod)
- [x] **Decision 6** — Tạo kịch bản load curve test mới
- [x] **Decision 7** — Không tạo Grafana panel mới (dùng lại panel cũ)
- [x] **Rejected options** — liệt kê đầy đủ các phương án đã cân nhắc và lý do bác bỏ
- [x] **Rollback plan** — cách rollback từng thành phần
- [x] **Approval gates** — liệt kê rõ các bước thực thi còn thiếu

### Cần cập nhật SAU KHI lấy đủ bằng chứng

- [ ] Status: Đổi "Proposed" thành "Accepted" (hoặc "Accepted with deferred: Graviton")
- [ ] Thêm section "Evidence" dẫn link tới file screenshot/log thật
- [ ] Chữ ký Owner: `Signed: [Tên bạn] — CDO-09, [ngày]`

---

## 9. Những điểm cần nhấn mạnh khi trình bày với Mentor

### Điểm mạnh cần flex

1. **Cô lập môi trường** — Shared module được rào kỹ bằng `enable_karpenter_interruption_queue`, sandbox không hề hấn gì (chứng minh bằng PR plan "No changes")
2. **Chuỗi xử lý interruption hoàn hảo:** EventBridge → SQS → Karpenter → cordon + drain → PDB chặn → preStop ngắt IP → 0 request rớt
3. **Co node thật sự (True consolidation)** — `WhenEmptyOrUnderutilized` (không xài `WhenEmpty` vô dụng), pha cuối của load test cố tình kéo dài 10 phút để khoe cảnh scale-down tự nhiên
4. **Disruption budget** — `nodes: "1"` chặn đứng tình trạng evict hàng loạt, bảo vệ tuyệt đối SLO
5. **Nguyên tắc "thay đổi tối thiểu"** — chỉ sửa những gì directive yêu cầu, không vẽ thêm râu ria

### Điểm yếu cần chủ động thừa nhận

1. **Graviton bị hoãn** — CI hiện tại chỉ build `linux/amd64`; việc mở rộng ma trận build multi-arch + test tính tương thích arm64 cho mọi service (đặc biệt là Java/C++ OTel agents) là scope quá khổng lồ. Đây là quyết định "bỏ qua có chủ đích" (deliberate deferral), không phải quên. → Sẵn sàng mất điểm tiêu chí "Graviton" ở yêu cầu #5
2. **Chưa apply** (nếu chưa làm) — Code viết rất chuẩn, nhưng thiếu bằng chứng thật trên cluster thì vẫn chỉ là Proposed (Đề xuất)

### Q&A dự kiến Mentor sẽ hỏi

| Câu hỏi | Trả lời |
|---|---|
| "Sao em vẫn giữ lại 2 con node on-demand?" | Để làm mức sàn HA (fault floor) cho CoreDNS/kube-proxy — lỡ Karpenter sập thì cluster vẫn thoi thóp sống được |
| "Sao lại để consolidateAfter 5 phút mà không phải 1 phút?" | 1 phút gây ra node churn (giật lag múa node), 5 phút là chuẩn production — bài load test đã kéo dài pha cuối để đủ thời gian demo cái này |
| "Sao không xài Cluster Autoscaler?" | IAM/Pod Identity của Karpenter đã có sẵn rồi, chỉ cần bật lên là xong. Xài CA là mang thêm 1 tool mới vào + dễ bị race condition (đấm nhau) nếu chạy song song 2 cái |
| "Chuyện gì xảy ra khi Spot node bị kill?" | AWS EventBridge bắt 3 loại event → đẩy vào SQS → Karpenter poll (< 2 phút) → cordon node → drain nhẹ nhàng (preStop 5s + terminationGrace 30s) → PDB đảm bảo dư pod sống → pod nhảy sang node khác |
| "Vì sao nhóm em không làm Graviton?" | CI pipeline hiện tại chỉ build amd64. Việc kéo dài thời gian build multi-arch + test rủi ro sập app của Java/C++ OTel agent là đánh cược mạng sống của app, hoàn toàn không cân xứng với scope của mandate này |

---

## Quick Reference — Các lệnh thiết yếu

```bash
# Biến môi trường
export DV=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
export NS=techx-develop

# Kiểm tra node
kubectl --context "$DV" get nodes -L karpenter.sh/capacity-type,kubernetes.io/arch,eks.amazonaws.com/capacityType

# Kiểm tra Karpenter
kubectl --context "$DV" get nodeclaims -o wide
kubectl --context "$DV" -n kube-system logs deploy/karpenter -c controller | grep -i interrupt

# Kiểm tra PDB
kubectl --context "$DV" -n "$NS" get pdb

# EC2 instances (kiểm tra nhanh)
aws ec2 describe-instances \
  --filters "Name=tag:karpenter.sh/cluster,Values=ecommerce-develop-dev-eks" \
  --query 'Reservations[].Instances[].{Id:InstanceId,Life:InstanceLifecycle,Type:InstanceType,Arch:Architecture,State:State.Name}' \
  --output table

# Chạy load test
kubectl --context "$DV" -n "$NS" apply -f docs/mandate-19/loadtest/locust-loadcurve-mandate13-job.yaml
kubectl --context "$DV" -n "$NS" logs -f job/locust-loadcurve-mandate13

# Kill spot
aws ec2 terminate-instances --instance-ids <SPOT_INSTANCE_ID>
```
