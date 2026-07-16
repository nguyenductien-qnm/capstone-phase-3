# Câu hỏi mở cuối Tuần 1 — đem đi hỏi CDO & mentor (12/07/2026)

Mỗi câu kèm bối cảnh 1 dòng + phương án để người trả lời chọn nhanh. Đánh dấu ✍️ = cần câu trả lời trước khi nhóm AI làm tiếp việc tương ứng.

## A. Hỏi CDO — valkey-cart (J1, CRITICAL — TTL cart đã KHÔI PHỤC 60m tạm thời 13/07 để an toàn, chờ CDO chốt hướng cuối — code CDO, SLO checkout của chung)

> **✅ CẬP NHẬT 14/07: J1 đóng do hạ tầng đổi.** CDO đã migrate cart + reviews cache sang **ElastiCache Valkey managed** (`terraform/modules/elasticache/`, TLS + auth, failover); pod `valkey-cart` in-cluster đã tắt. Kịch bản OOMKill 20Mi không còn. Câu 1-4 dưới đây obsolete — chỉ còn cần CDO: (1) xác nhận `maxmemory-policy` trên param group (default `volatile-lru`), (2) CloudWatch alarm `Evictions > 0`, (3) co-sign hồi tố ADR-003 (đã có addendum 14/07 trong `05_adrs.md`). Tracked TF1-68.

Bối cảnh (lịch sử): `volatile-lru` được thêm **không kèm `--maxmemory`** (policy không chạy); TTL cart đã gỡ; limit container 20Mi → cart tích vô hạn → nguy cơ kubelet OOMKill = mất toàn bộ giỏ đang sống = đánh checkout ≥99%.

1. ✍️ Chọn hướng nào: **(a)** khôi phục TTL cart (60m như baseline, hay số khác?); **(b)** set `--maxmemory` (bao nhiêu? cần < cgroup limit) + nâng limit 20Mi lên; **(c)** cả hai?
2. ✍️ Cache reviews của AI đang ở chung instance valkey-cart — CDO muốn **tách instance riêng** (thêm ~20-50Mi) hay chấp nhận chung + maxmemory? (Nếu chung + maxmemory: key reviews là nhóm volatile duy nhất → hứng 100% eviction trước.)
3. Ai chạy soak test đo time-to-OOM (`INFO memory` theo giờ dưới locust) để chọn số maxmemory — CDO hay AI hỗ trợ?
4. Session length thực tế của khách (từ analytics/locust) là bao nhiêu — để TTL cart (nếu khôi phục) có căn cứ thay vì lấy lại 60m mặc định?

## B. Hỏi CDO — IAM Bedrock (blocker deploy thật duy nhất)

Bối cảnh: code đã gọi `bedrock-runtime` (us-east-1); thiếu quyền là pod chỉ chạy được đường mock.

1. ✍️ Cấp `bedrock:InvokeModel` bằng **IRSA cho serviceAccount `product-reviews`** (least-privilege, khuyến nghị) hay **node role** (nhanh hơn)? Tuần 2 cần thêm serviceAccount `shopping-copilot`.
2. ✍️ Model access trong Bedrock console đã enable cho `amazon.nova-lite-v1:0`, `nova-micro-v1:0`, `nova-pro-v1:0` chưa? (Region `us-east-1`.)

5. EKS đã có **kube-state-metrics + cadvisor metrics** trong Prometheus chưa? Rule `memory-saturation-high` (cảnh báo sớm OOM — chính là lớp sự cố J1) cần 2 metric đó.


## D. Nhờ CDO cung cấp (cho bài toán thay OpenSearch — doc `ai-data-requirements-for-cdo.md`)
1. Con số "tốn" hiện tại của OpenSearch trên EKS: RAM request/limit, EBS GB, % chi phí node.
2. Nếu CDO muốn thử Loki: ai dựng container chạy song song 24h? (AI cung cấp script đo MTTD/ingest để so táo-với-táo, cam kết không lock-in backend.)

---

## ✅ CÂU TRẢ LỜI NHẬN ĐƯỢC (mentor, 12/07 tối)

| Câu | Trả lời | Hành động đã làm |
|---|---|---|
| C1 — evidence-pack 6 doc áp dụng Phase 3? | **CÓ** | Hoàn tất bộ 6: `01_requirements` / `02_solution_design` / `03_ai_engine_spec` (+`03_specs/`) / `04_eval_report` / `05_adrs` (đổi tên từ ADR-log) / `06_contracts` (pointer → `docs/shared/integration-contracts/`) |
| C3 — đọc cờ sự cố flagd để bypass? | **CÓ PHẠM LUẬT** | May: đã gỡ từ 12/07 sáng (trước khi hỏi) — circuit breaker hiện theo lỗi quan sát được. Ghi xác nhận vào `05_adrs.md` |
| C4 — số đo compose local làm evidence? | **DÙNG TẠM ĐƯỢC** | `04_eval_report.md` đánh dấu evidence tier: "compose (tạm, mentor chấp nhận 12/07)" vs "EKS (chính thức, W2)" |
| C2 — target MTTD chính thức? | Chưa có số cứng | Theo tài liệu AIOps course: **TTD là KPI đo qua chaos** (confusion matrix + TTD/TTR per experiment), còn *alerting policy* đi theo **multi-window burn-rate trên error budget** — tức course nghiêng về **target suy từ SLO/budget, không phải con số cố định**. Cách nhóm suy ≤2 phút từ budget 0.5%/24h là đúng school này; giữ target đó + bảng sensitivity, sẽ trình mentor như derivation thay vì xin số |
