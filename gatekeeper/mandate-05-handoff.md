# Mandate-05 Runtime Hardening — Handoff & Phase 4/5 Plan

**Mã:** CDO-SEC-HANDOFF-001 · **Cập nhật:** 2026-07-17
**Trạng thái:** Phase 1–3 XONG (live, dryrun) · Phase 4–5 CHƯA làm
**Mục tiêu mandate:** Manifest nguy hiểm (root / tag `latest` / thiếu limit / priv-esc / thừa cap) bị **từ chối ngay lúc apply** tại admission — chứng minh bằng 1 lần apply thử bị chặn, cluster không còn workload vi phạm.

> Đọc kèm: `mandates/MANDATE-05-runtime-hardening.md` (đề bài), `docs/adr-runtime-hardening.md` / `docs/adr-admission-policy*.md` (ADR).

---

## 0. TL;DR cho người tiếp nhận

- Engine: **OPA Gatekeeper 3.23.0**, cài bằng **Helm TAY** (KHÔNG qua ArgoCD) trong ns `gatekeeper-system`.
- **5 constraint đang `dryrun`** (chỉ cảnh báo, chưa chặn). **Vi phạm hiện = 0.**
- Việc còn lại = **Phase 4**: đổi `dryrun`→`deny` (chặn thật) + test evidence. **Phase 5**: ADR + demo mentor + dọn dẹp.
- Đã sạch vi phạm rồi nên flip `deny` an toàn, không chặn nhầm đồ đang chạy.

---

## 1. Bối cảnh — tại sao & đã làm gì

### 1.1 Xuất phát điểm
Cluster `ecommerce-dev-eks` (us-east-1) có nhiều cấu hình nguy hiểm: container chạy root, image tag di động (`latest`), workload thiếu requests/limits, securityContext trống. Gatekeeper lúc đầu là **zombie** (chỉ còn ns + CRD sót, không controller/webhook) → không enforce gì.

### 1.2 Đã làm (Phase 1–3)

| Phase | Việc | Kết quả |
|---|---|---|
| Dọn nền | Xóa 17 CRD mồ côi + ns zombie | Clean slate |
| Cài | Helm install gatekeeper 3.23.0, `replicas=1` | controller + audit Running |
| Policy | Fix bug Rego + apply 6 template, 5 constraint (`dryrun`) | Enforce logic sẵn sàng |
| Fix conflict | Gỡ custom `K8sDisallowCapabilities` (xung đột logic với upstream), giữ `K8sPSPCapabilities` | 1 luật capabilities duy nhất |
| **Phase 1** | Thêm requests/limits cho 5 app initContainer | require-cpu-memory sạch phần app |
| **Phase 3** | opensearch: bỏ init root (`enableInitChown:false`) + `initResources`; exempt observability | Sạch nốt |

**Merged:** PR #141 (constraints), PR #142 (values) → đã vào `develop`, ArgoCD synced.

### 1.3 Trạng thái LIVE hiện tại
```
5 constraint = enforcementAction: dryrun
Vi phạm: priv-esc 0 · caps 0 · non-root 0 · require-cpu 0 · floating-tag 0
opensearch-0: 1/1 Running (đã bỏ fsgroup-volume init root, data còn)
```

---

## 2. Kiến trúc policy — 5 constraint

Tất cả scope `techx-tf1`, loại trừ `kube-system` / `gatekeeper-system` / `argocd`. File tại `gatekeeper/`.

| Constraint (name) | Kind | Luật | Directive |
|---|---|---|---|
| `run-as-non-root` | K8sPSPAllowedUsers | cấm chạy root (MustRunAsNonRoot) | #1 |
| `deny-privilege-escalation` | K8sPSPAllowPrivilegeEscalationContainer | bắt `allowPrivilegeEscalation:false` | #1 |
| `psp-capabilities` | K8sPSPCapabilities | drop ALL, chỉ add NET_BIND_SERVICE | #1 |
| `deny-floating-image-tag` | K8sDisallowedTags | cấm `latest/dev/master/main/stable/edge` | #2 |
| `require-cpu-memory-limits-requests` | K8sRequiredResources | đủ requests+limits cpu+memory (cả initContainers) | #3 |

**Ngoại lệ (exemptImages)** — observability stack cần quyền cao, ghi trong constraint files, **ADR-003 §4, hết hạn 2026-12-31**:
- `deny-privilege-escalation`: prometheus, otel, jaeger, opensearch
- `psp-capabilities`: prometheus, otel, jaeger
- `run-as-non-root`: otel

