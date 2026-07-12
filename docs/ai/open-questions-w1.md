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


## D. Nhờ CDO cung cấp (cho bài toán thay OpenSearch — doc `ai-data-requirements-for-cdo.md`)
1. Con số "tốn" hiện tại của OpenSearch trên EKS: RAM request/limit, EBS GB, % chi phí node.
2. Nếu CDO muốn thử Loki: ai dựng container chạy song song 24h? (AI cung cấp script đo MTTD/ingest để so táo-với-táo, cam kết không lock-in backend.)
