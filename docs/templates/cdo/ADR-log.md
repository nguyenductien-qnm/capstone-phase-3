# Decision Log (ADR) - TF__ / __

> Append-only. 1 quyết định lớn = 1 ADR. Không xóa ADR cũ. Khi nào viết ADR + vì sao có các trường cost/SLO/rollback: xem `README.md`.

---

## ADR-REL-001 - Dùng HPA thay vì replicas tĩnh cho service critical
> Trạng thái: Chấp nhận
- **Ngày:** 2026-07-13
- **Người ký:** Phong (Rel Eng #1) · Kien (đồng quyết định) · Tech Lead (sign-off)
- **Trụ:** Reliability (chạm Performance / Cost)
- **Bối cảnh:** Hệ thống phải gánh flash sale (mandate #2: 200 user đồng thời / 15 phút) mà không tăng ngân sách. Replicas tĩnh = 2 để lại tài nguyên neo ở đỉnh, không co giãn được khi tải tăng/giảm.
- **Quyết định:** Dùng HPA (CDO-42) cho checkout / cart / product-catalog thay vì replicas tĩnh. HPA ghi đè trường replicas — khi `.hpa.enabled`, bỏ replicas tĩnh để tránh fight HPA ↔ ArgoCD. PDB (CDO-34) đi kèm đảm bảo không breach SLO khi scale.
- **Phương án khác đã cân:** A) replicas tĩnh = 2 (loại: tĩnh, neo cost, không hấp thụ spike, vi phạm "co lên rồi co xuống" của mandate #2). B) chỉ Cluster Autoscaler (loại: chậm hơn, theo node-group thay vì pod metric).
- **Cost Δ:** HPA $0; cho phép burst co giãn theo tải → cost theo tải, nằm trong trần $300/tuần.
- **Ảnh hưởng SLO:** Giữ checkout ≥99% / cart ≥99.5% dưới 200 user nhờ co giãn pod; PDB (maxUnavailable:1 + spread) ngăn breach SLO lúc node churn. Verify qua SLO dashboard (CDO-27).
- **Rollback:** tắt HPA / khôi phục replicas tĩnh trong values.yaml.
- **Hệ quả:** ✅ co giãn, cost theo tải · ⚠️ HPA cần metrics + PDB + right-size để an toàn.

---

## ADR-REL-002 - ResourceQuota (không phải node) là bottleneck flash-sale → nâng quota
> Trạng thái: Chấp nhận
- **Ngày:** 2026-07-14
- **Người ký:** Phong (Rel Eng #1) · Kien (đồng quyết định)
- **Trụ:** Reliability (chạm Cost)
- **Bối cảnh:** Load test 200 user vào namespace `techx-tf1` cho `FailedCreate: exceeded quota: techx-corp-quota, requested: limits.cpu=200m, used: limits.cpu=7850m, limited: limits.cpu=8` cho frontend/ad TRONG KHI node mới ~43% idle. → Trần chặn HPA scale-up KHÔNG phải thiếu node; ResourceQuota (CDO-42) là ràng buộc thực sự.
- **Quyết định:** Nâng `resourceGovernance.resourceQuota.hard` trong `platform/charts/application/values.yaml`: requests.cpu 4→6, limits.cpu 8→14, requests.memory 8Gi→10Gi, limits.memory 12Gi→16Gi, pods 40→70. Giữ trần đủ chịu 200 user mà vẫn trong ngân sách.
- **Phương án khác đã cân:** A) Bỏ ResourceQuota (loại: mất governance chống phình cost, trái mandate). B) Chỉ thêm node (loại: đã chứng minh node KHÔNG phải bottleneck; tốn tiền vô ích).
- **Cost Δ:** $0 trực tiếp (quota là trần, không phải cấp phát); thực chi vẫn theo tải nhờ HPA, trong trần $300/tuần.
- **Ảnh hưởng SLO:** Gỡ FailedCreate → HPA scale-up được → giữ checkout ≥99% / cart ≥99.5% dưới 200 user. Verify qua SLO dashboard.
- **Rollback:** khôi phục giá trị quota cũ (4/8/8Gi/12Gi/40) trong values.yaml.
- **Hệ quả:** ✅ gỡ bottleneck thật, giữ governance · ⚠️ trần cao hơn cần Cluster Autoscaler để có node thật khi HPA bung (xem ADR-REL-003).

---

## ADR-REL-003 - Cluster Autoscaler trên Managed Node Group (hoãn Karpenter)
> Trạng thái: Bị thay thế bởi ADR-REL-005 (CDO-99)
- **Ngày:** 2026-07-14
- **Người ký:** Phong (Rel Eng #1) · Kien (đồng quyết định)
- **Trụ:** Reliability + Cost
- **Bối cảnh:** Sau khi nâng quota, HPA có thể bung pod vượt sức chứa node hiện có → cần node co giãn TỰ ĐỘNG (up khi pod Pending, down khi thừa) để đúng "co lên rồi co xuống" của mandate #2 mà không neo node 24/7. Cluster hiện chỉ có MNG tĩnh, không autoscaler.
- **Quyết định:** Cài Cluster Autoscaler (Helm 9.58.0) qua ArgoCD, auth IRSA (`terraform/modules/eks/cluster-autoscaler.tf`), auto-discovery ASG của MNG. Node group `desired_size` chuyển cho CA sở hữu (`lifecycle.ignore_changes`); min/max = 2/6 do terraform quản. Karpenter HOÃN (follow-up) vì MNG+CA đủ cho mandate #2 và ít thay đổi hạ tầng hơn trong 3 tuần.
- **Phương án khác đã cân:** A) Karpenter (loại tạm: mạnh hơn nhưng thêm bề mặt vận hành/hạ tầng, để lại follow-up). B) Node tĩnh desired=5 (loại: neo cost, không co xuống, trái mandate). C) Auth Pod Identity (loại: repo đã chuẩn hoá IRSA + OIDC provider sẵn có).
- **Cost Δ:** Co xuống về min=2 khi hết tải → tiết kiệm so với neo 5 node; đỉnh giới hạn bởi max=6, trong trần $300/tuần.
- **Ảnh hưởng SLO:** Node kịp cấp khi pod Pending → giữ SLO dưới flash-sale; PDB (CDO-34) chống breach lúc node churn/scale-down.
- **Rollback:** `enable_cluster_autoscaler=false` (gỡ IRSA) + xoá ArgoCD app cluster-autoscaler; MNG về desired tĩnh.
- **Hệ quả:** ✅ node co giãn tự động theo tải, cost theo tải · ⚠️ CA chậm hơn Karpenter; cần theo dõi để cân nhắc migrate sau.
- **Forward link:** Xem ADR-REL-005 thay thế cơ chế Cluster Autoscaler bằng Karpenter.

