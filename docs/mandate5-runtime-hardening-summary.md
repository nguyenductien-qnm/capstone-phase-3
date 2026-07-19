# Tổng hợp Mandate 5 — Runtime Hardening (Directive #5): Trạng thái Triển khai & Yêu cầu Hạ tầng

**Mã tài liệu**: CDO-SEC-SUM-001
**Trạng thái**: Đang triển khai (In Progress)
**Người thực hiện**: Nguyễn Khánh Duy (SRE Lead) · Châu Thành Trung (Security Lead)
**Ngày cập nhật**: 15/07/2026 · Deadline nộp: **thứ Sáu 17/07/2026**
**Tổng hợp từ**: [CDO-SEC-ADR-002](./adr-admission-policy.md) · [CDO-SEC-ADR-003](./adr-runtime-hardening.md) · [CDO-SEC-IMPL-001](./adr-admission-policy-implementation.md)

---

## 1. Bối cảnh (tóm tắt)

Directive #5 yêu cầu **chặn cấu hình nguy hiểm ngay tại admission**: container chạy root, image tag di động (`latest`), workload thiếu requests/limits. Engine được chọn: **OPA Gatekeeper** (ADR-002 — trưởng thành nhất, có thư viện luật mẫu, chi phí ~$0 trong cụm sẵn có). Chiến lược rollout 2 giai đoạn: `dryrun` (giám sát) → `deny` (chặn thật), không phá SLO.

---

## 2. Các luật đã cấu hình (file tại `gatekeeper/`)

Tất cả Constraint: `enforcementAction: deny` · scope `techx-tf1` · loại trừ `kube-system`, `gatekeeper-system`, `argocd`.

| # | Constraint | Luật | Directive |
| :-: | :--- | :--- | :-: |
| 1 | `run-as-non-root` | Cấm chạy root (`MustRunAsNonRoot`) | #1 |
| 2 | `deny-privilege-escalation` | Bắt buộc `allowPrivilegeEscalation: false` | #1 |
| 3 | `psp-capabilities` | Drop `ALL`; chỉ được add `NET_BIND_SERVICE` | #1 |
| 4 | `deny-floating-image-tag` | Cấm tag `latest/dev/master/main/stable/edge` | #2 |
| 5 | `require-cpu-memory-limits-requests` | Đủ 4 field requests+limits × cpu+memory (cả initContainers) | #3 |

Luật `read-only-root-filesystem`: giữ ở **kế hoạch audit-only** (nhiều service cần ghi `/tmp`), mục tiêu enforce 30/09/2026 — chi tiết ADR-003 §3.

---

## 3. Bộ test cho mentor (đã tạo — `tests/gatekeeper/`)

Mỗi file negative vi phạm **đúng 1 luật** (field khác hợp lệ) → deny message chỉ rõ luật bắn. Bad pod nhắm thẳng `techx-tf1`; bị từ chối tại admission nghĩa là **không object nào được tạo** → không cần cleanup. Positive test chạy `--dry-run=server`.

| File | Vi phạm | Kỳ vọng |
| :--- | :--- | :-: |
| `neg-01-root.yaml` | `runAsUser: 0` | REJECT |
| `neg-02-image-latest.yaml` | image `nginx:latest` | REJECT |
| `neg-03-missing-resources.yaml` | không khai `resources` | REJECT |
| `neg-04-privilege-escalation.yaml` | `allowPrivilegeEscalation: true` | REJECT |
| `neg-05-added-capabilities.yaml` | `capabilities.add: [SYS_ADMIN]` | REJECT |
| `pos-01-valid.yaml` | hợp lệ cả 5 luật | PASS |

Lệnh chạy + expected deny message nguyên văn: xem `tests/gatekeeper/README.md` và IMPL-001 §6.

---

## 4. Đã cập nhật — dọn hiện trạng workload (`values.yaml`, 15/07/2026)

Bổ sung đủ 4 field resources cho 10 app container (giữ nguyên giá trị/comment sẵn có, chỉ thêm field thiếu); 7 component khác đã đủ từ trước (accounting, cart, checkout, load-generator, product-catalog, product-reviews, shipping).

| Component | requests.cpu | requests.memory | limits.cpu | limits.memory |
| :--- | :---: | :---: | :---: | :---: |
| ad | 50m | 128Mi | 200m | 300Mi |
| currency | 50m | 16Mi | 100m | 20Mi |
| email | 50m | 64Mi | 100m | 100Mi |
| fraud-detection | 50m | 128Mi | 150m | 300Mi |
| frontend | 100m | 128Mi | 200m | 250Mi |
| frontend-proxy | 100m | 48Mi | 200m | 65Mi |
| image-provider | 50m | 32Mi | 100m | 50Mi |
| payment | 50m | 64Mi | 100m | 140Mi |
| quote | 50m | 32Mi | 100m | 40Mi |
| recommendation | 100m | 128Mi | 200m | 500Mi |

---

## 5. Yêu cầu hạ tầng CÒN THIẾU (verify trực tiếp cụm `ecommerce-dev-eks`, 15/07/2026)

| # | Hạng mục | Hiện trạng trên cụm | Việc cần làm | Ưu tiên |
| :-: | :--- | :--- | :--- | :-: |
| 1 | Gatekeeper controller | ❌ Chưa cài — không có ns `gatekeeper-system`, không CRD | Cài Helm chart `gatekeeper/gatekeeper`, khuyến nghị qua ArgoCD Application | **Chặn tất cả** |
| 2 | Apply luật | ❌ 5 template + 5 constraint mới là file trong repo | Apply templates → constraints, khởi đầu ở `dryrun` | Cao |
| 3 | Workload vi phạm luật #5 | `flagd`, `llm` đang Running nhưng thiếu resources; `flagd-ui` + 5 initContainers chưa khai | Bổ sung 4 field vào `values.yaml` (sizing đề xuất sẵn) | Cao |
| 4 | `default.securityContext: {}` | Component không tự khai sẽ vi phạm luật #1–#3 khi restart | Khôi phục default hardened, làm **trước khi bật deny** | Cao |
| 5 | GitOps wiring | Không Application nào trỏ `gatekeeper/` | Đóng cùng #1, hoặc ghi chủ ý apply thủ công vào IMPL-001 | TB |

> Hạng mục #1 hiện đồng nghĩa **chưa có admission control nào chạy trên cụm** — mọi demo/enforce đều phụ thuộc bước này. Chi phí ~$0: Gatekeeper limits nhỏ (CPU 100m, RAM 256Mi), nằm gọn trong cụm EKS sẵn có (khớp ADR-002 §3).

**Trình tự bật enforce an toàn (ràng buộc "không phá SLO")**: cài controller → apply constraints ở `dryrun` → dọn sạch vi phạm (#3, #4; xác nhận `kubectl get constraints` violations = 0) → chuyển từng constraint sang `deny` → chạy bộ test §3 làm evidence.

---

## 6. Rollback (tóm tắt — chi tiết IMPL-001 §7)

Chặn nhầm workload thật → patch constraint liên quan `deny` → `dryrun` (tức thời, không gỡ Gatekeeper); phải có Owner duyệt và ghi lý do. Ngoại lệ có kiểm soát (otel-collector-agent, grafana sidecar, opensearch, jaeger — đều hết hạn 31/12/2026): xem ADR-003 §4.

---

## 7. Người thực hiện

* **Nguyễn Khánh Duy** (SRE Lead — triển khai & tổng hợp)
* **Châu Thành Trung** (Security Lead — thiết kế policy, tác giả ADR-002/ADR-003)
