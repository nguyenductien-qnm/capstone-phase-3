# Báo Cáo Nguyên Nhân — Mandate 13: 3 Tiêu Chí Chưa Đạt

> **TF:** CDO-09 · **Directive:** [`mandates/MANDATE-13-cost-efficiency-elastic.md`](../../../mandates/MANDATE-13-cost-efficiency-elastic.md)
> **Cluster đo:** sandbox `ecommerce-dev-eks`, namespace `techx-tf1`
> **Ngày đo:** 2026-07-28 và 2026-07-30 (2 lần độc lập)
> **Tài liệu liên quan (không bắt buộc đọc kèm):** ADR `docs/05_adr/ADR-mandate13-cost-efficiency-elastic.md`, evidence pack `docs/03_platform/mandate-13/evidence/`

## 1. Tổng quan

Mandate 13 yêu cầu 5 tiêu chí trên cùng một đường cong tải (thấp→cao→thấp): (1) spot >50% compute, (2) trả tiền theo demand (node tăng khi tải lên, giảm khi tải xuống), (3) sống sót spot interruption, (4) đủ tín hiệu cho scheduler, (5) tổng hợp — node-hours giảm ≥30% + spot ≥50% + Graviton + co xuống thật + giữ SLO.

Báo cáo này giải thích chi tiết **3 hạng mục chưa đạt**: (2) trả tiền theo demand ở mức node, (5) node-hours giảm ≥30%, và (5) Graviton. Các tiêu chí còn lại (spot >50% = 63.9%, sống sót spot interruption, tín hiệu scheduler, giữ SLO) đều đã đạt và không nằm trong phạm vi báo cáo này.

**Kết luận nhanh:** cả 3 hạng mục đều là **giới hạn kiến trúc/cấu hình thật, đã kiểm chứng bằng đo lường trực tiếp trên cluster** — không phải lỗi đo, không phải Karpenter/HPA cấu hình sai.

| # | Hạng mục | Trạng thái | Nguyên nhân chính |
|---|---|---|---|
| 1 | #2 Trả tiền theo demand — node-level | ❌ KHÔNG ĐẠT | CPU request/pod quá nhỏ so với capacity node; trọng số task thấp của checkout-family |
| 2 | #5 Node-hours ≥30% | ❌ KHÔNG ĐẠT | Cùng nguyên nhân với mục 1 (đo trên cùng bài test) |
| 3 | #5 Graviton | ❌ Chưa bật | NodePool chưa cho phép kiến trúc arm64/instance-family Graviton — KHÔNG còn là giới hạn CI như nhận định ban đầu |

---

## 2. Vấn đề #2 — Trả tiền theo demand (node-level)

### 2.1 Bối cảnh

Directive yêu cầu: tải lên → Karpenter thêm node giữ SLO; tải xuống → drain + bỏ node thật, không để node bật 24/7. Ở mức pod, HPA đã scale đúng theo tải (đạt). Ở mức node — nơi mandate thực sự tính chi phí — cần Karpenter tự launch/terminate node theo nhu cầu thật.

### 2.2 Hai lần đo độc lập

**Lần 1 (28-07-2026, đỉnh 450 user):** `frontend` HPA scale 2→10 replica (đúng trần `maxReplicas` cũ), `cart` 2→4, nhưng Karpenter giữ nguyên 4 node suốt toàn bộ bài test.

**Lần 2 (30-07-2026, đỉnh 700 user, sau khi đã nới `maxReplicas`):**

| Thời điểm (UTC) | Node pool `default` | Node pool `spot` | HPA `frontend` |
|---|---|---|---|
| 07:00 (baseline) | 2 | 2 | 2 replica |
| 07:41 | 2 | 3 (Karpenter launch) | 4 replica, 116%/70% |
| 07:47 | 2 | 2 (Karpenter tự consolidate: Underutilized→delete) | — |
| 08:01 | 2 | 2 | **20/20 replica (kịch trần mới), vẫn 74%/70%** |
| 09:01 (về baseline) | 2 | 2 | 3 replica |

