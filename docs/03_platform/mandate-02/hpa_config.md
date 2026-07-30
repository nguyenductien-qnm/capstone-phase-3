# CDO-42 — HPA + ResourceQuota + LimitRange (Evidence + ADR)

> **Task:** Bổ sung HPA, ResourceQuota, LimitRange cho namespace (auto-scale + khóa trần tài nguyên).
> **Assignee:** Le Trung Kien / CDO-09 · **Status Jira:** In Progress
> **Driver:** MANDATE-02 (flash-sale 200 user/15′ giữ SLO, KHÔNG vượt trần ~$300/tuần, "co lên rồi co xuống").

---

## 1. Đã làm gì (deliverable)

Tất cả quản lý bằng Helm để **ArgoCD tự sync** (GitOps), không apply thủ công.

| # | Thành phần | File |
|---|---|---|
| 1 | **LimitRange** (default/defaultRequest/max mỗi container) | `platform/charts/application/templates/resource-governance.yaml` |
| 2 | **ResourceQuota** (trần cứng namespace) | cùng file trên |
| 3 | **CPU requests** cho 8 hot-path service (blocker của HPA) | `platform/charts/application/values.yaml` |
| 4 | **HPA** `autoscaling/v2` CPU-only, behavior fast-up/slow-down | `platform/charts/application/templates/hpa.yaml` |
| 5 | Values-driven config + schema | `values.yaml` (`resourceGovernance`, `default.hpa`, per-component `hpa`) + `values.schema.json` |
| 6 | Loại bỏ quota rời (con trỏ) | `platform/policies/resource-governance/quota.yaml` |

**Services bật HPA (hot-path flash-sale):** frontend-proxy, frontend, cart, checkout, currency, product-catalog, recommendation, ad.

## 2. Vì sao thứ tự này: Governance → requests → HPA

- **HPA CPU tính theo % của CPU *request*.** Trước đó gần như mọi service chỉ có `limits.memory`, **không có CPU request** → HPA sẽ báo `<unknown>` và không scale. Đây là **blocker thật**, phải fix trước.
- **LimitRange** đảm bảo *mọi* pod (kể cả pod AIO push lên mà quên khai) có CPU request mặc định → HPA luôn có mẫu số để tính, và ResourceQuota không bị pod "trần trụi" phá.
- **ResourceQuota** là **trần cứng** chặn HPA scale vượt ngân sách. Phải có *trước* khi mở autoscale (MANDATE-02: không phình cost khi scale).

## 3. Thiết kế HPA — perf ⇄ cost

- **Metric: CPU-only**, `targetCPUUtilizationPercentage: 70`. (Không dùng memory làm metric vì nhiều Go service có mem limit rất chặt 20Mi + GOMEMLIMIT → memory-HPA dễ flap.)
- **behavior (dùng chung ở `default.hpa`):**
  - *scale-UP nhanh:* `stabilizationWindowSeconds: 0`, +100%/lần hoặc +2 pod mỗi 30s (`selectPolicy: Max`) → bắt kịp burst flash-sale.
  - *scale-DOWN chậm:* `stabilizationWindowSeconds: 300`, -1 pod/60s (`selectPolicy: Min`) → "co xuống" mượt, không thrash, trả tài nguyên về sau đỉnh.
- **minReplicas:**
  - **=2 cho service có PDB (CDO-34):** frontend-proxy, frontend, cart, checkout, product-catalog. Lý do **INC-2**: nếu min=1, lúc tải thấp HPA co về 1 pod → đúng lúc Karpenter (CDO-99) consolidate node → giết pod duy nhất → downtime. PDB (`minAvailable`) **vô nghĩa khi chỉ 1 pod**. min=2 để PDB giữ được 1 available khi node bị thu hồi. (Reliability thắng cost ở service có PDB.)
  - **=1 cho service không PDB:** currency, recommendation, ad (rẻ, đúng tinh thần co xuống).
- **maxReplicas:** 4–6 tùy service, chặn dưới ResourceQuota.

## 4. Kiểm chứng ngân sách (MANDATE-02)

CPU request theo replica (cores):

| | Baseline (min) | Peak (tất cả ở max) |
|---|---|---|
| Tổng CPU requests | **1.10** | **3.45** |
| ResourceQuota `requests.cpu` (trần cứng) | 4.00 | 4.00 |

*(Baseline 1.10 cores sau khi nâng min=2 cho 5 service có PDB; trước đó min=1 toàn bộ = 0.75.)*

→ Peak **3.45 < 4.00 cores**: HPA có room scale cho flash-sale **mà không bao giờ vượt trần quota**. Quota là ceiling — HPA không thể phá.

## 5. Evidence render (offline, helm v3.16.3)

```
$ helm lint . -f ../../gitops/environments/sandbox/values-flagd-sync.yaml
1 chart(s) linted, 0 chart(s) failed

$ helm template techx-corp . -f .../values-flagd-sync.yaml
# 8 × HorizontalPodAutoscaler: ad, cart, checkout, currency,
#     frontend, frontend-proxy, product-catalog, recommendation
# 1 × ResourceQuota (techx-corp-quota)
# 1 × LimitRange (techx-corp-limits)
# CPU requests present on all 8 hot-path Deployments
```

## 6. Kiểm tra cluster thực tế (2026-07-13)

