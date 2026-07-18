# Implementation Record: Admission Policy — Runtime Hardening (M5-03, M5-08, M5-09, M5-10, M5-15)

**Mã tài liệu**: CDO-SEC-IMPL-001  
**Trạng thái**: Hoàn thành (Implemented)  
**Tác giả**: Nguyễn Khánh Duy (SRE Lead)  
**Ngày thực hiện**: 18/07/2026  
**Tham chiếu ADR**: [CDO-SEC-ADR-002](./adr-admission-policy.md) · [CDO-SEC-ADR-003](./adr-runtime-hardening.md)

---

## 1. Bối cảnh & Yêu cầu (Context)

Theo quyết định tại **CDO-SEC-ADR-002**, nhóm CDO-05 lựa chọn **Kubernetes ValidatingAdmissionPolicy (VAP)** làm Admission Controller để thực thi **Directive #5 (Runtime Hardening)**. Tài liệu này ghi lại chi tiết những gì đã được triển khai cho 5 work items thuộc Mandate 5, bao gồm các file manifest VAP, test package và kế hoạch khôi phục.

* **Policy Engine**: Kubernetes ValidatingAdmissionPolicy & ValidatingAdmissionPolicyBinding (ngôn ngữ CEL)
* **Namespace áp dụng**: Toàn bộ cluster (Cluster-wide)
* **Namespace loại trừ**: `kube-system`, `kube-public`, `kube-node-lease`, `gatekeeper-system`, `argocd` (qua `namespaceSelector`)
* **Enforcement mode**: `validationActions: [Deny]` (chặn thật sự)

---

## 2. M5-03 — Inventory Resources Requests/Limits

### 2.1. Kết quả Rà soát
Rà soát toàn bộ workload trong cụm trước khi bật policy bắt buộc, xác định baseline thực tế:
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
* Reject container không có `runAsNonRoot: true` hoặc `runAsUser != 0`.
* Reject container có `allowPrivilegeEscalation: true` (hoặc không set về `false`).
* Reject container không drop Linux capabilities (`drop: ALL` bắt buộc).

### 3.2. Files đã triển khai (VAP)

| File | Policy Name |
|---|---|
| `vap/run-as-non-root.yaml` | `run-as-non-root` |
| `vap/deny-privilege-escalation.yaml` | `deny-privilege-escalation` |
| `vap/psp-capabilities.yaml` | `psp-capabilities` |

### 3.3. Acceptance Criteria
* Manifest không có `runAsNonRoot: true` hoặc `runAsUser > 0` → **bị reject**.
* Manifest có `allowPrivilegeEscalation: true` (hoặc thiếu) → **bị reject**.
* Container không `drop: ALL` → **bị reject**.
* Workload hợp lệ (đủ securityContext) → **được allow**.

### 3.4. Exception đã đăng ký
* `otel/opentelemetry-collector-contrib` (otel-collector-agent) được ngoại lệ cho các luật `run-as-non-root`, `deny-privilege-escalation` và `psp-capabilities`.
* `prometheus`, `jaeger` được ngoại lệ cho các luật `deny-privilege-escalation` và `psp-capabilities`.
* `opensearch` được ngoại lệ cho luật `deny-privilege-escalation`.

---

## 4. M5-09 — Policy: Chặn Image Latest/Floating

### 4.1. Policy Intent
* Reject image dùng tag: `latest`, `dev`, `master`, `main`, `stable`, `edge`.
* Reject image không có tag (vd: `nginx` không có `:tag`).
* Cho phép tag cố định (vd: `nginx:1.27`, `1.1-checkout`) hoặc image digest.
* Áp dụng cho `containers`, `initContainers`, `ephemeralContainers`.

### 4.2. Files đã triển khai

| File | Policy Name |
|---|---|
| `vap/deny-floating-image-tag.yaml` | `deny-floating-image-tag` |

### 4.3. Acceptance Criteria
* `nginx:latest` → **bị reject**.
* `nginx` (không tag) → **bị reject**.
* `public.ecr.aws/docker/library/nginx:1.27` → **được allow**.
* Deny message hiển thị rõ thông tin vi phạm.

---

