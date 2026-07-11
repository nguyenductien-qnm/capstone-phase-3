# Architecture Trade-off: Amazon ElastiCache for Valkey

## Quyết định của nhóm

Nhóm quyết định dùng **Amazon ElastiCache for Valkey** cho Redis-compatible state/cache thay vì tự chạy Valkey trong cluster hoặc chuyển sang ElastiCache for Redis OSS.

Lý do chính: repo đã dùng Valkey từ baseline, app đang trỏ qua `VALKEY_ADDR`, và workload hiện tại chỉ cần Redis-compatible commands phổ biến. Chuyển sang managed Valkey giữ app change thấp nhưng giảm rủi ro vận hành stateful dependency trong EKS.

Tradeoff nhóm chấp nhận:

- Phải cấu hình VPC/subnet, security group, TLS/auth, secret và endpoint riêng cho ElastiCache.
- Failover behavior không giống in-cluster single pod; app phải có retry/reconnect đúng.
- Cost cần đo theo model ElastiCache, đặc biệt nếu dùng Serverless.
- Nhóm mất một phần quyền kiểm soát runtime so với tự chạy Valkey container trong cluster.

Phương án không chọn làm mặc định:

- **In-cluster Valkey**: tiện cho local/demo, nhưng không phải default production-minded vì team phải tự xử lý persistence, failover, backup và node disruption.
- **ElastiCache for Redis OSS**: chỉ chọn nếu có yêu cầu rõ về Redis OSS compatibility, vendor certification, policy nội bộ hoặc runbook đã phụ thuộc engine/version Redis OSS cụ thể.

Nhóm bắt đầu với **ElastiCache Serverless for Valkey** nếu traffic chưa ổn định. Khi traffic đã đo được và cần tối ưu dài hạn, nhóm benchmark lại với **node-based Valkey**.

## Bối cảnh

Project có cart state/cache dùng Redis-compatible API. Trong baseline, dependency này chạy trong cluster dưới tên Valkey. Nếu vẫn giữ in-cluster khi lên EKS, worker node autoscaling và node replacement sẽ phải gánh thêm rủi ro stateful workload.

Quyết định này đi cùng boundary chung:

- PostgreSQL sang RDS.
- Valkey/cart state sang ElastiCache.
- EKS worker chủ yếu chạy stateless app pods.

Boundary này giúp Karpenter/worker autoscaling an toàn hơn vì node replacement không còn trực tiếp đụng vào data dependency chính.

## Các phương án

| Phương án | Vai trò | Kết luận |
|---|---|---|
| ElastiCache for Valkey | Managed Redis-compatible engine theo hướng Valkey. | Chọn làm default. |
| ElastiCache for Redis OSS | Managed Redis OSS engine. | Không chọn nếu không có requirement Redis OSS cụ thể. |
| In-cluster Valkey | Chạy Valkey bằng Kubernetes workload. | Chỉ giữ cho local/demo hoặc fallback có kiểm soát. |

## Tradeoff chính

| Khía cạnh | ElastiCache for Valkey | ElastiCache for Redis OSS | In-cluster Valkey |
|---|---|---|---|
| Fit với repo | Cao, trùng engine naming/runtime hiện tại. | Chạy được nếu command compatible, nhưng lệch baseline. | Cao cho local, thấp hơn cho production-minded. |
| App change | Thấp: đổi endpoint, TLS/auth, secret. | Thấp nếu dùng command cơ bản. | Thấp nhất, nhưng giữ state trong cluster. |
| Vận hành | AWS quản lý nhiều phần cache operation. | AWS quản lý tương tự. | Nhóm tự lo pod, storage, failover, backup. |
| Cost | Có lợi thế lifecycle/cost trên AWS, nhưng phải đo. | Có thể cao hơn tùy engine/version/support. | Bill trực tiếp có thể thấp, ops risk cao hơn. |
| Worker autoscaling | Tách khỏi node drain/autoscaling. | Tách khỏi node drain/autoscaling. | Node replacement có thể ảnh hưởng state/cache. |
| Compatibility | Đủ cho Redis-compatible command phổ biến. | Mạnh nếu bắt buộc Redis OSS. | Đúng với baseline local. |

## Lý do chọn Valkey

Nhóm chọn Valkey vì project hiện chưa có bằng chứng cần Redis OSS-specific behavior. Giữ Valkey giúp giảm lệch giữa local baseline và managed runtime, đồng thời vẫn dùng được managed service của AWS.

Điểm quan trọng không phải chỉ là engine name. Quyết định chính là đưa state/cache ra khỏi worker node để giảm rủi ro khi scale, consolidate hoặc replace EKS nodes.

## Serverless hay node-based

Nhóm dùng **Serverless** khi:

- Traffic chưa dự đoán chắc.
- Muốn giảm vận hành capacity/sharding trong phase này.
- Cần hấp thụ spike mà chưa muốn sizing node thủ công.

Nhóm chuyển sang **node-based** khi:

- Traffic đã ổn định và có số liệu.
- Muốn dự báo chi phí bằng node-hour rõ hơn.
- Cần kiểm soát topology, node size hoặc parameter cụ thể.

Quyết định Serverless không phải chốt vĩnh viễn. Đây là điểm bắt đầu để lấy metrics thật.

## Guardrail vận hành

- ElastiCache phải nằm trong private subnet, không public endpoint.
- Security group chỉ cho phép app pod/node security group truy cập cache port cần thiết.
- Secret/TLS/auth phải được đưa vào app config rõ ràng, không hardcode endpoint hoặc credential.
- App phải có retry/reconnect khi failover hoặc connection reset.
- Nếu cart state là user-facing state quan trọng, nhóm phải xác định rõ durability expectation, backup/snapshot policy và hành vi mất cache.
- Không coi cache là database dài hạn nếu chưa có thiết kế durability riêng.

## Rollback và điều kiện đổi quyết định

Rollback gần nhất là trỏ app về in-cluster Valkey cho local/demo hoặc khi ElastiCache chưa sẵn sàng. Rollback này không nên là runtime path production-minded lâu dài.

Chuyển sang Redis OSS hợp lý nếu xuất hiện requirement formal về Redis OSS engine/version, certification, vendor policy hoặc library behavior không tương thích Valkey.

Chuyển từ Serverless sang node-based nếu metrics cho thấy cost Serverless cao hơn dự kiến hoặc traffic đủ ổn định để sizing node hiệu quả hơn.

## Verification

- App đọc `VALKEY_ADDR` và secret/TLS config đúng.
- Cart flow pass qua restart app pod.
- Failover hoặc connection reset không làm app crash loop.
- Theo dõi connection count, latency, error rate, cache memory/data stored và cost.
- Xác nhận security group không cho public hoặc cross-boundary access ngoài app path cần thiết.