Verify trực tiếp trên `ecommerce-dev-eks` (ns deploy = `techx-tf1`):

- ❌ **metrics-server KHÔNG có sẵn** — `deploy metrics-server` not found, API `v1beta1.metrics.k8s.io` không tồn tại, `kubectl top nodes` = "Metrics API not available". **→ HPA sẽ `<unknown>/70%` cho tới khi cài.**
  - metrics-server = add-on kube-system, thu CPU/mem thực từ kubelet → expose API `metrics.k8s.io` mà **HPA đọc để tính %**. Không phải Prometheus (observability), không phải Karpenter (node autoscaling).
  - **Không có Jira task riêng.** CDO-99 (Karpenter, Mạnh Khang) là *node* autoscaling — khác tầng, không cấp metrics-server. → xử lý như **dependency của CDO-42**.
  - ✅ **Đã thêm** metrics-server làm ArgoCD Application (App-of-Apps): `platform/gitops/applications/metrics-server.yaml` (chart 3.12.2 = app v0.7.2, `--kubelet-insecure-tls` cho EKS). root-app tự sync sau khi merge lên `develop`.
- ✅ **ArgoCD Healthy/Synced** — `techx-corp` + `techx-corp-root`, track `develop`, dest `techx-tf1`.
- ⚠️ Code CDO-42 đang ở working tree, **chưa lên `develop`** → cluster chưa có HPA/Quota/LimitRange, pod chưa có CPU request. Cần nhánh riêng → PR vào `develop`.

### Việc còn lại
- [ ] Merge lên `develop` → ArgoCD sync metrics-server + HPA/Quota/LimitRange.
- [ ] `kubectl top nodes` ra số; `kubectl get hpa -n techx-tf1` thấy `TARGETS %/70%` (không `<unknown>`).
- [ ] Đồng bộ **CDO-28 (Phong)**: HPA quản replica cart/checkout/product-catalog → bỏ replica tĩnh, tránh xung đột.
- [ ] (Sau) load-test 200 user/15′ → evidence SLO cho MANDATE-02.

## 7. Ranh giới với task khác

- **CDO-37 (Manh Khang, CPU requests/limits toàn diện):** tôi chỉ thêm CPU request cho **8 hot-path service** đủ để HPA chạy; sweep toàn bộ + tinh chỉnh limit là của CDO-37.
- **CDO-34 (Nguyen Dinh Thi, PDB):** min=2 cho 5 service có PDB (frontend-proxy, frontend, cart, checkout, product-catalog) — HPA `minReplicas` là điều kiện để PDB có ý nghĩa (INC-2).
- **CDO-28 (Phong, chỉnh replica cart/checkout/product-catalog):** **chồng lấn — HPA thay thế replica tĩnh.** Không được để cả `spec.replicas` cố định lẫn HPA cùng quản một Deployment (mỗi lần sync sẽ đánh nhau, pod flap). `minReplicas` của HPA đảm nhận vai trò "sàn replica" của CDO-28. → thống nhất với Phong: bỏ con số replica tĩnh cho 3 service này, để HPA cầm lái.
- **CDO-47 (ndtien317, probes):** HPA scale-up nhanh sẽ mượt hơn khi có readiness probe; nằm ở CDO-47.

---

## ADR-042 — Auto-scale hot-path bằng HPA CPU-only trong trần ResourceQuota

> Trạng thái: **Đề xuất**
- **Ngày:** 2026-07-13
- **Người ký:** Le Trung Kien / CDO-09
- **Trụ:** Performance / Cost (chạm Reliability)
- **Bối cảnh:** MANDATE-02 yêu cầu chịu flash-sale 200 user/15′ giữ SLO mà không tăng ngân sách. Hệ thống chưa có autoscale, và pod thiếu CPU request nên không thể HPA.
- **Quyết định:** HPA `autoscaling/v2` CPU-utilization 70% cho 8 hot-path service, behavior scale-up nhanh / scale-down chậm; LimitRange cấp CPU request mặc định; ResourceQuota làm trần cứng. Tất cả trong Helm để ArgoCD sync.
- **Phương án khác đã cân:** (A) HPA theo memory — loại vì mem limit quá chặt, dễ flap. (B) Custom metric RPS/p95 qua prometheus-adapter — loại (tuần này) vì phải cài thêm hạ tầng, vượt scope. (C) Tăng replica cố định — loại vì neo cost ở đỉnh, phá "co xuống".
- **Cost Δ:** Baseline 1.10 cores (min=2 cho 5 service có PDB). Peak request 3.45 cores < trần quota 4 cores → không phình vượt ngân sách. Không thêm dịch vụ trả phí.
- **Ảnh hưởng SLO:** Kỳ vọng cải thiện checkout/browse SLO khi burst (thêm pod). Verify bằng load-test 200 user (Pha B).
- **Rollback:** Set `hpa.enabled: false` (hoặc `resourceGovernance.*.enabled: false`) trong values → ArgoCD tự gỡ HPA/quota, Deployment về replica tĩnh. Rollback qua git revert PR. Kích hoạt nếu HPA flap hoặc quota chặn nhầm workload hợp lệ.
- **Hệ quả:** ✅ Autoscale bám tải, cost có trần cứng, GitOps-clean. ⚠️ Phụ thuộc metrics-server (chưa verify trên cluster); CPU request mới cần theo dõi để không đội baseline.
