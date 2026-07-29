# MANDATE-05 — Runtime Hardening: Report triển khai

**Trạng thái:** Hoàn thành · **Ngày:** 2026-07-19 · **Môi trường test:** Develop (`458580846647` / `ecommerce-develop-dev-eks`, EKS 1.36)
**Tham chiếu:** [MANDATE-05](../../../mandates/MANDATE-05-runtime-hardening.md) · [ADR](../../adr-admission-policy-implementation.md)

---

## 1. Giải pháp

Dùng **Kubernetes ValidatingAdmissionPolicy (VAP)** làm admission controller — chạy native trong `kube-apiserver`, **không thêm pod/controller nào** → thỏa ràng buộc "không dựng thêm service, không tốn hạ tầng".

| # | Policy | Chặn |
|---|--------|------|
| 1 | `run-as-non-root` | Container chạy root (`runAsUser: 0` / thiếu `runAsNonRoot`) |
| 2 | `deny-privilege-escalation` | `allowPrivilegeEscalation != false` |
| 3 | `psp-capabilities` | Không `drop: ALL`; chỉ cho `add: NET_BIND_SERVICE` |
| 4 | `deny-floating-image-tag` | Tag trôi (`latest`, `dev`, `main`...) / không pin |
| 5 | `require-resources` | Thiếu requests/limits CPU & Memory |

- **Phạm vi:** cluster-wide. **Loại trừ:** `kube-system`, `kube-public`, `kube-node-lease`, `gatekeeper-system`, `argocd`.
- **Ngoại lệ workload:** otel-collector, kube-state-metrics, reloader, k8s-sidecar, aiops-detector/remediation, prometheus, jaeger, opensearch (theo image).
- **Enforcement:** `validationActions: [Deny]` — vi phạm bị **từ chối ngay lúc apply**.

## 2. Resource đã cấu hình

| Loại | Số lượng | Trạng thái |
|------|----------|-----------|
| ValidatingAdmissionPolicy | 5 | Active |
| ValidatingAdmissionPolicyBinding | 5 | Active |
| Pod/controller thêm mới | **0** | — |

**Manifest (GitOps):** `platform/policies/runtime-hardening/` (5 file)
**ArgoCD Application:** `platform/gitops/environments/develop/applications/runtime-hardening.yaml` — `sync-wave: -3` (active trước mọi workload), manual-sync theo posture Develop.

## 3. Kết quả test

Bộ 14 case chạy `--dry-run=server` (read-only) trên Develop, namespace `default`:

```
TỔNG KẾT:  PASS=14  FAIL=0  / 14 case
```

| Nhóm | Số case | Kết quả |
|------|---------|---------|
| `neg-*` (pod vi phạm) | 10 | ✅ Tất cả bị **Deny**, đúng luật |
| `pos-*` (pod hợp lệ / exempt) | 4 | ✅ Tất cả **qua** được |

Mode Deny short-circuit ở luật đầu tiên → case đa-vi-phạm chỉ hiện 1 luật (vẫn bị chặn đúng).
**Script:** `tests/vap/run-dry-run-tests.sh` · **Chạy:** `NS=default bash run-dry-run-tests.sh`

## 4. Rollback

Gỡ enforce ngay mà không xóa định nghĩa policy — xóa binding:

```bash
kubectl delete validatingadmissionpolicybinding \
  run-as-non-root-binding deny-privilege-escalation-binding \
  psp-capabilities-binding require-resources-binding deny-floating-image-tag-binding
```

## 5. Đối chiếu yêu cầu

| Yêu cầu MANDATE-05 | Đáp ứng |
|--------------------|---------|
| Không container chạy root | ✅ Policy 1 |
| Không image trôi | ✅ Policy 4 |
| Bắt buộc request/limit | ✅ Policy 5 |
| Enforce tự động ở admission | ✅ VAP mode Deny |
| Không dựng thêm service / tốn hạ tầng | ✅ 0 pod thêm mới |
| Manifest vi phạm bị từ chối lúc apply | ✅ 10/10 neg bị Deny |
