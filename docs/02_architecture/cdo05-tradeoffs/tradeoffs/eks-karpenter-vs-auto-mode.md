# Architecture Trade-off: Standard EKS with Karpenter for worker nodes

## Quyết định của nhóm

Nhóm quyết định dùng **Standard EKS + Karpenter** cho worker nodes.

Lý do chính: sau khi PostgreSQL được tách sang RDS và Valkey/cart state được tách sang ElastiCache, EKS worker layer chủ yếu chạy stateless application pods. Với boundary đó, Karpenter fit hơn vì nhóm cần kiểm soát capacity, instance mix, Spot/On-Demand policy, consolidation và cost của worker nodes.

Tradeoff nhóm chấp nhận:

- Nhóm tự vận hành Karpenter controller, IAM, `NodePool`, `EC2NodeClass` và upgrade lifecycle.
- Phải thiết kế PDB, topology spread, resource requests và disruption policy nghiêm túc.
- Incident debug phức tạp hơn Auto Mode vì nhiều behavior nằm ở cấu hình platform của nhóm.
- Cost thấp hơn không tự xảy ra; nhóm phải đo và tune requests, consolidation, Spot mix và node overhead.

Phương án không chọn làm mặc định:

- **EKS Auto Mode**: phù hợp nếu ưu tiên giảm vận hành data plane, nhưng nhóm muốn giữ quyền kiểm soát worker capacity và tránh Auto Mode management fee.
- **Managed Node Groups**: đơn giản hơn Karpenter, nhưng autoscaling thô hơn và dễ dư idle node khi traffic biến động.

Nhóm sẽ xem xét lại quyết định nếu chưa phân công vận hành platform rõ ràng, workload không fit với Karpenter policy, hoặc chi phí vận hành Karpenter cao hơn lợi ích cost/control nhận được.

## Bối cảnh

Repo hiện chưa có IaC worker node hoàn chỉnh. Đây là quyết định platform khi dựng EKS, không phải migration từ một setup Karpenter hoặc Auto Mode đang tồn tại.

Project có nhiều service nhỏ, `frontend-proxy`, observability stack, background/load-generator và một số dependency stateful trong baseline. Các quyết định liên quan đã nghiêng về managed services cho stateful data:

- PostgreSQL sang Amazon RDS.
- Valkey/cart state sang Amazon ElastiCache for Valkey.
- EKS giữ vai trò chạy application compute.

Khi stateful dependency không còn buộc chặt vào worker node, node replacement, consolidation và scale down trở nên an toàn hơn. Đây là điều kiện quan trọng để Karpenter có giá trị.

## Các phương án

| Phương án | Vai trò | Kết luận |
|---|---|---|
| EKS Auto Mode | AWS quản lý nhiều phần data plane và node lifecycle hơn. | Không chọn mặc định vì nhóm muốn kiểm soát sâu worker capacity/cost. |
| Standard EKS + Karpenter | Nhóm tự quản autoscaling worker node bằng Karpenter. | Chọn làm hướng chính. |
| Standard EKS + Managed Node Groups | Dùng node group quen thuộc, ít moving parts hơn Karpenter. | Giữ làm fallback nếu Karpenter quá nặng cho phase này. |

## Tradeoff chính

| Khía cạnh | EKS Auto Mode | Standard EKS + Karpenter | Managed Node Groups |
|---|---|---|---|
| Operational overhead | Thấp nhất, AWS quản lý nhiều hơn. | Cao hơn, nhóm vận hành controller/policy/add-ons. | Trung bình, ít moving parts hơn Karpenter. |
| Control node/capacity | Thấp hơn, node managed/immutable hơn. | Cao nhất: instance family, Spot mix, topology, disruption, consolidation. | Vừa phải: kiểm soát theo node group/ASG. |
| Autoscaling | Built-in, ít cấu hình hơn. | Linh hoạt, provision sát pod demand hơn. | Thô hơn, dễ overprovision. |
| Cost | Có Auto Mode management fee. | Không có Auto Mode fee, nhưng cần tune tốt. | Không có Auto Mode fee, nhưng idle node dễ xảy ra. |
| Debug/runbook | Ít quyền can thiệp node hơn. | Rõ policy nhưng nhiều thứ nhóm phải hiểu. | Quen thuộc, dễ giải thích hơn Karpenter. |
| Fit với boundary stateless | Tốt nếu ưu tiên simplicity. | Tốt nhất nếu ưu tiên cost/control. | Tốt cho baseline nhỏ, ít biến động. |

## Lý do chọn Karpenter

Karpenter là lựa chọn hợp lý cho boundary đã chốt vì worker nodes không còn là nơi chạy database chính. Nhóm có thể để Karpenter thay node, consolidate capacity và scale theo pod demand mà không kéo theo rủi ro detach/attach volume của database production.

Các lợi ích nhóm muốn lấy:

- Provision node sát nhu cầu pod hơn Managed Node Groups.
- Consolidation xóa node dư sau load spike.
- NodePool/EC2NodeClass cho phép tách workload, instance family, architecture và topology.
- Có đường dùng Spot cho workload chịu được interruption.
- Thể hiện rõ platform engineering: capacity policy, disruption budget, workload isolation và cost control.

Karpenter không được chọn chỉ vì "rẻ". Nếu requests sai, PDB block consolidation, workload không chịu disruption, hoặc team không theo dõi node cost thì Karpenter vẫn có thể tốn hơn và khó debug hơn.

## Guardrail vận hành

- Không để production database chạy như dependency stateful không có operator/HA/backup trên worker pool do Karpenter tự thay node.
- `frontend-proxy` cần tối thiểu 2 replicas nếu public traffic đi qua NLB.
- Các service quan trọng như `frontend`, `cart`, `checkout`, `product-catalog` cần resource requests đúng và PDB khi có nhiều replica.
- Dùng topology spread hoặc anti-affinity cho app path chính.
- Spot chỉ dùng cho workload chịu được interruption; critical path cần On-Demand hoặc policy rõ.
- Theo dõi DaemonSet overhead vì overhead này ảnh hưởng trực tiếp tới packing và cost.

## Rollback và điều kiện đổi quyết định

Fallback gần nhất là **Managed Node Groups** nếu Karpenter làm phase này chậm lại quá nhiều hoặc team chưa đủ năng lực vận hành.

Chuyển sang **EKS Auto Mode** hợp lý nếu mục tiêu thay đổi sang giảm ops tối đa, team không cần custom node policy, và Auto Mode fee chấp nhận được so với chi phí vận hành platform.

## Verification

Không chốt quyết định chỉ bằng việc node được tạo thành công. Cần kiểm tra bằng workload thật:

- Scale up bằng load-generator và đo pod pending time.
- Scale down sau khi hết load và xác nhận node dư được consolidate.
- Rolling update app trong lúc Karpenter đang consolidate.
- Simulate node drain với PDB.
- Test NLB -> `frontend-proxy` availability khi node bị thay.
- Theo dõi unschedulable pods, node provisioning latency, disruption events, Spot interruption nếu dùng Spot và node cost theo workload label.
