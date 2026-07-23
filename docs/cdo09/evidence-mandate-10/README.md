# MANDATE-10 P2 — Kyverno verifyImages: bằng chứng

Admission control chặn image không mang chữ ký Cosign của workflow `app-build.yaml`.
Bổ sung cho VAP `runtime-hardening`: VAP trả lời "tag có trôi không", Kyverno trả lời
"image này do CI của mình dựng ra hay ai đó push tay".

## Cấu trúc

```
evidence/     manifest pod test (signed / unsigned / upstream đối chứng)
logs/         output đo đạc và trạng thái cụm
screenshots/  ảnh chụp + hướng dẫn chụp
```

## Trạng thái các bước

| Bước | Nội dung | Trạng thái |
|---|---|---|
| 2.0 | Capacity (hạ ml-guard 1000m→400m) | ✅ PR #303 |
| 2.1 | IRSA + cài Kyverno qua GitOps | ✅ PR #311, #314 |
| 2.2 | ClusterPolicy verify-image-signature (Audit) | ✅ PR #314 |
| 2.3 | Soak Audit | ✅ ~2h, sạch |
| 2.4 | 2 image aiops vào app-build | ✅ PR #307 |
| 2.5 | Flip Enforce + 5 test | ⏳ **chưa merge** |

## Kết quả soak (23/07, chế độ Audit)

```
PolicyReport : 23 report, PASS=23, FAIL=0, ERROR=0
Log verify   : 80 "verification succeeded", 0 failed
PDB          : kyverno-admission-controller  ALLOWED DISRUPTIONS = 1
```

80 lần verify thành công là bằng chứng **IRSA hoạt động** — không có role
`ecommerce-dev-kyverno` thì mọi verify đã fail với lỗi ECR auth (node prod đặt
IMDSv2 hop limit = 1 nên pod không mượn được node role).

2 pod aiops đều PASS: chuỗi build→Trivy→ký→SBOM→verify khép kín cho 2 workload
trước đây push tay.

## Độ trễ admission (baseline lúc Audit)

| | Thời gian |
|---|---|
| Image qua policy — lần verify **đầu** của một digest | **70.1s** |
| Image qua policy — lần 2-5 | 2.6-4.8s |
| Image ngoài policy (busybox) — mốc overhead mạng | 2.4s |

Chi phí verify khi cache đã ấm: **~0.2-2.4s**. Con số 70s là cái giá một lần cho mỗi
digest mới (tải TUF root + truy vấn Rekor qua NAT) — lý do giữ
`webhookTimeoutSeconds: 30`.

Chi tiết: [logs/01-baseline-admission-latency.txt](logs/01-baseline-admission-latency.txt)

## Cặp bằng chứng before/after

| | Trước (Audit) | Sau (Enforce) |
|---|---|---|
| Pod không chữ ký | **được nhận** | **bị chặn** |
| Chế độ policy | `Audit / Ignore` | `Enforce / Fail` |

Vế "trước" đã thu: [logs/02-nhom-a-truoc-enforce.txt](logs/02-nhom-a-truoc-enforce.txt)
Vế "sau": chờ merge PR flip Enforce.

Image dùng làm mẫu "không chữ ký" là `1.2-aiops-detector-ae89fa2` — chính image
aiops push tay ngày 17/07, trước khi aiops được kéo vào app-build.

## Hạn chế đã biết

1. **Kyverno không cache được token ECR** — `readOnlyRootFilesystem` chặn ghi `/.ecr`
   (log `Could not save cache` ×143). Mỗi verify tốn thêm 1 round-trip ECR. Giảm được
   bằng cách mount emptyDir vào `/.ecr` trong values chart. Để lại sau deadline.

2. **App `kyverno` báo OutOfSync vĩnh viễn** — chart khai `annotations: {}` và
   `labels: {}` (map rỗng) mà K8s không lưu field rỗng, nên diff không bao giờ hết.
   Vô hại, không ảnh hưởng hoạt động. Dọn được bằng thêm 2 jsonPointer vào
   `ignoreDifferences`.

3. **Policy chỉ verify chữ ký, KHÔNG verify attestation** — attestation
   `promoted-develop` nằm ở repo tách riêng (`ecommerce-dev-techx-corp-attest`, vì ECR
   immutable không cho ghi `.att` thứ hai lên repo chính). Kéo vào admission vừa phức
   tạp vừa thừa: gate promote đã enforce ở CI.

## Rollback

Leo thang theo mức độ:

1. **Hạ về Audit**: sửa 2 dòng trong `platform/policies/kyverno/verify-image-signature.yaml`
   (`Enforce`→`Audit`, `Fail`→`Ignore`) rồi merge. Policy vẫn ghi report, hết chặn.
2. **Gỡ hẳn policy**: `kubectl delete clusterpolicy verify-image-signature`. Thoát
   ngay, không cần gỡ Kyverno — đây là lý do policy tách Application riêng.
   **Phải revert cả Git**, nếu không selfHeal dựng lại sau ~3 phút.

KHÔNG `kubectl patch` để đổi Audit/Enforce — ArgoCD selfHeal revert về Git.
