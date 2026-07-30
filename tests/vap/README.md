# Bộ test VAP — Mandate 05 Runtime Hardening

Test 5 ValidatingAdmissionPolicy trên cluster bằng **server-side dry-run** —
KHÔNG ghi gì vào cluster (an toàn với workload đang chạy).

## Cách chạy

Chạy **từ trong thư mục `tests/vap/`** (script sẽ tự `cd` về đúng chỗ chứa các
manifest, nhưng tên file phải gọi đúng vị trí):

```bash
cd tests/vap
bash run-dry-run-tests.sh
# hoặc lưu evidence:
bash run-dry-run-tests.sh 2>&1 | tee "results-$(date +%Y%m%d-%H%M).txt"
```

Nếu đang đứng ở thư mục `tests/` (thư mục cha), gọi kèm đường dẫn `vap/`:

```bash
bash vap/run-dry-run-tests.sh
```

Mặc định test chạy trên namespace `default`. Để test đúng namespace production
`techx-tf1`, đặt biến `NS` ở đầu lệnh:

```bash
NS=techx-tf1 bash run-dry-run-tests.sh
```

Yêu cầu: SSO đã đăng nhập, kubectl trỏ cluster `ecommerce-dev-eks`, có quyền
create Pod trong `techx-tf1` (dry-run vẫn qua RBAC).

## Ma trận test (15 case)

### Negative — phải bị bắt (11 case)

| Case | Luật kích hoạt | Nhánh CEL được test |
|---|---|---|
| `neg-01-root` | run-as-non-root | container-level `runAsUser: 0` |
| `neg-02-image-latest` | deny-floating-image-tag | tag `:latest` |
| `neg-03-missing-resources` | require-resources | thiếu toàn bộ `resources` |
| `neg-04-privesc-caps` | deny-privilege-escalation + psp-capabilities | `allowPrivilegeEscalation: true` + add `SYS_ADMIN` |
| `neg-05-multi` | **cả 5 luật** | nhiều luật cùng bắn trên 1 pod |
| `neg-06-initcontainer-latest` | deny-floating-image-tag | vi phạm giấu trong **initContainer** (`allContainers` gộp) |
| `neg-07-privesc-absent` | deny-privilege-escalation | **không set** field (absent → chặn, vì CEL đòi `== false` tường minh) |
| `neg-08-no-caps-block` | psp-capabilities | **không có** `capabilities` block (absent → chặn) |
| `neg-09-partial-resources` | require-resources | có requests nhưng **thiếu `limits.memory`** (lỗi dev phổ biến nhất) |
| `neg-10-podlevel-root` | run-as-non-root | `runAsUser: 0` ở **pod-level**, container không set (nhánh fallback) |
| `neg-11-uppercase-tag` | deny-floating-image-tag | tag floating viết **HOA** (`nginx:LATEST`) → CEL `lowerAscii()` vẫn bắt |

### Positive — phải PASS sạch, không warning nào (4 case)

| Case | Nhánh CEL được test |
|---|---|
| `pos-01-valid` | chuẩn đầy đủ: nonRoot + tag cố định + resources + privEsc false + drop ALL |
| `pos-02-podlevel-nonroot` | `runAsNonRoot: true` ở **pod-level** (pattern phổ biến nhất trên cluster: checkout, currency...) |
| `pos-03-otel-exempt` | **exempt list**: image otel-collector không securityContext vẫn pass (regression guard cho DaemonSet otel-collector-agent) |
| `pos-04-digest-netbind` | pin image theo **digest `@sha256`** + add **`NET_BIND_SERVICE`** (cap duy nhất được phép) |

## Cách script chấm điểm

Với mỗi case, script kiểm tra 2 chiều:
1. **Đủ**: mọi policy trong cột kỳ vọng phải xuất hiện trong output.
2. **Không thừa**: policy NGOÀI kỳ vọng không được xuất hiện (chống nhiễu chéo /
   false positive) — áp cho cả case neg lẫn pos.

## Diễn giải kết quả theo giai đoạn

| Giai đoạn binding | Case neg | Case pos |
|---|---|---|
| `Warn` (hiện tại) | Hiện `Warning: Validation failed ...'<policy>'`, pod vẫn `configured (server dry run)` | Không warning |
| `Deny` (Phase 3) | Bị **từ chối** (`error ... denied the request`) | Vẫn apply được |

Bảng EXPECT không phải sửa khi chuyển Warn→Deny (message hai chế độ đều chứa tên
policy) → chạy lại chính script này sau Phase 3 làm bằng chứng "chặn thật" cho mentor.

## Nhánh chưa phủ (chấp nhận bỏ, lý do)

- `ephemeralContainers` — không test được qua `kubectl apply` (cần `kubectl debug`),
  rủi ro thấp.
- Registry có port (`registry:5000/app`) — hệ thống chỉ dùng ECR chuẩn.
- Tag cấm khác (`dev/master/main/stable/edge`) — cùng nhánh CEL với `latest`, đã
  đại diện bởi neg-02.
- Image test `ecommerce-dev-techx-corp:...` không cần tồn tại thật — dry-run không
  pull image, admission chỉ so chuỗi.
