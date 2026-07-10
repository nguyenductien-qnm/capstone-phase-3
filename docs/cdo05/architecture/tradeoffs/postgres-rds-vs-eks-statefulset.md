# Architecture Trade-off: Amazon RDS PostgreSQL vs PostgreSQL on EKS

## Owner

- Team: Infrastructure
- Nhóm chịu trách nhiệm : CDO05-CD09
- Người chịu trách nhiệm : Thành Đạt

## Quyết định của nhóm

Nhóm quyết định dùng **Amazon RDS PostgreSQL** thay vì chạy PostgreSQL production-minded trong EKS bằng StatefulSet/CSI/PVC.

Lý do chính: PostgreSQL là stateful dependency quan trọng, trong khi baseline hiện tại chỉ giống demo dependency hơn là database platform. RDS giảm rủi ro vận hành DB bằng managed backup, snapshot, PITR, patching và Multi-AZ/failover option, đồng thời tách database khỏi EKS node drain/autoscaling.

Tradeoff nhóm chấp nhận:

- Chi phí AWS cao hơn so với tự chạy một pod PostgreSQL nhỏ trong cluster.
- Ít quyền kiểm soát OS/container/runtime hơn self-managed PostgreSQL.
- Nhóm vẫn phải vận hành schema migration, query/index tuning, connection pool, secret rotation, security group, monitoring, backup retention và failover test.

Phương án không chọn làm mặc định:

- **PostgreSQL trong EKS + CSI/PVC**: CSI/PVC giải quyết storage attach/provision, nhưng không tự giải quyết replication, failover, PITR, backup verification, restore drill, corruption handling hoặc DB upgrade.

Nhóm sẽ xem xét lại nếu mục tiêu phase chuyển sang học/vận hành database platform trên Kubernetes và team cam kết dùng PostgreSQL operator, replication, WAL archive, restore drill và runbook failover đầy đủ.

## Bối cảnh

Baseline hiện có PostgreSQL trong cluster. Với local/demo, cách này đơn giản và đủ để chạy app. Với production-minded boundary, database không nên phụ thuộc vào worker node lifecycle nếu không có operator và runbook rất rõ.

Quyết định này cũng giúp worker layer sạch hơn:

- EKS worker chủ yếu chạy stateless app pods.
- Karpenter/Managed Node Groups/Auto Mode có thể thay node mà không kéo theo database crash recovery.
- App failure khi node down chủ yếu là reconnect/retry, không phải volume detach/attach và database recovery.

## Các phương án

| Phương án | Vai trò | Kết luận |
|---|---|---|
| PostgreSQL trong EKS + CSI/PVC | Nhóm tự vận hành DB platform trong Kubernetes. | Không chọn làm default. |
| Amazon RDS PostgreSQL | AWS quản lý nhiều phần DB operation. | Chọn làm default. |

## Tradeoff chính

| Khía cạnh | PostgreSQL trong EKS + CSI/PVC | Amazon RDS PostgreSQL |
|---|---|---|
| Fit với repo hiện tại | Thấp nếu giữ như baseline, vì chưa có HA/backup/operator rõ. | Cao hơn cho production-minded design. |
| Vận hành | Team tự vận hành database platform trong Kubernetes. | AWS quản lý nhiều phần storage, backup, patching, failover option. |
| Node down/eviction | Phải xử lý reschedule, detach/attach volume, crash recovery, AZ constraint. | EKS node down không làm DB chạy lại trên worker node. |
| HA/failover | Không tự có, cần operator/replication/runbook. | Multi-AZ/failover option do RDS quản lý. |
| Backup/PITR | Team tự thiết kế WAL archive/snapshot/restore test. | Automated backup, snapshot và PITR trong retention window. |
| Worker autoscaling | Khó hơn vì stateful pod ràng buộc node/AZ/PDB. | Dễ hơn vì worker chủ yếu stateless. |
| Control | Cao hơn với OS/container/extensions/operator. | Ít control runtime hơn, dùng capability RDS cung cấp. |
| Cost | Bill trực tiếp có thể thấp nhưng ops risk cao. | Tốn RDS cost, đổi lại giảm DB operations burden. |

## Vì sao CSI/PVC chưa đủ

EBS CSI giúp Kubernetes provision và attach EBS volume cho pod. Đây là storage primitive, không phải database platform.

Nếu tự chạy PostgreSQL trong EKS theo hướng production, nhóm còn phải có:

- StatefulSet hoặc PostgreSQL operator như CloudNativePG/Crunchy.
- Replication, failover và split-brain prevention.
- WAL archive, backup/PITR và restore drill định kỳ.
- PDB, anti-affinity/topology spread và node pool riêng cho stateful workload.
- Runbook volume attach, crash recovery, failover, corruption handling và upgrade.
- DB-level monitoring, slow query/index tuning và connection storm handling.

Nếu các phần này chưa được thiết kế, gọi PostgreSQL pod + PVC là production database sẽ rủi ro.

## Guardrail vận hành

- RDS phải nằm trong private subnet, không public.
- Security group chỉ cho phép app hoặc RDS Proxy path cần thiết truy cập port `5432`.
- Bật automated backup với retention rõ ràng.
- Nếu workload quan trọng, đánh giá Multi-AZ.
- App phải có connection pool, retry/reconnect behavior và timeout rõ.
- Migration phải chạy qua path có kiểm soát, không để mọi pod runtime dùng quyền migration/admin.

## Rollback và điều kiện đổi quyết định

Fallback cho local/demo là PostgreSQL in-cluster. Fallback này không thay thế RDS cho runtime production-minded nếu chưa có operator/HA/backup đầy đủ.

Chuyển lại PostgreSQL in EKS chỉ hợp lý khi nhóm chủ động nhận ownership DB platform và chứng minh được backup/restore, failover, upgrade và node disruption bằng test.

## Verification

- App kết nối tới RDS hoặc RDS Proxy endpoint thành công.
- Automated backup/PITR được bật và có restore drill tối thiểu.
- Nếu dùng Multi-AZ, chạy failover test và xác nhận app reconnect.
- Theo dõi `DatabaseConnections`, CPU, memory, storage, slow queries và error rate.
- Kiểm tra node drain EKS không làm mất database availability.
