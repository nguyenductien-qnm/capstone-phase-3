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
> Trạng thái: Chấp nhận
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

---

> Thêm ADR mới ở dưới. ADR bị thay thế: đổi Trạng thái + link forward, giữ nguyên nội dung cũ.