Dù `frontend` đã đạt **tuyệt đối trần `maxReplicas`** (20/20) và vẫn over-target (74% > 70%), pool `default` (money-path: frontend/cart/checkout/currency/quote/shipping/payment/product-catalog) **không tăng node dù chỉ 1 lần** trong suốt bài test.

### 2.3 Vì sao — capacity math

Node `c6a.large`: 1930m CPU allocatable/node → 2 node hiện có = **3.86 vCPU**.

| Service | CPU request/pod | `maxReplicas` (đã nới) | Tổng CPU tại trần |
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
| **Tổng thực đo tại đỉnh 700 user** | | | **~2.9 vCPU** |

Trần lý thuyết tuyệt đối (5.64 vCPU) vượt capacity 2-node (3.86 vCPU) — nhưng tải thực tế đo được (2.9 vCPU) thì chưa, vì chỉ `frontend` kịch trần, còn `checkout/payment/quote/shipping/currency/product-catalog` vẫn ở `minReplicas=2`. Lý do các service này không tăng: trong locustfile, task `checkout` có weight=1 so với `browse_product` weight=10 — ở 700 user, lượng request đổ vào nhóm checkout-family chưa đủ đẩy CPU utilization qua ngưỡng 70% để HPA tự sinh thêm replica. Ước tính cần **~2500+ user đồng thời** mới đủ — vượt xa mức có thể test an toàn khi `frontend` đã bão hoà từ trước (rủi ro dồn ứ, vi phạm SLO p95<1s).

### 2.4 Karpenter có hoạt động, chỉ là chưa có nhu cầu thêm node

Log Karpenter thật (không suy đoán):
```
08:06 UTC  Unconsolidatable  nodeclaim/default-pqfbw  Can't remove without creating 4 candidates
08:06 UTC  Unconsolidatable  nodeclaim/default-8m5nb  Can't remove without creating 4 candidates
```
Karpenter chủ động đánh giá consolidate nhưng bị chặn vì còn nhiều pod (do `frontend` chưa kịp co lại từ đỉnh) — xác nhận Karpenter đang hoạt động đúng, chỉ là pool `default` chưa từng cần THÊM node trong suốt bài test.

---

## 3. Vấn đề #5 — Node-hours giảm ≥30%

Đây là hệ quả trực tiếp của mục 2: node-hours chỉ đổi khi số node đổi. Vì pool `default` giữ nguyên 2 node từ đầu đến cuối cả 2 lần test, **node-hours trên pool này = 0% chênh lệch** — không đạt yêu cầu ≥30%.

Pool `spot` có 1 chu kỳ launch→consolidate thật (~6 phút, xem mục 2.2 timeline 07:41-07:47) — xác nhận cơ chế "co xuống thật" hoạt động đúng thiết kế, nhưng quá ngắn/nhỏ để đại diện cho mức giảm ≥30% mà mandate yêu cầu.

**4 phương án đã cân nhắc để khắc phục** (không thực hiện thêm ngoài phương án 4, để tránh rủi ro SLO/chi phí không cần thiết):

| # | Phương án | Đánh đổi |
|---|---|---|
| 1 | Đẩy traffic lên 1500-3000 user | `frontend` đã bão hoà — traffic dư chỉ dồn ứ, rủi ro SLO cao nhất |
| 2 | Tăng CPU *request* (không phải `maxReplicas`) cho money-path service | Hiệu quả nhất về mặt kỹ thuật, nhưng là "rightsizing ngược" chỉ phục vụ demo, cần revert sau |
| 3 | Giảm baseline xuống 1 node/AZ | Đánh đổi trực tiếp với yêu cầu HA (M17-R2) |
| 4 | **Chấp nhận kết quả thật + báo cáo trung thực** *(đã chọn)* | An toàn nhất, không tạo thêm rủi ro, nhưng không có thêm bằng chứng node-hours mới |

