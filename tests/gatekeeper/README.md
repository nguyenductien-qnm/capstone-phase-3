# Gatekeeper Negative-Test Package (Directive #5 — Runtime Hardening)

Bộ manifest để mentor **tự apply và tận mắt thấy bị từ chối** bởi 5 policy Gatekeeper
(`enforcementAction: deny`, namespace `techx-tf1`). Tham chiếu: ADR-002, ADR-003, IMPL-001 §6.

**Thiết kế:** mỗi file negative vi phạm **đúng 1 luật** — mọi field còn lại hợp lệ — để deny
message chỉ ra chính xác luật nào bắn. Vì pod vi phạm bị từ chối **ngay tại admission**, không
có gì được tạo ra trong namespace prod → không cần dọn dẹp sau test. Pod hợp lệ (positive)
kiểm bằng `--dry-run=server` nên cũng không tạo pod thật.

## Điều kiện tiên quyết

```bash
# Gatekeeper controller đang chạy
kubectl get pods -n gatekeeper-system

# 5 ConstraintTemplate + 5 Constraint đã apply (từ thư mục gốc capstone-phase-3/)
kubectl apply -f gatekeeper/ConstraintTemplate/
kubectl apply -f gatekeeper/constraints/

# Đợi template được compile (vài giây), xác nhận đủ 5 constraint, tất cả deny:
kubectl get constraints
```

## Danh sách test

| File | Vi phạm | Constraint chặn | Kỳ vọng |
|---|---|---|:--:|
| `neg-01-root.yaml` | `runAsUser: 0` (chạy root) | `run-as-non-root` | ❌ REJECT |
| `neg-02-image-latest.yaml` | image `nginx:latest` (tag trôi) | `deny-floating-image-tag` | ❌ REJECT |
| `neg-03-missing-resources.yaml` | không khai `resources` | `require-cpu-memory-limits-requests` | ❌ REJECT |
| `neg-04-privilege-escalation.yaml` | `allowPrivilegeEscalation: true` | `deny-privilege-escalation` | ❌ REJECT |
| `neg-05-added-capabilities.yaml` | `capabilities.add: [SYS_ADMIN]` | `psp-capabilities` | ❌ REJECT |
| `pos-01-valid.yaml` | không vi phạm gì (pass cả 5 luật) | — | ✅ PASS |

## Lệnh chạy (từ thư mục gốc `capstone-phase-3/`)

```bash
# Negative tests — TỪNG LỆNH phải trả về "Error from server (Forbidden)":
kubectl apply -f tests/gatekeeper/neg-01-root.yaml
kubectl apply -f tests/gatekeeper/neg-02-image-latest.yaml
kubectl apply -f tests/gatekeeper/neg-03-missing-resources.yaml
kubectl apply -f tests/gatekeeper/neg-04-privilege-escalation.yaml
kubectl apply -f tests/gatekeeper/neg-05-added-capabilities.yaml

# Positive test — phải PASS (server-side dry-run, không tạo pod thật):
kubectl apply --dry-run=server -f tests/gatekeeper/pos-01-valid.yaml
# Kỳ vọng: pod/pos-01-valid created (server dry run)
```

## Deny message kỳ vọng (nguyên văn từ Rego trong ConstraintTemplate)

**neg-01** (`run-As-Non-Root.yaml`):
```
Error from server (Forbidden): ... admission webhook "validation.gatekeeper.sh" denied the request:
[run-as-non-root] Container neg-root is attempting to run as disallowed user 0.
Allowed runAsUser: {"rule": "MustRunAsNonRoot"}
```

**neg-02** (`reject-floating-image-tag.yaml`):
```
[deny-floating-image-tag] container <neg-latest> uses a disallowed tag <nginx:latest>;
disallowed tags are ["latest", "dev", "master", "main", "stable", "edge"]
```

**neg-03** (`k8s-required-resources.yaml` — ra 2 dòng, thiếu cả limits lẫn requests):
```
[require-cpu-memory-limits-requests] container <neg-noresources> does not have <{"cpu", "memory"}> limits defined
[require-cpu-memory-limits-requests] container <neg-noresources> does not have <{"cpu", "memory"}> requests defined
```

**neg-04** (`allow-Privilege-Escalation.yaml`):
```
[deny-privilege-escalation] Privilege escalation container is not allowed: neg-privesc
```

**neg-05** (`k8s-psp-capabilities.yaml`):
```
[psp-capabilities] container <neg-caps> has a disallowed capability. Allowed capabilities are ["NET_BIND_SERVICE"]
```

> Wording có thể lệch nhẹ theo version Gatekeeper (phần prefix `Error from server`);
> phần trong `[...]` và nội dung message lấy đúng từ Rego của repo này.

## Xác nhận cluster đang chạy không còn workload vi phạm

```bash
# Tổng số vi phạm còn tồn tại theo từng constraint (audit định kỳ của Gatekeeper).
# Kỳ vọng: TOTAL-VIOLATIONS = 0 ở cả 5 dòng.
kubectl get constraints

# Nếu có vi phạm, xem chi tiết pod nào:
kubectl get constraint <tên-constraint> -o jsonpath='{.status.violations}' | jq
```

## Ghi chú

- Bad pod nhắm thẳng vào `techx-tf1` là **chủ ý**: chứng minh policy chặn ở đúng namespace
  prod. Deny tại admission nghĩa là **không có object nào được tạo** — an toàn tuyệt đối,
  không đụng workload thật, không cần rollback.
- Không dùng namespace test riêng vì cả 5 Constraint chỉ `match.namespaces: [techx-tf1]` —
  apply vào namespace khác sẽ PASS oan (false negative), làm demo mất giá trị.
- Image dùng `busybox:1.38.0` / `nginx:latest` — không cần pull image về vì pod bị chặn
  trước khi scheduler/kubelet chạy (riêng pos-01 là dry-run).