---

## 3. PHASE 4 — Flip `dryrun` → `deny` (chặn thật)

**Nguyên tắc:** vi phạm đã = 0 nên flip an toàn. Admission chỉ ảnh hưởng pod **tạo/sửa mới**, KHÔNG evict pod đang chạy. Flip **từng cái**, test, rồi tiếp — để cô lập blast radius.

### 3.1 Trình tự đề xuất (an toàn → nhạy)
1. `deny-floating-image-tag`
2. `require-cpu-memory-limits-requests`
3. `run-as-non-root`
4. `deny-privilege-escalation`
5. `psp-capabilities`

### 3.2 Với MỖI constraint
```bash
export AWS_PROFILE=Phase3-CDO-PermissionSet-804372444787
# 1. Flip sang deny (sửa file gatekeeper/constraints/<file>.yaml: enforcementAction: dryrun -> deny), rồi apply.
#    Hoặc patch nhanh:
kubectl patch <kind> <name> --type=merge -p '{"spec":{"enforcementAction":"deny"}}'

# 2. NEGATIVE test — apply pod vi phạm, KỲ VỌNG bị REJECT:
kubectl apply -f gatekeeper/tests/neg-02-image-latest.yaml   # -> phải Error/denied
# (chọn neg-* khớp luật vừa flip — bảng ở §4.1)

# 3. POSITIVE test — pod hợp lệ phải PASS:
kubectl apply --dry-run=server -f gatekeeper/tests/pos-01-valid.yaml   # -> created (dry run)

# 4. Confirm pod thật KHÔNG rớt (admission không đụng pod đang chạy):
kubectl get pods -n techx-tf1 | grep -v Running | grep -v Completed
```

### 3.3 Rollback (nếu chặn nhầm)
```bash
kubectl patch <kind> <name> --type=merge -p '{"spec":{"enforcementAction":"dryrun"}}'
# Tức thời. Không cần gỡ gatekeeper. Ghi lý do + Owner duyệt.
```

### 3.4 ⚠ Cảnh báo quan trọng
- **Gatekeeper là manual, KHÔNG GitOps.** Flip = `kubectl` thẳng lên cluster, không qua PR/ArgoCD. Sửa file constraint trong repo để **khớp** cluster (đừng để lệch).
- **CI KHÔNG bắt vi phạm.** "Validate Helm manifest" chỉ render helm; gatekeeper chặn lúc `kubectl apply` lên cluster. Deploy qua ArgoCD mà manifest vi phạm → ArgoCD sync sẽ **fail** (bị admission từ chối). Đừng flip `deny` ngay trước 1 đợt deploy lớn chưa kiểm.
- **Webhook `failurePolicy: Ignore`** (fail-open): controller chết → pod xấu lọt. `deny` chỉ đáng tin khi controller Up. Kiểm `kubectl get pods -n gatekeeper-system` trước khi tin.
- Kiểm mọi constraint đã `enforced:true` (audit ăn) trước flip: `kubectl get <kind> <name> -o jsonpath='{.status.byPod[0].enforced}'`.

---

## 4. PHASE 5 — Evidence + ADR + dọn dẹp

### 4.1 Chạy full test suite làm evidence
Thư mục `gatekeeper/tests/`. neg-* phải REJECT, pos-* phải PASS. Map:

| Test | Vi phạm | Constraint bắt |
|---|---|---|
| neg-01-root | runAsUser:0 | run-as-non-root |
| neg-02-image-latest | image `:latest` | deny-floating-image-tag |
| neg-03-missing-resources | không khai resources | require-cpu-memory |
| neg-04-priv-esc-true | allowPrivilegeEscalation:true | deny-privilege-escalation |
| neg-06-no-drop-all | không drop ALL | psp-capabilities |
| neg-07-add-dangerous-cap | add SYS_ADMIN | psp-capabilities |
| neg-11-initcontainer-latest | init dùng `:latest` | deny-floating-image-tag |
| neg-12-multi-violation | nhiều luật | nhiều |
| pos-01-valid | hợp lệ hết | PASS |
| pos-04-exempt-image | image exempt | PASS |
| pos-05-image-digest | pin digest | PASS |

Lệnh gợi ý: apply từng neg → lưu output deny message nguyên văn (evidence). Xem `gatekeeper/tests/README.md`.

### 4.2 Demo mentor (yêu cầu nộp)
1. Apply 1 manifest vi phạm (root / `latest` / thiếu limit) → mentor **tận mắt thấy REJECT**.
2. `kubectl get constraint -A` → cột TOTAL-VIOLATIONS = **0** (cluster sạch).