## 5. M5-10 — Policy: Bắt Buộc Resources Requests/Limits

### 5.1. Policy Intent
* Require `resources.requests.cpu` & `resources.requests.memory`
* Require `resources.limits.cpu` & `resources.limits.memory`
* Áp dụng cho `containers` và `initContainers`.

### 5.2. Files đã triển khai

| File | Policy Name |
|---|---|
| `vap/require-resources.yaml` | `require-resources` |

### 5.3. Acceptance Criteria
* Container thiếu bất kỳ field nào trong 4 fields trên → **bị reject**.
* Container có đủ 4 fields → **được allow**.

---

## 6. M5-15 — Mentor Negative Test Package

Test package đặt tại **`tests/gatekeeper/`** (giữ nguyên đường dẫn cũ để khớp cấu trúc nộp bài của hệ thống, nhưng đã cập nhật mô tả VAP).

### 6.1. Files đã chuẩn bị

Mỗi file negative vi phạm **đúng 1 luật** (các field còn lại hợp lệ) để deny message chỉ rõ luật nào bắn.

| File | Loại | Vi phạm | Policy chặn |
|---|---|---|---|
| `tests/gatekeeper/neg-01-root.yaml` | Bad Pod | `runAsUser: 0` | `run-as-non-root` |
| `tests/gatekeeper/neg-02-image-latest.yaml` | Bad Pod | Image `nginx:latest` | `deny-floating-image-tag` |
| `tests/gatekeeper/neg-03-missing-resources.yaml` | Bad Pod | Không khai báo `resources` | `require-resources` |
| `tests/gatekeeper/neg-04-privilege-escalation.yaml` | Bad Pod | `allowPrivilegeEscalation: true` | `deny-privilege-escalation` |
| `tests/gatekeeper/neg-05-added-capabilities.yaml` | Bad Pod | `capabilities.add: [SYS_ADMIN]` | `psp-capabilities` |
| `tests/gatekeeper/pos-01-valid.yaml` | Good Pod | Hợp lệ cả 5 luật — phải PASS | — |
| `tests/gatekeeper/README.md` | Hướng dẫn | Lệnh chạy + expected deny message chi tiết | — |

### 6.2. Commands Mentor Thực hiện

```bash
# Bước 1: Deploy các ValidatingAdmissionPolicy
kubectl apply -f vap/

# Bước 2: Xác nhận các policy và binding đã active
kubectl get validatingadmissionpolicy
kubectl get validatingadmissionpolicybinding

# Bước 3: Negative tests — TỪNG LỆNH expect "Error from server (Forbidden)"
kubectl apply -f tests/gatekeeper/neg-01-root.yaml
kubectl apply -f tests/gatekeeper/neg-02-image-latest.yaml
kubectl apply -f tests/gatekeeper/neg-03-missing-resources.yaml
kubectl apply -f tests/gatekeeper/neg-04-privilege-escalation.yaml
kubectl apply -f tests/gatekeeper/neg-05-added-capabilities.yaml

# Bước 4: Positive test — expect PASS (server dry-run, không tạo pod thật)
kubectl apply --dry-run=server -f tests/gatekeeper/pos-01-valid.yaml
```

---

## 7. Kế hoạch Khôi phục (Rollback Plan)

* Nếu policy chặn nhầm workload thật, gây tắc nghẽn CI/CD:
  * **Cách thực hiện**: Xóa ValidatingAdmissionPolicyBinding tương ứng để tạm ngừng enforce chính sách ngay lập tức mà không cần xóa định nghĩa policy.

```bash
# Xóa binding để khôi phục deploy nhanh chóng
kubectl delete validatingadmissionpolicybinding deny-floating-image-tag-binding
kubectl delete validatingadmissionpolicybinding require-resources-binding
kubectl delete validatingadmissionpolicybinding run-as-non-root-binding
kubectl delete validatingadmissionpolicybinding deny-privilege-escalation-binding
kubectl delete validatingadmissionpolicybinding psp-capabilities-binding
```

  * **Quy trình phê duyệt**: Rollback chỉ được thực hiện khi có sự đồng ý của Security Lead (Châu Thành Trung).
