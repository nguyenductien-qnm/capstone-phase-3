# Đối chiếu repo với DIRECTIVE #10 — audit 23/07/2026

Chấm theo **kết quả**, không theo có-làm-hay-không. Mỗi dòng dưới đây đều tra từ repo/cụm thật.

## Bảng tổng

| # | Yêu cầu | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | CI đỏ = không merge | ⚠️ **MỎNG** | ruleset có 4 required checks, nhưng chỉ 1/7 service có test thật được chạy — xem mục YC1 dưới |
| 2a | Image CVE scan là gate | ✅ ĐỦ | Trivy `severity: CRITICAL,HIGH` + `exit-code: 1` |
| 2b | IaC misconfig scan là gate | ❌ **THIẾU** | Trivy config `exit-code: "0"`, Checkov `soft_fail: true` — chỉ báo cáo |
| 2c | Secret scan là gate | ✅ ĐỦ | gitleaks nằm trong required status checks |
| 2d | SAST | ❌ **THIẾU** | không có CodeQL/Semgrep/gosec/bandit trong workflow nào |
| 3a | Registry immutable | ✅ ĐỦ | `image_mutability = "IMMUTABLE"` (module ecr) |
| 3b | Ký cosign + SBOM | ✅ ĐỦ | app-build ký digest keyless + attest spdxjson |
| 3c | Provenance attestation | ⚠️ MỘT PHẦN | có `promoted-develop` (app-attest) nhưng KHÔNG phải SLSA provenance chuẩn |
| 3d | Admission enforce | ⚠️ **CHƯA MERGE** | policy đã viết Enforce/Fail (commit e12e8b6), cụm vẫn Audit/Ignore |
| 4a | Action pin theo SHA | ❌ **THIẾU** | chỉ 3/22 pin SHA, 19 còn lại dùng tag `@v4`/`@v3` |
| 4b | Base image pin theo digest | ❌ **THIẾU** | chỉ ml-guard pin; 55 dòng FROM khác dùng tag |
| 5 | Truy ngược full provenance | ❌ **THIẾU** | `scripts/provenance.sh` chưa tồn tại (P3 trong plan) |
| 6 | Build có phạm vi theo service | ✅ ĐỦ | job `detect` lọc `git diff` theo `src/<svc>/` |

**Đủ: 5 · Một phần: 3 · Thiếu: 5**

---

## YC1 — cổng chặn có, nhưng phủ rất mỏng  (phát hiện 23/07)

`required_status_checks` trên develop có 4 check:
```
Secret scan (gitleaks)
Unit test (checkout)
Unit test (product-catalog)
Helm lint + render (deploy gate)
```

Vấn đề nằm ở 2 check unit test:

1. **`product-catalog` KHÔNG có file `_test.go` nào.** `go test ./...` trên module
   không test in `no test files` và thoát code 0 → check này **luôn xanh, không kiểm
   được gì**. Chỉ còn giá trị ở bước `go vet`.

2. **Matrix hardcode `[checkout, product-catalog]`** trong `platform-ci.yaml:51`,
   trong khi repo có **7 service có test**:

| Service | Test | Trong CI? |
|---|---|---|
| checkout | 4 file Go | ✅ |
| product-catalog | **0 file** | ✅ (check rỗng) |
| product-reviews | 5 file Python | ❌ |
| shopping-copilot | 3 file Python | ❌ |
| cart | 2 file C# | ❌ |
| llm | 1 file Python | ❌ |
| ml-guard | 1 file Python | ❌ |
| recommendation | 1 file Python | ❌ |

→ **11 file test Python + 2 file C# không bao giờ chạy trong CI.** Sửa code
`product-reviews` hay `shopping-copilot` làm hỏng test — CI vẫn xanh, vẫn merge được.

Directive nói "CI đỏ = không merge". Cổng chặn tồn tại, nhưng thứ nó chặn là: một
service Go thật, một check rỗng, gitleaks, helm lint.

**Cách sửa** (~1h, có rủi ro): thêm job `unit-test-python` matrix
`[product-reviews, shopping-copilot, llm, ml-guard, recommendation]` chạy pytest, rồi
thêm vào required status checks. Bền hơn thì suy service động từ filesystem như job
`detect` của app-build đang làm.