---

## ADR-REL-004 - valkey-cart SPOF: chuyển sang ElastiCache HA (2 node/2 AZ) + bật MultiAZ
> Trạng thái: Chấp nhận
- **Ngày:** 2026-07-14
- **Người ký:** Nguyen Dinh Thi (Rel Eng #2 - Deploy Safety) · Tech Lead (sign-off)
- **Trụ:** Reliability (SPOF) · chạm Cost
- **Bối cảnh (INC-2):** valkey-cart là kho state của giỏ hàng. Bản gốc chart chạy valkey **in-cluster 1 replica** → mất pod/node = **mất toàn bộ giỏ khách**. Tăng replica cart API (CDO-28) KHÔNG cứu được, vì dữ liệu giỏ nằm ở valkey chứ không ở cart API (cart chỉ là stateless client). Đây là SPOF thật trên luồng ra tiền.
- **Quyết định:** Tắt valkey in-cluster (`components.valkey-cart.enabled=false`, values.yaml:1272) và trỏ cart sang **AWS ElastiCache Valkey** managed (`VALKEY_ADDR` = primary endpoint, values.yaml:345). Cấu hình HA: `automatic_failover_enabled=true`, `transit/at_rest_encryption=true` (`terraform/modules/elasticache/main.tf:51-53`). **Bổ sung `multi_az_enabled=true`** để có guarantee cross-AZ chính thức.
- **Bằng chứng runtime (14/07/2026, `aws elasticache describe-replication-groups --replication-group-id ecommerce-dev-valkey`):**
  - 2 node: `ecommerce-dev-valkey-001` (primary, **us-east-1b**), `ecommerce-dev-valkey-002` (replica, **us-east-1a**).
  - `AutomaticFailover = enabled`; node đã nằm ở **2 AZ khác nhau**.
  - Caveat phát hiện: `MultiAZ = disabled` → **đã bật + verify live 14/07/2026** (`terraform apply -target=module.elasticache`: plan 1 in-place change, sau apply `MultiAZ=enabled`, Status=available, không recreate). Cart dùng primary DNS endpoint → tự repoint khi failover.
- **Phương án khác đã cân:** A) Giữ valkey in-cluster + thêm replica/Sentinel (loại: tự vận hành HA cache trên K8s tốn công + rủi ro, trong khi managed rẻ và ổn hơn). B) Chấp nhận SPOF (loại: vi phạm yêu cầu ② Mandate-03 "không điểm chết đơn lẻ trên luồng ra tiền"). C) Không bật MultiAZ, chỉ dựa auto-failover (loại: node đã cross-AZ nhưng thiếu guarantee chính thức của AWS; bật flag chi phí $0).
- **Cost Δ:** 2× `cache.t4g.micro` (đã đang chạy) — trong trần $300/tuần. Bật MultiAZ **$0** (không tính phí riêng, không thêm node).
- **Ảnh hưởng SLO:** Hết SPOF giỏ hàng → giữ cart ≥99.5%. Residual risk: failover blip vài giây khi mất primary (nằm trong cart error budget 0.5%; cart có readiness gate + HPA min=2 + retry). Single-primary write là đặc tính chấp nhận của ElastiCache (không multi-master).
- **Rollback:** trỏ `VALKEY_ADDR` về endpoint cũ / bật lại valkey in-cluster; `multi_az_enabled=false` (chỉ là flag).
- **Hệ quả:** ✅ SPOF giỏ hàng đã gỡ, HA managed cross-AZ · ⚠️ bật MultiAZ cần `terraform apply` có thể gây 1 lần failover ngắn → làm ngoài giờ cao điểm, KHÔNG sát demo. Cross-ref: SG valkey mở `0.0.0.0/0:6379` (CACHE.md:32) là vấn đề **security (Directive #1)**, tracked riêng — không thuộc ADR này.

---

## ADR-REL-005 - Triển khai Karpenter coexist-first cho Worker Nodes (CDO-99)
> Trạng thái: Chấp nhận
- **Ngày:** 2026-07-15
- **Người ký:** Phong (Rel Eng #1) · Kien (đồng quyết định)
- **Trụ:** Reliability + Cost
- **Bối cảnh:** ADR-REL-003 quyết định cài Cluster Autoscaler nhưng sau đó MNG đã chuyển sang scheduled scaling (2->3->2) để demonstrate baseline tĩnh. Dưới flash-sale Mandate-02 (200 user), tải có thể vượt baseline này bất kỳ lúc nào, cần cơ chế autoscaling thực sự tự động co giãn. Karpenter fit hơn vì node stateless hoàn toàn (RDS/Valkey đã tách), giúp bin-packing tốt hơn và scale-up nhanh (~30s, gọi trực tiếp EC2 Fleet API, không qua ASG).
- **Quyết định:** 
  1. Cấu hình Karpenter IAM bằng EKS Pod Identity (aws_eks_pod_identity_association) thay vì IRSA để đồng nhất với các controller mới.
  2. Tạo Karpenter Node Role (`ecommerce-dev-eks-karpenter-node`) + Instance Profile + EKS Access Entry (`EC2_LINUX`) để node tự join cluster.
  3. Deploy Karpenter Controller qua ArgoCD Helm chart `public.ecr.aws/karpenter/karpenter` (targetRevision: 1.0.1) trong `kube-system`.
  4. Cấu hình NodePool `default` chạy On-Demand duy nhất, giới hạn CPU tối đa `8` và instance types `2` hoặc `4` vCPU để kiểm soát chi phí. Consolidation set `WhenEmpty` để tránh node churn.
  5. Giữ nguyên MNG primary + ASG schedule hiện tại làm static fallback. Karpenter chỉ provision node phụ khi HPA tạo pod Pending vượt quá năng lực MNG.
- **Phương án khác đã cân:** A) Khôi phục Cluster Autoscaler (loại: scale thô theo node group, cấu hình tĩnh hơn). B) Bật Spot ngay lập tức (loại: cần SQS queue + EventBridge rules để handle Spot interruption, tăng rủi ro SLO lúc đầu, lùi lại Phase 3).
- **Cost Δ:** $0 trực tiếp; Karpenter chỉ launch node khi tải tăng và tự thu hồi node trống → tối ưu hóa chi phí thực tế. Trần CPU limit = 8 khống chế chi phí tối đa ~$40/tuần.
- **Ảnh hưởng SLO:** Node up nhanh khi pod Pending → giữ SLO checkout >=99% / cart >=99.5%. Consolidation chỉ kích hoạt khi node trống (`WhenEmpty`) → giảm thiểu tối đa rủi ro pod bị evict gây latency/error blips.
- **Rollback:** Xóa các ArgoCD application `karpenter` + `karpenter-nodepool`; disable resource trong terraform. Workload tự động schedule về MNG primary.
- **Hệ quả:** ✅ Node co giãn nhanh theo nhu cầu pod, cost tối ưu theo tải thực · ⚠️ Cần theo dõi logs/events của Karpenter và chuẩn bị SQS/EventBridge nếu muốn nâng cấp Spot ở Phase 3.

---

> Thêm ADR mới ở dưới. ADR bị thay thế: đổi Trạng thái + link forward, giữ nguyên nội dung cũ.
