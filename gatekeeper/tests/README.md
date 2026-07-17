# Gatekeeper Policy Test Suite

Bộ test kiểm chứng độ bao quát của 5 constraint trong `../constraints`.
Tất cả pod test nằm ở namespace **`techx-tf1`** (khớp `spec.match.namespaces` của constraint).

> ⚠️ **Các constraint đang để `enforcementAction: dryrun`** → khi `kubectl apply`,
> pod vi phạm **VẪN được tạo thành công**, KHÔNG bị từ chối. Vi phạm chỉ xuất hiện trong
> **audit / status.violations** của constraint. Xem mục "Hướng dẫn sử dụng" bên dưới.

---

## Hướng dẫn sử dụng

### 0. Chuẩn bị (làm 1 lần)

```sh
# a) Trỏ đúng cluster & kiểm tra quyền
kubectl config current-context
kubectl auth can-i create pods -n techx-tf1

# b) Gatekeeper phải đang chạy
kubectl get pods -n gatekeeper-system

# c) ConstraintTemplate và Constraint đã được cài (chạy từ thư mục gatekeeper/)
kubectl get constrainttemplates
kubectl get constraints

# d) Namespace test tồn tại (nếu chưa có)
kubectl get ns techx-tf1 || kubectl create ns techx-tf1
```

> Nếu chưa cài policy: `kubectl apply -f ../ConstraintTemplate/` rồi `kubectl apply -f ../constraints/`.
> Cần cài Template TRƯỚC, đợi vài giây cho CRD sẵn sàng, rồi mới cài Constraint.

### 1. Cách nhanh nhất — chạy toàn bộ rồi đọc vi phạm

```sh
# Từ thư mục gatekeeper/tests/

# (1) Apply tất cả pod test — do dryrun nên pod nào cũng được tạo
kubectl apply -f .

# (2) Đợi audit chạy 1 nhịp (mặc định ~60s) rồi xem vi phạm của TẤT CẢ constraint
sleep 60
kubectl get constraints -o json \
  | jq -r '.items[] | "== \(.kind)/\(.metadata.name) ==",
      ( .status.violations // [] | .[] | "  - \(.name): \(.message)" )'

# (3) Dọn dẹp
kubectl delete -f .
```

### 2. Chạy & kiểm tra MỘT test cụ thể

Ví dụ kiểm tra `neg-07-add-dangerous-cap.yaml` (kỳ vọng vi phạm `deny-dangerous-capabilities`):

```sh
kubectl apply -f neg-07-add-dangerous-cap.yaml
sleep 60   # đợi audit

# Đọc vi phạm của đúng constraint tương ứng
kubectl get k8sdisallowcapabilities deny-dangerous-capabilities \
  -o jsonpath='{.status.violations}' | jq

kubectl delete -f neg-07-add-dangerous-cap.yaml
```

Kết quả mong đợi: trong danh sách violations có entry với `name: neg-add-dangerous-cap`
và message kiểu *"đang add capabilities không được phép: {SYS_ADMIN}"*.

### 3. Bảng tra: policy ↔ lệnh đọc vi phạm

| Policy (constraint) | Kind | Lệnh đọc violations |
|---|---|---|
| run-as-non-root | `k8spspallowedusers` | `kubectl get k8spspallowedusers run-as-non-root -o jsonpath='{.status.violations}' \| jq` |
| deny-floating-image-tag | `k8sdisallowedtags` | `kubectl get k8sdisallowedtags deny-floating-image-tag -o jsonpath='{.status.violations}' \| jq` |
| require-cpu-memory-limits-requests | `k8srequiredresources` | `kubectl get k8srequiredresources require-cpu-memory-limits-requests -o jsonpath='{.status.violations}' \| jq` |
| deny-privilege-escalation | `k8spspallowprivilegeescalationcontainer` | `kubectl get k8spspallowprivilegeescalationcontainer deny-privilege-escalation -o jsonpath='{.status.violations}' \| jq` |
| deny-dangerous-capabilities | `k8sdisallowcapabilities` | `kubectl get k8sdisallowcapabilities deny-dangerous-capabilities -o jsonpath='{.status.violations}' \| jq` |

### 4. Cách ĐỌC kết quả (đối chiếu pass/fail)

- **Test negative (`neg-*`) coi là ĐẠT** khi tên pod của nó **XUẤT HIỆN** trong `status.violations`
  của đúng constraint ghi ở comment cuối mỗi file (dòng `# Policy kỳ vọng: ...`).
- **Test positive (`pos-*`) coi là ĐẠT** khi tên pod của nó **KHÔNG xuất hiện** trong bất kỳ
  `status.violations` nào.
- `neg-12-multi-violation` phải xuất hiện trong violations của **cả 5** constraint.
- Mỗi file test đều có comment `# Policy kỳ vọng: ...` ở cuối — dùng nó làm "đáp án".

Đếm nhanh tổng số vi phạm hiện có:

```sh
kubectl get constraints -o json \
  | jq '[.items[].status.violations // [] | length] | add'
```

### 5. Kiểm tra "chặn thật" mà KHÔNG đổi hạ tầng

Với `dryrun`, webhook không reject. Muốn xem hành vi `deny` mà không sửa constraint đang chạy,
đánh giá phía server bằng bản copy constraint để `deny` trong file tạm (không apply constraint đó):

```sh
# Chỉ evaluate, không lưu gì vào cluster
kubectl apply -f neg-04-priv-esc-true.yaml --dry-run=server
```

> Lưu ý: với constraint hiện tại (`dryrun`), lệnh trên vẫn báo *created*. Chỉ khi constraint để
> `enforcementAction: deny` thì `--dry-run=server` mới trả về lỗi admission (bị chặn).

### 6. Dọn dẹp

```sh
kubectl delete -f .                      # xóa tất cả pod test
kubectl get pods -n techx-tf1            # xác nhận đã sạch
```

### 7. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân & cách xử lý |
|---|---|
| `status.violations` rỗng dù đã apply pod xấu | Audit chưa chạy — đợi thêm ~60s. Hoặc pod không ở ns `techx-tf1`. |
| Pod bị từ chối ngay khi apply | Constraint đã đổi sang `deny` (không còn `dryrun`). |
| Không thấy constraint nào | Chưa cài Template/Constraint — xem mục Chuẩn bị. |
| `error: the server doesn't have a resource type "k8s..."` | ConstraintTemplate chưa được cài hoặc CRD chưa kịp tạo — cài Template trước, đợi vài giây. |
| Pod `pos-*` lại bị liệt kê vi phạm | Bug ở policy hoặc test — kiểm tra lại securityContext/resources của pod đó. |
| `jq: command not found` | Cài `jq`, hoặc bỏ `| jq` và đọc JSON thô. |

---

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

## Ghi chú
- `namespace-policy-test.yaml` tạo namespace `policy-test` — **không khớp** match `techx-tf1` của
  constraint hiện tại, nên không dùng cho bộ test này. Giữ lại hay bỏ tùy mục đích khác.
- Template `k8spspcapabilities` (ConstraintTemplate) hiện KHÔNG có constraint nào tham chiếu →
  không nằm trong phạm vi test.
