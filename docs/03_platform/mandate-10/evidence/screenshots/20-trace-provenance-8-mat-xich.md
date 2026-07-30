# 20 ⭐ — Đủ 8 mắt xích, không "unknown" nào

![](20-trace-provenance-8-mat-xich.png)

**Chụp:** 26/07/2026 10:09 · GitHub Actions job summary
**Chứng minh:** yêu cầu #5 — **truy ngược full provenance từ một pod đang chạy**

## Trong ảnh có gì

Bảng summary cho pod `techx-tf1/product-catalog-694449c757-6ljmc`:

| Mắt xích | Bằng chứng |
|---|---|
| Pod → runtime digest | `sha256:bd9175e8305e6b52cce697f0f8c28b4dcf61da8cf9a4c492c5de69ddc4c09a02` |
| Spec image ↔ runtime imageID | hai dòng **trùng digest** |
| SLSA provenance | `PASS via gh attestation verify` |
| Source commit | `6beefa4b6a8e30e22f8123d7c05349ffea813191` |
| Chữ ký Cosign | identity `.../app-build.yaml@refs/heads/develop` |
| SBOM | `PASS spdxjson attestation verified` |
| Dấu promote | `PASS service=product-catalog, tag=1.0-product-catalog-6beefa4` |
| CI run | run `30159978689` conclusion=success |
| PR + người duyệt | PR #401 · **Approved by `nhatphanhk`** |

Kết luận in ở cuối:

> PASS: pod runtime digest traced to SLSA provenance, cosign signature, SBOM,
> promoted-develop attestation, successful app-build run, and approved PR.

## Vì sao đáng chụp

Đây là bài mentor bấm nút số 3: *"chỉ vào một pod đang chạy → team truy ngược full
provenance ngay trước mặt"*.

Directive #5 đòi 5 mắt xích: digest → commit → PR ai duyệt → scan nào pass → ai ký → SBOM.
Workflow truy **8 mắt**, thừa ra **SLSA provenance** và dấu **`promoted-develop`** (chứng
minh image này đã đi qua develop chứ không nhảy thẳng vào prod).

Một chi tiết tinh tế: dòng `Spec image` và `Runtime imageID` **trùng digest**. Nghĩa là thứ
Kubernetes ghi trong spec đúng bằng thứ container runtime thật sự kéo về — không bị tráo ở
giữa. Workflow fail-closed: lệch một mắt là `::error::` + exit 1, không có "unknown" mù.

## Phần tự khai điểm yếu

Hai dòng `Build run note` và `PR trace note` ghi rõ:

> Manual workflow_dispatch run. This can rebuild the full repository snapshot at the source
> commit; it does not mean the traced PR changed every service.

> Changed files may not belong to the traced service when app-build was run as a manual full
> rebuild. The PR is the source merge commit for the repository snapshot used to build this image.

Image này dựng từ một lần `workflow_dispatch` full rebuild, nên PR #401 gắn kèm là PR của
commit snapshot chứ không phải PR đổi riêng `product-catalog`. **Ghi rõ ra thay vì giấu** —
đúng tinh thần "không tin mù" của directive. Khi demo nên chủ động nói trước điểm này.