**Kết luận:** node-hours ≥30% **KHÔNG ĐẠT**, xác nhận độc lập 2 lần, là giới hạn kiến trúc thật (CPU-request sizing quá nhỏ so với capacity node + task-weight distribution trong locustfile), không phải lỗi đo lường hay lỗi cấu hình Karpenter/HPA.

---

## 4. Vấn đề #5 — Graviton (arm64)

### 4.1 Nhận định ban đầu (26-07-2026)

ADR Decision 4 (viết khi triển khai mandate-13) loại Graviton khỏi phạm vi vì: *"CI hiện chỉ build `linux/amd64`; multi-arch cần build matrix mới + test tương thích arm64 cho service dùng native/JNI (Java OTel agent, C++ OTel SDK) — quá lệch pha so với scope mandate này."*

### 4.2 Phát hiện mới (30-07-2026): nhận định trên đã lỗi thời

PR #467 (`feat/arm64-multiarch`, tác giả khác, **merge 28-07-2026** — 2 ngày sau khi ADR viết Decision 4, không thuộc phạm vi công việc mandate-13) đã thêm build đa kiến trúc thật cho toàn bộ app image:

- Tách job build theo kiến trúc (`ubuntu-latest` cho amd64, `ubuntu-24.04-arm` cho arm64 — runner ARM **native**, không qua QEMU), gộp thành 1 OCI manifest list/service.
- CI gate bắt buộc mỗi tag phải có đúng 2 platform (`linux/amd64` + `linux/arm64`) mới pass (`.github/workflows/app-build.yaml`, bước "Verify index có đủ 2 platform").
- Có sửa riêng cross-compilation ARM64 cho service dùng native code (`shipping` Dockerfile, thêm biến `AR`, commit `cfdea8b6`/`8764ec88`).
- Message commit ghi rõ mục tiêu: *"mở đường cho node Graviton... kubelet tự kéo đúng biến thể theo kiến trúc node."*

### 4.3 Trạng thái thật tại thời điểm báo cáo (kiểm tra trực tiếp)

Kiểm tra cả local repo lẫn NodePool live trên cluster:
```
kubernetes.io/arch:      ["amd64"]              (chưa có "arm64")
instance-family:         ["m6a", "c6a", "c7i"]  (toàn x86, không có m7g/c7g/c6g/t4g)
```

→ **Image đã sẵn sàng multi-arch (nhờ PR #467), nhưng NodePool chưa cho phép Karpenter chọn node Graviton.** Đây là thay đổi cấu hình nhỏ, không còn là giới hạn CI như ADR gốc từng ghi nhận.

### 4.4 Việc còn lại để thực sự bật Graviton

1. Thêm `"arm64"` vào `kubernetes.io/arch` + thêm instance-family Graviton (vd `m7g`, `c7g`, `t4g`) vào NodePool.
2. Audit thủ công xác nhận từng service thực sự có index 2-platform trên ECR (CI gate đã enforce nên nhiều khả năng đã có, nhưng chưa kiểm tra toàn bộ service).
3. **Test chạy thật trên node arm64** cho service dùng native/JNI (Java OTel agent, C++ OTel SDK) — CI build thành công không đồng nghĩa runtime đúng, cần verify riêng trước khi cho traffic thật.

**Kết luận:** Graviton **vẫn chưa đạt**, nhưng lý do đã đổi — không còn là "CI không hỗ trợ" mà là "chưa cấu hình NodePool + chưa runtime-verify", việc nhỏ hơn nhiều so với ghi nhận ban đầu trong ADR.

---

## 5. Kết luận chung

Cả 3 hạng mục đều **chưa đạt**, nhưng đã được đo lường/kiểm chứng trực tiếp trên cluster thật (không dựa trên suy đoán), kèm nguyên nhân gốc rõ ràng và hướng khắc phục cụ thể cho từng mục. Các tiêu chí còn lại của Directive #13 (spot >50%, sống sót spot interruption, tín hiệu scheduler, giữ SLO) đều đã đạt chuẩn.