**Rủi ro**: 11 file test đó chưa từng chạy trong CI, rất có thể đỏ ngay lần đầu
(thiếu dependency, import sai, fixture hỏng). Bật lên là phải xử finding thật, KHÔNG
được tắt lại — cùng tình huống với IaC gate ở YC2b.

---

## Chi tiết phần THIẾU

### YC2b — IaC scan không chặn  (sửa nhanh, ~10 phút)

`.github/workflows/infra-cd.yaml`:
```yaml
# Trivy config scan
severity: CRITICAL,HIGH
exit-code: "0"        # <-- không bao giờ fail
# Checkov
soft_fail: true       # <-- không bao giờ fail
```

Sửa: `exit-code: "1"` và `soft_fail: false`. **Cảnh báo**: bật lên rất có thể đỏ ngay
vì Terraform hiện chưa từng bị chặn bởi 2 scan này — cần chạy thử trước, xử finding
thật hoặc khai báo skip có lý do, KHÔNG tắt lại.

### YC2d — không có SAST  (~30 phút)

Chưa có công cụ nào phân tích mã nguồn. Rẻ nhất: thêm CodeQL (GitHub native, miễn phí
cho repo này) cho Go + Python + JS, đặt vào required status checks.

### YC4a — 19/22 action chưa pin SHA  (~20 phút)

Đã pin đúng (3): `trivy-action`, `cosign-installer` (trong app-build), `sbom-action`.
Chưa pin (19): `actions/checkout@v4`, `aws-actions/configure-aws-credentials@v4`,
`docker/build-push-action@v6`, `mikefarah/yq@v4`, `azure/setup-helm@v4`, …

Lấy SHA: `gh api repos/actions/checkout/git/refs/tags/v4 --jq .object.sha`
Giữ comment `# v4` sau SHA để còn đọc được.

Lưu ý: `sigstore/cosign-installer` xuất hiện CẢ 2 dạng (pin SHA trong app-build,
`@v3.5.0` chỗ khác) — thống nhất lại.

### YC4b — 55 dòng FROM chưa pin digest  (~40 phút)

Chỉ `ml-guard/Dockerfile` pin `python:3.12-slim-trixie@sha256:57cd7c3a...`.
Lấy digest: `docker buildx imagetools inspect <image>:<tag> --format '{{.Manifest.Digest}}'`
hoặc `crane digest <image>:<tag>`.

Đánh đổi: pin digest thì bump base image thành việc thủ công. Đúng ý directive
("không phụ thuộc thứ trôi") nhưng cần Dependabot/Renovate để không bị bỏ quên.

### YC5 — chưa có provenance.sh  (~1h30, chính là P3 của plan)

Đây là thứ mentor sẽ **bấm nút kiểm trực tiếp** ("chỉ vào một pod đang chạy → truy
ngược full provenance ngay trước mặt"). Không có script thì phải gõ tay 6 lệnh rời rạc
trước mặt người chấm.

Chuỗi cần dựng: pod → digest → chữ ký (+ Rekor UUID) → commit → PR ai duyệt → CI run
nào pass → SBOM. Chi tiết kỹ thuật đã có trong `D:\Game\MANDATE-10-P2-P3-PLAN.md` mục P3.

---

## Ba thứ mentor sẽ bấm nút kiểm

| Bài kiểm | Sẵn sàng? |
|---|---|
| PR với CI cố tình đỏ → bị chặn merge | ⚠️ ruleset bật, nhưng chỉ `checkout` có test thật — làm đỏ PHẢI nhắm vào service đó (xem YC1) |
| Deploy image chưa ký → admission từ chối | ⚠️ **cần merge Enforce trước** |
| Chỉ vào pod → truy ngược full provenance | ❌ **cần viết provenance.sh** |

---

## Thứ tự ưu tiên

1. **Merge Enforce** (đã commit `e12e8b6`) — bài kiểm #2 phụ thuộc hoàn toàn vào nó
2. **Viết `provenance.sh`** — bài kiểm #3, không có thì mất trắng
3. **Pin action SHA** — rẻ, nhanh, YC4 nói thẳng
4. **Pin base image digest** — cùng YC4
5. **Bật IaC gate** — cần thời gian xử finding phát sinh
6. **Thêm SAST** — nhiều thời gian nhất, ưu tiên cuối

Mục 1-2 là bắt buộc (mentor bấm nút trực tiếp). Mục 3-6 là điểm trừ nếu thiếu nhưng
không làm hỏng buổi demo.
