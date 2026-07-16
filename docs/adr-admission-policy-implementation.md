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
| `gatekeeper/ConstraintTemplate/k8s-psp-capabilities.yaml` | `K8sPSPCapabilities` |

**Constraints** (binding + enforce):

| File | enforcementAction |
|---|---|
| `gatekeeper/constraints/constraint-run-as-non-root.yaml` | `deny` |
| `gatekeeper/constraints/constraint-deny-privilege-escalation.yaml` | `deny` |
| `gatekeeper/constraints/constraint-psp-capabilities.yaml` | `dryrun` |

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

> **Cập nhật 15/07/2026**: test package đặt tại **`tests/gatekeeper/`** (không phải
> `gatekeeper/tests/` như bản trước). Bỏ `namespace-policy-test.yaml`: cả 5 Constraint chỉ
> `match.namespaces: [techx-tf1]`, nên apply bad pod vào namespace test riêng sẽ PASS oan
> (false negative). Bad pod nhắm thẳng `techx-tf1` — deny tại admission nghĩa là **không có
> object nào được tạo**, an toàn cho namespace prod, không cần cleanup. Mở rộng từ 3 lên
> **5 negative test** để mỗi policy đang deny có đúng 1 bằng chứng reject.

### 6.1. Files đã chuẩn bị

Mỗi file negative vi phạm **đúng 1 luật** (các field còn lại hợp lệ) để deny message chỉ rõ luật nào bắn.

| File | Loại | Vi phạm | Constraint chặn |
|---|---|---|---|
| `tests/gatekeeper/neg-01-root.yaml` | Bad Pod | `runAsUser: 0` | `run-as-non-root` |
| `tests/gatekeeper/neg-02-image-latest.yaml` | Bad Pod | Image `nginx:latest` | `deny-floating-image-tag` |
| `tests/gatekeeper/neg-03-missing-resources.yaml` | Bad Pod | Không khai báo `resources` | `require-cpu-memory-limits-requests` |
| `tests/gatekeeper/neg-04-privilege-escalation.yaml` | Bad Pod | `allowPrivilegeEscalation: true` | `deny-privilege-escalation` |
| `tests/gatekeeper/neg-05-added-capabilities.yaml` | Bad Pod | `capabilities.add: [SYS_ADMIN]` | `psp-capabilities` |
| `tests/gatekeeper/pos-01-valid.yaml` | Good Pod | Hợp lệ cả 5 luật — phải PASS | — |
| `tests/gatekeeper/README.md` | Hướng dẫn | Lệnh chạy + expected deny message chi tiết | — |

### 6.2. Commands Mentor Thực hiện

```bash
# Bước 0: Xác nhận Gatekeeper controller đang chạy
kubectl get pods -n gatekeeper-system

# Bước 1: Apply ConstraintTemplates (định nghĩa luật)
kubectl apply -f gatekeeper/ConstraintTemplate/

# Bước 2: Apply Constraints (bật enforce); xác nhận đủ 5 constraint
kubectl apply -f gatekeeper/constraints/
kubectl get constraints

# Bước 3: Negative tests — TỪNG LỆNH expect "Error from server (Forbidden)"
kubectl apply -f tests/gatekeeper/neg-01-root.yaml
kubectl apply -f tests/gatekeeper/neg-02-image-latest.yaml
kubectl apply -f tests/gatekeeper/neg-03-missing-resources.yaml
kubectl apply -f tests/gatekeeper/neg-04-privilege-escalation.yaml
kubectl apply -f tests/gatekeeper/neg-05-added-capabilities.yaml

# Bước 4: Positive test — expect PASS (server dry-run, không tạo pod thật)
kubectl apply --dry-run=server -f tests/gatekeeper/pos-01-valid.yaml

# Bước 5: Xác nhận cluster không còn workload vi phạm (audit của Gatekeeper)
kubectl get constraints   # kỳ vọng TOTAL-VIOLATIONS = 0 ở cả 5 dòng
```

### 6.3. Expected Deny Messages

Nguyên văn theo Rego trong `gatekeeper/ConstraintTemplate/` của repo này (prefix
`Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request:`
ở mọi message, lược bớt bên dưới cho gọn):

**neg-01-root.yaml** — chạy root (`runAsUser: 0`):
```
[run-as-non-root] Container neg-root is attempting to run as disallowed user 0.
Allowed runAsUser: {"rule": "MustRunAsNonRoot"}
```

**neg-02-image-latest.yaml** — tag di động:
```
[deny-floating-image-tag] container <neg-latest> uses a disallowed tag <nginx:latest>;
disallowed tags are ["latest", "dev", "master", "main", "stable", "edge"]
```

**neg-03-missing-resources.yaml** — thiếu resources (ra 2 dòng: limits + requests):
```
[require-cpu-memory-limits-requests] container <neg-noresources> does not have <{"cpu", "memory"}> limits defined
[require-cpu-memory-limits-requests] container <neg-noresources> does not have <{"cpu", "memory"}> requests defined
```

**neg-04-privilege-escalation.yaml** — cho phép leo thang đặc quyền:
```
[deny-privilege-escalation] Privilege escalation container is not allowed: neg-privesc
```

**neg-05-added-capabilities.yaml** — add capability nguy hiểm:
```
[psp-capabilities] container <neg-caps> has a disallowed capability. Allowed capabilities are ["NET_BIND_SERVICE"]
```

**pos-01-valid.yaml** — manifest hợp lệ:
```
pod/pos-01-valid created (server dry run)
```

### 6.4. Cleanup

**Không cần cleanup.** Bad pod bị từ chối tại admission → không object nào được tạo.
Positive test chạy `--dry-run=server` → cũng không tạo pod thật. Namespace `techx-tf1`
không bị ảnh hưởng bởi bất kỳ bước test nào.

---

## 7. Kế hoạch Khôi phục (Rollback Plan)

* Nếu policy chặn nhầm workload thật, gây tắc nghẽn CI/CD:
  * **Cách thực hiện**: Chuyển `enforcementAction` của Constraint liên quan từ `deny` về `dryrun`. Không cần gỡ bỏ OPA Gatekeeper.

```bash
# Rollback về audit mode — thực hiện ngay, không downtime
for constraint in \
  run-as-non-root \
  deny-privilege-escalation \
  psp-capabilities \
  deny-floating-image-tag \
  require-cpu-memory-limits-requests; do
  kubectl patch constraint $constraint \
    --type=merge -p '{"spec":{"enforcementAction":"dryrun"}}'
done
```

  * **Quy trình phê duyệt**: Rollback chỉ được thực hiện khi có sự đồng ý của Security Lead (Châu Thành Trung). Sau rollback, reopen task liên quan để sửa policy hoặc bổ sung `securityContext` cho service trước khi bật `deny` lại.

