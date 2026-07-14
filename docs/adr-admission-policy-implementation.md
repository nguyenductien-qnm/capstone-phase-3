# Implementation Record: Admission Policy — Runtime Hardening (M5-03, M5-08, M5-09, M5-10, M5-15)

**Mã tài liệu**: CDO-SEC-IMPL-001  
**Trạng thái**: Hoàn thành (Implemented)  
**Tác giả**: Nguyễn Khánh Duy (SRE Lead)  
**Ngày thực hiện**: 14/07/2026  
**Tham chiếu ADR**: [CDO-SEC-ADR-002](./adr-admission-policy.md) · [CDO-SEC-ADR-003](./adr-runtime-hardening.md)

---

## 1. Bối cảnh & Yêu cầu (Context)

Theo quyết định tại **CDO-SEC-ADR-002**, nhóm CDO-05 lựa chọn **OPA Gatekeeper** làm Admission Controller để thực thi **Directive #5 (Runtime Hardening)**. Tài liệu này ghi lại chi tiết những gì đã được triển khai cho 5 work items thuộc Mandate 5, bao gồm manifest policy, test package và kế hoạch khôi phục.

* **Policy Engine**: OPA Gatekeeper (`ConstraintTemplate` + `Constraint` CRDs, ngôn ngữ Rego)
* **Namespace áp dụng**: `techx-tf1`
* **Namespace loại trừ**: `kube-system`, `gatekeeper-system`, `argocd`
* **Enforcement mode**: `enforcementAction: deny` (chặn thật sự)

---

## 2. M5-03 — Inventory Resources Requests/Limits

### 2.1. Kết quả Rà soát
Rà soát toàn bộ workload trong cluster trước khi bật policy bắt buộc (M5-10), xác định baseline thực tế:

* `values.yaml` toàn cục đang đặt `securityContext: {}` — không có resource declaration mặc định.
* Các service **chưa** có `resources.requests` / `resources.limits`: `checkout`, `cart`, `product-catalog`, `currency`, `payment`.
* Chỉ ~6 component đã đặt `runAsNonRoot: true` tường minh: `frontend`, `frontend-proxy/envoy`, `product-reviews`, `image-provider`, `valkey`.

### 2.2. Rủi ro Xác định
* Pod bị rò rỉ bộ nhớ có thể chiếm hết tài nguyên Node, kéo sập dịch vụ khác (noisy neighbor).
* Kubernetes Scheduler không thể tối ưu bin-packing nếu thiếu resource declaration.

**Tài liệu liên quan**: [`docs/security-inventory.md`](./security-inventory.md)

---

## 3. M5-08 — Policy: Chặn Root & Privilege Escalation

### 3.1. Policy Intent
* Reject container không có `runAsNonRoot: true`.
* Reject container có `allowPrivilegeEscalation: true` (hoặc không set về `false`).
* Reject container không drop Linux capabilities (`drop: ALL` bắt buộc).

### 3.2. Files đã triển khai

**ConstraintTemplates** (định nghĩa luật — viết bằng Rego):

| File | Kind |
|---|---|
| `gatekeeper/ConstraintTemplate/run-As-Non-Root.yaml` | `K8sPSPAllowedUsers` |
| `gatekeeper/ConstraintTemplate/allow-Privilege-Escalation.yaml` | `K8sPSPAllowPrivilegeEscalationContainer` |
| `gatekeeper/ConstraintTemplate/k8s-disallow-capabilities.yaml` | `K8sDisallowCapabilities` |

**Constraints** (binding + enforce):

| File | enforcementAction |
|---|---|
| `gatekeeper/constraints/constraint-run-as-non-root.yaml` | `deny` |
| `gatekeeper/constraints/constraint-deny-privilege-escalation.yaml` | `deny` |
| `gatekeeper/constraints/constraint-deny-capabilities.yaml` | `deny` |

### 3.3. Acceptance Criteria
* Manifest không có `runAsNonRoot: true` → **bị reject**.
* Manifest có `allowPrivilegeEscalation: true` → **bị reject**.
* Container không `drop: ALL` → **bị reject**.
* Workload hợp lệ (đủ securityContext) → **được allow**.

### 3.4. Exception đã đăng ký
| Workload | Namespace | Lý do |
|---|---|---|
| `DaemonSet/otel-collector-agent` | `techx-tf1` | Cần root + HostNetwork để thu thập log/metrics từ Host |
| `Deployment/grafana` (sidecars) | `techx-tf1` | Container `k8s-sidecar` cần ghi file vào EmptyDir chung |

---

## 4. M5-09 — Policy: Chặn Image Latest/Floating

### 4.1. Policy Intent
* Reject image dùng tag: `latest`, `dev`, `master`, `main`, `stable`, `edge`.
* Reject image không có tag (vd: `nginx` không có `:tag`).
* Cho phép tag cố định (vd: `nginx:1.27`, `1.1-checkout`) hoặc image digest.
* Áp dụng cho `containers`, `initContainers`, `ephemeralContainers`.

### 4.2. Files đã triển khai

