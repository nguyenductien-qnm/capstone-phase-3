# Câu hỏi mở cuối Tuần 1 — đem đi hỏi CDO & mentor (12/07/2026)

Mỗi câu kèm bối cảnh 1 dòng + phương án để người trả lời chọn nhanh. Đánh dấu ✍️ = cần câu trả lời trước khi nhóm AI làm tiếp việc tương ứng.

## A. Hỏi CDO — valkey-cart (J1, CRITICAL — code CDO, SLO checkout của chung)

Bối cảnh: `volatile-lru` được thêm **không kèm `--maxmemory`** (policy không chạy); TTL cart đã gỡ; limit container 20Mi → cart tích vô hạn → nguy cơ kubelet OOMKill = mất toàn bộ giỏ đang sống = đánh checkout ≥99%.

1. ✍️ Chọn hướng nào: **(a)** khôi phục TTL cart (60m như baseline, hay số khác?); **(b)** set `--maxmemory` (bao nhiêu? cần < cgroup limit) + nâng limit 20Mi lên; **(c)** cả hai?
2. ✍️ Cache reviews của AI đang ở chung instance valkey-cart — CDO muốn **tách instance riêng** (thêm ~20-50Mi) hay chấp nhận chung + maxmemory? (Nếu chung + maxmemory: key reviews là nhóm volatile duy nhất → hứng 100% eviction trước.)
3. Ai chạy soak test đo time-to-OOM (`INFO memory` theo giờ dưới locust) để chọn số maxmemory — CDO hay AI hỗ trợ?
4. Session length thực tế của khách (từ analytics/locust) là bao nhiêu — để TTL cart (nếu khôi phục) có căn cứ thay vì lấy lại 60m mặc định?

## B. Hỏi CDO — IAM Bedrock (blocker deploy thật duy nhất)

Bối cảnh: code đã gọi `bedrock-runtime` (us-east-1); thiếu quyền là pod chỉ chạy được đường mock.

1. ✍️ Cấp `bedrock:InvokeModel` bằng **IRSA cho serviceAccount `product-reviews`** (least-privilege, khuyến nghị) hay **node role** (nhanh hơn)? Tuần 2 cần thêm serviceAccount `shopping-copilot`.
2. ✍️ Model access trong Bedrock console đã enable cho `amazon.nova-lite-v1:0`, `nova-micro-v1:0`, `nova-pro-v1:0` chưa? (Region `us-east-1`.)
3. Loại credit AWS của account là gì (Activate/EDU/promo)? — quyết định cách trình bày cost trước CFO; nhóm đã bỏ Claude nên không blocking, nhưng cần biết để không hứa sai.
4. ECR repo cho image `product-reviews` (và tuần 2 `shopping-copilot`) — đặt tên/tag theo convention nào, ai có quyền push? (`.env.override` đang trỏ `804372444787.dkr.ecr.us-east-1...`.)
5. EKS đã có **kube-state-metrics + cadvisor metrics** trong Prometheus chưa? Rule `memory-saturation-high` (cảnh báo sớm OOM — chính là lớp sự cố J1) cần 2 metric đó.

## C. Hỏi mentor — khung chấm & target

1. ✍️ Khung **evidence-pack 6 doc** (`01_requirements`…`06_contracts`, theo `CAPSTONE_EVIDENCE_PACK_FORMAT.md` của W11-12) có áp dụng cho Phase 3 không, hay Phase 3 chấm theo cấu trúc tự do? (Nhóm đã tạo sẵn 01/02/04 — nếu không cần thì giữ làm tài liệu nội bộ.)
2. ✍️ **Target MTTD** có con số chính thức không? Nhóm tự đặt ≤ 2 phút (suy từ error budget non-5xx 0.5%/24h); đo được max 35.4s @ poll 30s. Nếu mentor có số khác (vd ≤ 1 phút, ≤ 30s) thì poll interval sẽ chỉnh theo bảng sensitivity có sẵn.
3. Circuit breaker đọc **tín hiệu lỗi quan sát được** (đã sửa) — xác nhận cách hiểu luật "không tắt/đổi hướng cơ chế sự cố flagd": việc *đọc* cờ để bypass call (bản cũ) có bị tính vi phạm không? (Nhóm đã bỏ để an toàn, hỏi để chắc.)
4. Số đo hiện từ **docker compose local** (script tái tạo committed) — mentor chấp nhận làm evidence tạm trong khi chờ đo lại trên EKS, hay chỉ tính số EKS?
5. `_baseline-phase3/` để diff là bản BTC phát — có được phép trích diff vào doc công khai của nhóm không (hiện chỉ mô tả kết quả)?

## D. Nhờ CDO cung cấp (cho bài toán thay OpenSearch — doc `ai-data-requirements-for-cdo.md`)
1. Con số "tốn" hiện tại của OpenSearch trên EKS: RAM request/limit, EBS GB, % chi phí node.
2. Nếu CDO muốn thử Loki: ai dựng container chạy song song 24h? (AI cung cấp script đo MTTD/ingest để so táo-với-táo, cam kết không lock-in backend.)