### 4.3 ADR ký tên (yêu cầu nộp) — cập nhật `docs/adr-runtime-hardening.md`
Phải ghi:
- Luật nào **enforce (deny)**, luật nào còn **audit (dryrun)** + vì sao.
- Cách cắt chuyển audit→enforce để không chặn nhầm (chính là §3.2).
- **Ngoại lệ**: 4 image observability + lý do + expiry 2026-12-31.
- Rollback (§3.3).

### 4.4 Dọn dẹp (nợ kỹ thuật, không chặn nộp)
- **Xóa template mồ côi** `gatekeeper/ConstraintTemplate/k8s-disallow-capabilities.yaml` (không constraint nào dùng; cluster đã bỏ; repo còn sót).
- **Sửa stale ref** `deny-dangerous-capabilities` / `k8sdisallowcapabilities` trong `gatekeeper/tests/` + `gatekeeper/tests/README.md` (đặc biệt lệnh `kubectl get k8sdisallowcapabilities` sẽ lỗi) + `docs/` → đổi sang `psp-capabilities`/`K8sPSPCapabilities`.
- **GitOps hóa gatekeeper** (lớn): thêm 2 ArgoCD Application vào `platform/gitops/applications/` (controller Helm + constraints repo) để hết cảnh cài tay. Xem §6.

---

## 5. Gotchas — đọc trước khi đụng

1. **AWS/kubectl:** luôn `export AWS_PROFILE=Phase3-CDO-PermissionSet-804372444787` (default profile hết hạn token).
2. **helm CLI:** cài tay ở `~/.local/bin/helm` (v4.2.3). Nếu máy khác chưa có → cài lại.
3. **Gatekeeper KHÔNG trong ArgoCD** — templates/constraints apply bằng `kubectl apply -f gatekeeper/...`. Cluster rebuild = phải cài lại controller (Helm) + apply lại. Đây là lý do §4.4 khuyến nghị GitOps hóa.
4. **Đừng re-add** custom `K8sDisallowCapabilities` — nó xung đột logic với `K8sPSPCapabilities` (case-sensitivity "ALL", xử lý UPDATE khác nhau → cùng pod, cái cho cái chặn). Chỉ giữ upstream.
5. **opensearch:** đã bỏ init root `fsgroup-volume` bằng `enableInitChown:false` (kubelet fsGroup tự chown PVC trên EBS gp3). **Đừng bật lại** — sẽ tái sinh container root vi phạm.
6. **`llm` CrashLoopBackOff** = bug app riêng (exit 1), **KHÔNG liên quan** gatekeeper. Đừng nhầm là do policy.
7. **Storefront public / cổng vận hành private / flagd** — không đụng (RULES).

---

## 6. Tham chiếu nhanh

**Kiểm sức khỏe policy:**
```bash
export AWS_PROFILE=Phase3-CDO-PermissionSet-804372444787
kubectl get pods -n gatekeeper-system                 # controller + audit Up?
kubectl get constrainttemplate                        # 6 template
kubectl get constraint -A                             # 5 constraint + TOTAL-VIOLATIONS
kubectl get <kind> <name> -o jsonpath='{.status.totalViolations}'   # audit count 1 constraint
```

**File quan trọng:**
| Đường dẫn | Là gì |
|---|---|
| `gatekeeper/ConstraintTemplate/` | 6 template (Rego/CEL) |
| `gatekeeper/constraints/` | 5 constraint (`enforcementAction` ở đây) |
| `gatekeeper/tests/` | neg/pos test + README |
| `platform/charts/application/values.yaml` | app chart (init resources Phase 1) |
| `platform/gitops/environments/sandbox/values-ops-observability.yaml` | observability config (opensearch Phase 3) — file ArgoCD thật đọc |

**Cụm:** `ecommerce-dev-eks` / us-east-1 · ns app `techx-tf1` · ns policy `gatekeeper-system`.

---

## 7. Definition of Done (mandate)
- [ ] Phase 4: 5 constraint `enforcementAction: deny`, file repo khớp cluster.
- [ ] Test suite chạy: neg REJECT, pos PASS — có evidence (deny messages).
- [ ] Demo mentor: apply manifest vi phạm → REJECT live + `get constraint` violations=0.
- [ ] ADR ký tên (enforce vs audit, exemption+expiry, cutover, rollback).
- [ ] (Nên) dọn template mồ côi + stale ref + GitOps hóa gatekeeper.