| File | Loại |
|---|---|
| `gatekeeper/ConstraintTemplate/reject-floating-image-tag.yaml` | `K8sDisallowedTags` |
| `gatekeeper/constraints/constraint-deny-floating-tag.yaml` | Constraint — `deny` |

### 4.3. Acceptance Criteria
* `nginx:latest` → **bị reject**.
* `nginx` (không tag) → **bị reject**.
* `public.ecr.aws/docker/library/nginx:1.27` → **được allow**.
* Deny message hiển thị rõ image và tag vi phạm.

### 4.4. Ghi chú
Convention tag CI pipeline hiện tại (`<version>-<service>`, vd `1.1-checkout`) **không bị ảnh hưởng** — policy củng cố convention có sẵn, không phá pipeline.

---

## 5. M5-10 — Policy: Bắt Buộc Resources Requests/Limits

### 5.1. Policy Intent
* Require `resources.requests.cpu`
* Require `resources.requests.memory`
* Require `resources.limits.cpu`
* Require `resources.limits.memory`
* Áp dụng cho `containers` và `initContainers`.

### 5.2. Files đã triển khai

| File | Loại |
|---|---|
| `gatekeeper/ConstraintTemplate/k8s-required-resources.yaml` | `K8sRequiredResources` |
| `gatekeeper/constraints/constraint-required-resources.yaml` | Constraint — `deny` |

### 5.3. Acceptance Criteria
* Container thiếu bất kỳ field nào trong 4 fields trên → **bị reject**.
* Container có đủ 4 fields → **được allow**.
* Không conflict với LimitRange/ResourceQuota hiện có.

---

## 6. M5-15 — Mentor Negative Test Package

### 6.1. Files đã chuẩn bị

| File | Loại | Vi phạm |
|---|---|---|
| `gatekeeper/tests/namespace-policy-test.yaml` | Namespace | — (namespace test riêng biệt) |
| `gatekeeper/tests/neg-01-root.yaml` | Bad Pod | Không có `runAsNonRoot: true` |
| `gatekeeper/tests/neg-02-image-latest.yaml` | Bad Pod | Image `nginx:latest` |
| `gatekeeper/tests/neg-03-missing-resources.yaml` | Bad Pod | Không khai báo `resources` |
| `gatekeeper/tests/pos-01-valid.yaml` | Good Pod | Hợp lệ toàn bộ — phải PASS |

### 6.2. Commands Mentor Thực hiện

```bash
# Bước 1: Apply ConstraintTemplates (định nghĩa luật)
kubectl apply -f gatekeeper/ConstraintTemplate/

# Bước 2: Apply Constraints (bật enforce)
kubectl apply -f gatekeeper/constraints/

# Bước 3: Negative tests — expect REJECT
kubectl apply -f gatekeeper/tests/neg-01-root.yaml
kubectl apply -f gatekeeper/tests/neg-02-image-latest.yaml
kubectl apply -f gatekeeper/tests/neg-03-missing-resources.yaml

# Bước 4: Positive test — expect PASS
kubectl apply --dry-run=server -f gatekeeper/tests/pos-01-valid.yaml
```

### 6.3. Expected Deny Messages

**neg-01-root.yaml** — vi phạm `runAsNonRoot`:
```
Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request:
[run-as-non-root] Container neg-root is attempting to run without a required
securityContext/runAsNonRoot or securityContext/runAsUser != 0
```

**neg-02-image-latest.yaml** — vi phạm image tag:
```
Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request:
[deny-floating-image-tag] container <app> uses a disallowed tag <nginx:latest>;
disallowed tags are ["latest", "dev", "master", "main", "stable", "edge"]
```

**neg-03-missing-resources.yaml** — vi phạm resources:
```
Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request:
[require-cpu-memory-limits-requests] container <app> does not have <{"cpu", "memory"}> limits defined
container <app> does not have <{"cpu", "memory"}> requests defined
```

**pos-01-valid.yaml** — manifest hợp lệ:
```
pod/pos-valid created
```

### 6.4. Cleanup Commands

```bash
# Xóa pod test (nếu pos-01 đã apply thật)
kubectl delete pod pos-valid -n techx-tf1 --ignore-not-found

# Xóa toàn bộ nếu dùng namespace riêng
kubectl delete ns policy-test
```

---

## 7. Kế hoạch Khôi phục (Rollback Plan)

* Nếu policy chặn nhầm workload thật, gây tắc nghẽn CI/CD:
  * **Cách thực hiện**: Chuyển `enforcementAction` của Constraint liên quan từ `deny` về `dryrun`. Không cần gỡ bỏ OPA Gatekeeper.

```bash
# Rollback về audit mode — thực hiện ngay, không downtime
for constraint in \
  run-as-non-root \
  deny-privilege-escalation \
  deny-dangerous-capabilities \
  deny-floating-image-tag \
  require-cpu-memory-limits-requests; do
  kubectl patch constraint $constraint \
    --type=merge -p '{"spec":{"enforcementAction":"dryrun"}}'
done
```

  * **Quy trình phê duyệt**: Rollback chỉ được thực hiện khi có sự đồng ý của Security Lead (Châu Thành Trung). Sau rollback, reopen task liên quan để sửa policy hoặc bổ sung `securityContext` cho service trước khi bật `deny` lại.

