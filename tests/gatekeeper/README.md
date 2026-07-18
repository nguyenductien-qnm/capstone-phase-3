# Native ValidatingAdmissionPolicy Negative-Test Package (Directive #5 — Runtime Hardening)

Bộ manifest để mentor **tự apply và tận mắt thấy bị từ chối** bởi 5 Kubernetes native ValidatingAdmissionPolicies (VAP) áp dụng toàn cluster.

**Thiết kế:** mỗi file negative vi phạm **đúng 1 luật** — mọi field còn lại hợp lệ — để deny message chỉ ra chính xác luật nào bắn. Vì pod vi phạm bị từ chối **ngay tại admission**, không có gì được tạo ra trong cluster → không cần dọn dẹp sau test. Pod hợp lệ (positive) kiểm bằng `--dry-run=server` nên cũng không tạo pod thật.

## Điều kiện tiên quyết

```bash
# 5 ValidatingAdmissionPolicy + 5 ValidatingAdmissionPolicyBinding đã apply (từ thư mục gốc capstone-phase-3/)
kubectl apply -f vap/

# Xác nhận đủ 5 policy và binding:
kubectl get validatingadmissionpolicy
kubectl get validatingadmissionpolicybinding
```

## Danh sách test

| File | Vi phạm | Policy chặn | Kỳ vọng |
|---|---|---|:--:|
| `neg-01-root.yaml` | `runAsUser: 0` (chạy root) | `run-as-non-root` | ❌ REJECT |
| `neg-02-image-latest.yaml` | image `nginx:latest` (tag trôi) | `deny-floating-image-tag` | ❌ REJECT |
| `neg-03-missing-resources.yaml` | không khai `resources` | `require-resources` | ❌ REJECT |
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

## Deny message kỳ vọng

**neg-01** (`run-as-non-root`):
```
ValidatingAdmissionPolicy 'run-as-non-root' with binding 'run-as-non-root-binding' denied request: containers must run as non-root (runAsNonRoot: true or runAsUser != 0): neg-root
```

**neg-02** (`deny-floating-image-tag`):
```
ValidatingAdmissionPolicy 'deny-floating-image-tag' with binding 'deny-floating-image-tag-binding' denied request: container has disallowed image tag or no tag specified: neg-latest (nginx:latest)
```

**neg-03** (`require-resources`):
```
ValidatingAdmissionPolicy 'require-resources' with binding 'require-resources-binding' denied request: containers must have CPU and Memory requests and limits defined: neg-noresources
```

**neg-04** (`deny-privilege-escalation`):
```
ValidatingAdmissionPolicy 'deny-privilege-escalation' with binding 'deny-privilege-escalation-binding' denied request: containers must have allowPrivilegeEscalation set to false: neg-privesc
```

**neg-05** (`psp-capabilities`):
```
ValidatingAdmissionPolicy 'psp-capabilities' with binding 'psp-capabilities-binding' denied request: containers must drop ALL capabilities and can only add NET_BIND_SERVICE: neg-caps
```

## Ghi chú

- Deny tại admission nghĩa là **không có object nào được tạo** — an toàn tuyệt đối, không đụng workload thật, không cần rollback.
- Image dùng `busybox:1.38.0` / `nginx:latest` — không cần pull image về vì pod bị chặn trước khi scheduler/kubelet chạy.
