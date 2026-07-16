# Gatekeeper Policy Test Suite

Bộ test kiểm chứng độ bao quát của 5 constraint trong `../constraints`.
Tất cả pod test nằm ở namespace **`techx-tf1`** (khớp `spec.match.namespaces` của constraint).

> ⚠️ **Các constraint đang để `enforcementAction: dryrun`** → khi `kubectl apply`,
> pod vi phạm **VẪN được tạo thành công**, KHÔNG bị từ chối. Vi phạm chỉ xuất hiện trong
> **audit / status.violations** của constraint. Xem mục "Cách verify" bên dưới.

## Ma trận coverage

| File | Loại | Policy được test | Nhánh logic | Kỳ vọng |
|------|------|------------------|-------------|---------|
| `pos-01-valid.yaml`               | positive | tất cả | — | PASS toàn bộ |
| `pos-02-run-as-nonroot-only.yaml` | positive | run-as-non-root | runAsNonRoot:true, không runAsUser | PASS |
| `pos-03-allowed-cap.yaml`         | positive | deny-dangerous-capabilities | add NET_BIND_SERVICE (whitelist) | PASS |
| `pos-04-exempt-image.yaml`        | positive | deny-privilege-escalation | exemptImages (pause*) | PASS |
| `pos-05-image-digest.yaml`        | positive | deny-floating-image-tag | image digest cố định | PASS |
| `neg-01-root.yaml`                | negative | run-as-non-root | thiếu runAsNonRoot & runAsUser | VI PHẠM |
| `neg-02-image-latest.yaml`        | negative | deny-floating-image-tag | tag `:latest` | VI PHẠM |
| `neg-03-missing-resources.yaml`   | negative | require-resources | thiếu toàn bộ requests+limits | VI PHẠM |
| `neg-04-priv-esc-true.yaml`       | negative | deny-privilege-escalation | allowPrivilegeEscalation: true | VI PHẠM |
| `neg-05-priv-esc-missing.yaml`    | negative | deny-privilege-escalation | thiếu field allowPrivilegeEscalation | VI PHẠM |
| `neg-06-no-drop-all.yaml`         | negative | deny-dangerous-capabilities | drop nhưng không drop ALL | VI PHẠM |
| `neg-07-add-dangerous-cap.yaml`   | negative | deny-dangerous-capabilities | add SYS_ADMIN (ngoài whitelist) | VI PHẠM |
| `neg-08-no-image-tag.yaml`        | negative | deny-floating-image-tag | image không có tag | VI PHẠM |
| `neg-09-run-as-root-uid0.yaml`    | negative | run-as-non-root | runAsUser: 0 (root tường minh) | VI PHẠM |
| `neg-10-missing-limits-only.yaml` | negative | require-resources | có requests, thiếu limits | VI PHẠM |
| `neg-11-initcontainer-latest.yaml`| negative | deny-floating-image-tag | vi phạm nằm ở initContainers | VI PHẠM |
| `neg-12-multi-violation.yaml`     | negative | cả 5 policy | vi phạm đồng thời | VI PHẠM x5 |

### Bao phủ theo policy (mỗi policy đều có ≥1 negative + positive)

| Policy | Negative | Positive |
|--------|----------|----------|
| run-as-non-root               | neg-01, neg-09, neg-12 | pos-01, pos-02 |
| deny-floating-image-tag       | neg-02, neg-08, neg-11, neg-12 | pos-01, pos-05 |
| require-cpu-memory-limits-requests | neg-03, neg-10, neg-12 | pos-01 |
| deny-privilege-escalation     | neg-04, neg-05, neg-12 | pos-01, pos-04 (exempt) |
| deny-dangerous-capabilities   | neg-06, neg-07, neg-12 | pos-01, pos-03 |

## Cách verify (chỉ đọc, không phá hạ tầng)

Vì `enforcementAction: dryrun`, KHÔNG kỳ vọng `apply` bị chặn. Kiểm tra qua audit:

```sh
# 1) (Tùy chọn) apply toàn bộ test — pod sẽ được tạo do dryrun
kubectl apply -f tests/

# 2) Xem vi phạm mà audit ghi nhận cho từng constraint
kubectl get k8spspallowedusers run-as-non-root -o jsonpath='{.status.violations}' | jq
kubectl get k8sdisallowedtags deny-floating-image-tag -o jsonpath='{.status.violations}' | jq
kubectl get k8srequiredresources require-cpu-memory-limits-requests -o jsonpath='{.status.violations}' | jq
kubectl get k8spspallowprivilegeescalationcontainer deny-privilege-escalation -o jsonpath='{.status.violations}' | jq
kubectl get k8sdisallowcapabilities deny-dangerous-capabilities -o jsonpath='{.status.violations}' | jq

# 3) Dọn dẹp
kubectl delete -f tests/
```

Audit chạy theo chu kỳ (mặc định ~60s), nên chờ một nhịp trước khi đọc `status.violations`.

### Cách test "chặn thật" (không đổi hạ tầng)
Dùng `--dry-run=server` để cho webhook đánh giá nếu tạm đổi 1 constraint sang `deny`:
```sh
kubectl apply -f tests/neg-04-priv-esc-true.yaml --dry-run=server
```
(Với `dryrun` hiện tại, lệnh này vẫn trả về created — muốn thấy reject phải để constraint ở `deny`.)

## Ghi chú
- `namespace-policy-test.yaml` tạo namespace `policy-test` — **không khớp** match `techx-tf1` của
  constraint hiện tại, nên không dùng cho bộ test này. Giữ lại hay bỏ tùy mục đích khác.
- Template `k8spspcapabilities` (ConstraintTemplate) hiện KHÔNG có constraint nào tham chiếu →
  không nằm trong phạm vi test.
