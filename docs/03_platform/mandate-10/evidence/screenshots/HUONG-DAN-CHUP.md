# Hướng dẫn chụp bằng chứng — DIRECTIVE #10

Chụp theo thứ tự **A → B → C → D**. Mỗi nhóm là một lần ngồi, không nhảy qua lại.

| Nhóm | Nội dung | Khi nào chụp |
|---|---|---|
| **A** | Bằng chứng tĩnh — đọc từ repo/AWS | bất cứ lúc nào |
| **B** | Trạng thái Kyverno **trước** khi Enforce | **TRƯỚC** khi merge |
| **C** | Trạng thái Kyverno **sau** khi Enforce | **SAU** khi merge + sync root app |
| **D** | Ba bài kiểm mentor bấm nút | cuối cùng, khi mọi thứ đã xanh |

Đối chiếu tình trạng repo: [../AUDIT-DIRECTIVE-10.md](../AUDIT-DIRECTIVE-10.md)

## Chuẩn bị (dán 1 lần)

**Chạy mọi lệnh TRONG repo** (`cd ~/capstone-phase-3`) — các lệnh `grep`/`gh` cần
context git, đứng ở `~` sẽ báo "No such file" hoặc "not a git repository".

```bash
cd ~/capstone-phase-3
aws sso login --profile kienlht
export AWS_PROFILE=kienlht
export PROD=arn:aws:eks:us-east-1:804372444787:cluster/ecommerce-dev-eks
export EV=~/capstone-phase-3/docs/cdo09/evidence-mandate-10/evidence
alias k="kubectl --context $PROD"

# jq cần cho phần đọc SBOM
command -v jq >/dev/null || sudo apt install -y jq
```

## Credential ECR cho cosign (BẮT BUỘC nếu dùng WSL + Docker Desktop)

`~/.docker/config.json` trên WSL trỏ `credsStore: desktop.exe` — cosign chạy trong
WSL KHÔNG gọi được credential helper của Windows, nên mọi lệnh `cosign verify` sẽ
lỗi **401 Unauthorized**. Ghi credential vào một config riêng, không đụng Docker Desktop:

```bash
mkdir -p ~/.docker-cosign
AUTH=$(printf 'AWS:%s' "$(aws ecr get-login-password --region us-east-1)" | base64 -w0)
cat > ~/.docker-cosign/config.json <<EOF
{"auths":{"804372444787.dkr.ecr.us-east-1.amazonaws.com":{"auth":"$AUTH"}}}
EOF
export DOCKER_CONFIG=~/.docker-cosign
```

Token ECR sống **12 tiếng** — hết hạn thì chạy lại đoạn `AUTH=...` trên.

---

# NHÓM A — bằng chứng tĩnh (chụp lúc nào cũng được)

## A1 · Ruleset chặn merge  `A1-ruleset.png`
```bash
gh api repos/nguyenductien-qnm/capstone-phase-3/rules/branches/develop \
  --jq '.[] | select(.type=="required_status_checks") | .parameters.required_status_checks[].context'
```
Cần thấy 4 check: gitleaks, unit test ×2, helm lint.

## A2 · Trivy CVE là gate  `A2-trivy-gate.png`
```bash
grep -A6 "Trivy vulnerability scan" .github/workflows/app-build.yaml
```
Cần thấy `severity: CRITICAL,HIGH` + `exit-code: "1"`.

## A3 · ECR immutable  `A3-ecr-immutable.png`
```bash
aws ecr describe-repositories --repository-names ecommerce-dev-techx-corp \
  --region us-east-1 --query 'repositories[0].imageTagMutability' --output text
```
Cần thấy: `IMMUTABLE`

## A4 · Chữ ký + SBOM có thật  `A4-cosign-verify.png`
```bash
REG=804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp
ID="https://github.com/nguyenductien-qnm/capstone-phase-3/.github/workflows/app-build.yaml@refs/heads/develop"
TAG=$(k get deploy -n techx-tf1 frontend -o jsonpath='{.spec.template.spec.containers[0].image}' | sed 's/.*://;s/@.*//')
DG=$(aws ecr describe-images --repository-name ecommerce-dev-techx-corp --region us-east-1 \
      --image-ids imageTag=$TAG --query 'imageDetails[0].imageDigest' --output text)

cosign verify --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com "$REG@$DG"

cosign verify-attestation --type spdxjson --certificate-identity "$ID" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com "$REG@$DG" \
  | jq -r '.payload' | base64 -d | jq '.predicate.packages | length'
```
Lệnh sau in số package trong SBOM.

## A5 · Build chỉ đụng service đổi  `A5-build-scoped.png`
```bash
gh run list --workflow app-build.yaml --limit 10
gh run view <run-id>
```
Chọn run mà chỉ 1-2 service đổi, chụp job matrix chỉ có service đó.

---

# NHÓM B — Kyverno TRƯỚC khi Enforce

⚠️ **B3 và B4 mất cơ hội sau khi merge.** Chụp xong nhóm B mới được merge.

## B1 · Kyverno đang chạy  `B1-pods-kyverno.png`
```bash
k get pods -n kyverno
k get pdb -n kyverno
```
Cần thấy 4 pod Running 1/1, PDB ALLOWED DISRUPTIONS = 1.
(`kyverno-migrate-resources-*` trạng thái `Completed` là hook post-upgrade của chart,
đã chạy xong — không phải lỗi.)

## B2 · PolicyReport sạch  `B2-policyreport-sach.png`
```bash
k get policyreport -n techx-tf1 | head -12
k get policyreport -n techx-tf1 --no-headers | wc -l
```
Cần thấy PASS=1, FAIL=0 ở mọi dòng.

> **Lưu ý 23/07**: pod đã qua `mutateDigest` (image dạng `:tag@sha256:...`) từng
> KHÔNG có report vì `imageReferences` chỉ khai `:*`. Đã sửa thành 3 pattern.
> Sau khi merge, số report phải phủ HẾT pod dùng image techx-corp — kể cả aiops.

## B3 · TRƯỚC: pod không chữ ký VẪN ĐƯỢC NHẬN  `B3-truoc-unsigned-duoc-nhan.png` ⭐
```bash
k apply --dry-run=server -f $EV/pod-unsigned.yaml
```
Cần thấy: `pod/kyverno-test-unsigned created (server dry run)`
`--dry-run=server` nên không tạo pod thật, nhưng vẫn đi qua admission đầy đủ.

## B4 · Policy đang ở Audit  `B4-policy-audit.png`
```bash
k get clusterpolicy verify-image-signature \
  -o jsonpath='{.spec.validationFailureAction} / {.spec.failurePolicy}{"\n"}'
```
Cần thấy: `Audit / Ignore`

## B5 · ArgoCD app kyverno + kyverno-policies  `B5-argocd-apps.png`  [UI]
Chụp APP HEALTH + SYNC STATUS của cả hai.

---

# NHÓM C — Kyverno SAU khi Enforce

**Trước khi chụp nhóm này:**
1. Merge PR flip Enforce
2. Sync app **`techx-corp-root`** (App-of-Apps 2 tầng — sync app con là vô ích)
3. Kiểm tra:
```bash
k get clusterpolicy verify-image-signature \
  -o jsonpath='{.spec.validationFailureAction} / {.spec.failurePolicy}{"\n"}'
```
Phải ra `Enforce / Fail` mới chụp tiếp.

## C1 · SAU: pod không chữ ký BỊ CHẶN  `C1-sau-unsigned-bi-chan.png` ⭐⭐
```bash
k apply -f $EV/pod-unsigned.yaml
```
Cần thấy: error kèm message Kyverno. Chụp CẢ lệnh lẫn message.
**Đây là ảnh giá trị nhất toàn bộ mandate** — và cũng là bài kiểm D2.

## C2 · Pod đã ký vẫn tạo được  `C2-signed-van-tao-duoc.png`
```bash
k get deploy -n techx-tf1 frontend -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
# cập nhật tag trong $EV/pod-signed.yaml cho khớp, rồi:
k apply -f $EV/pod-signed.yaml
k get pod kyverno-test-signed -n techx-tf1 -o jsonpath='{.spec.containers[0].image}{"\n"}'
k delete pod kyverno-test-signed -n techx-tf1
```
Cần thấy: pod created, image bị mutate thành `:tag@sha256:...`
Chứng minh 2 việc: không chặn oan, và `mutateDigest` hoạt động.

## C3 · PolicyReport phủ HẾT pod  `C3-policyreport-day-du.png`
```bash
k get policyreport -n techx-tf1 --no-headers | wc -l
k get pods -n techx-tf1 --no-headers | wc -l
k get policyreport -n techx-tf1 | grep -E "NAME|aiops"
```
Cần thấy aiops **có** report — chứng minh fix 3 pattern `imageReferences` hiệu quả.

## C4 · Rollout thật không kẹt  `C4-rollout-khong-ket.png`
```bash
k rollout restart deploy/frontend -n techx-tf1
k rollout status deploy/frontend -n techx-tf1 --timeout=180s
```

## C5 · techx-corp vẫn Synced  `C5-techx-corp-van-synced.png`
```bash
k get app techx-corp -n argocd
```
Chụp sau ≥1 chu kỳ sync (~3 phút) kể từ C4.
Chứng minh `autogen-controllers: none` chặn được vòng lặp mutate ↔ selfHeal.

## C6 · Độ trễ sau Enforce  `C6-do-tre-sau-enforce.png`
```bash
for i in 1 2 3; do
  S=$(date +%s%N); k apply --dry-run=server -f $EV/pod-signed.yaml >/dev/null 2>&1; E=$(date +%s%N)
  echo "lần $i: $(( (E-S)/1000000 )) ms"
done
```
So với baseline: [../logs/01-baseline-admission-latency.txt](../logs/01-baseline-admission-latency.txt)

## C7 · Policy ở Enforce  `C7-policy-enforce.png`
```bash
k get clusterpolicy verify-image-signature \
  -o jsonpath='{.spec.validationFailureAction} / {.spec.failurePolicy}{"\n"}'
```
Cần thấy: `Enforce / Fail` — cặp với B4.

---

# NHÓM D — ba bài kiểm mentor bấm nút

## D1 · PR có CI đỏ → BỊ CHẶN MERGE  `D1-ci-do-chan-merge.png`

Dựng sẵn trước buổi demo (CI chạy vài phút, đừng tạo tại chỗ):
```bash
git checkout -b demo/ci-do origin/develop
# PHẢI nhắm vào checkout — đó là service DUY NHẤT có test thật trong required checks.
# product-catalog không có file _test.go nào (check luôn xanh), sửa nó không làm đỏ CI.
# Sửa 1 assert trong: techx-corp-platform/src/checkout/*_test.go
git commit -am "demo: cố tình làm đỏ CI để chứng minh gate"
git push -u origin demo/ci-do
gh pr create --base develop --title "DEMO: CI đỏ phải bị chặn" --body "Bài kiểm directive #10"
```
Chụp trang PR: nút **Merge bị khoá** + check đỏ.

## D2 · Image chưa ký → ADMISSION TỪ CHỐI  `D2-admission-tu-choi.png`
**Trùng với C1** — chụp một lần dùng hai chỗ.

Kể được câu chuyện: image `1.2-aiops-detector-ae89fa2` là chính image aiops push tay
ngày 17/07, trước khi vào app-build. *"Đây là image cũ của chính chúng tôi, giờ chính
hệ thống của chúng tôi từ chối nó."*

## D3 · Chỉ vào pod → TRUY NGƯỢC PROVENANCE  `D3-provenance-chain.png`
**Cần `scripts/provenance.sh`** — chưa có (xem AUDIT mục YC5).

```bash
./scripts/provenance.sh techx-tf1 <tên-pod>
```
Chuỗi phải hiện: digest → chữ ký + Rekor UUID → commit → PR ai duyệt → CI run pass → SBOM.
Chạy thử ≥3 pod trước demo: 1 pod chart bất kỳ, email, 1 pod aiops.

---

# Cặp before/after để cạnh nhau

| | Trước (B) | Sau (C) |
|---|---|---|
| Pod không chữ ký | **B3**: được nhận | **C1**: BỊ CHẶN |
| Chế độ policy | **B4**: Audit/Ignore | **C7**: Enforce/Fail |

**B3 ↔ C1 là cặp đắt nhất** — cùng một lệnh, hai kết quả trái ngược. Khi quay video,
giữ nguyên khung terminal và cỡ chữ để hai ảnh ghép cạnh nhau nhìn đối xứng.

---

# Lưu ý chung

- **App `kyverno` báo OutOfSync là bình thường**: chart khai `annotations: {}` và
  `labels: {}` (map rỗng) mà K8s không lưu field rỗng → diff không bao giờ hết.
  Vô hại. Chụp kèm APP HEALTH Healthy + 4 pod Running để không bị hiểu nhầm.
- **`Sync OK to 3.8.2` trên UI là phiên bản CHART**, không phải commit Git. Muốn
  chứng minh "đang chạy đúng code trong Git" thì chụp app `techx-corp-root`.

# Ảnh KHÔNG chụp được (repo chưa đạt)

Theo AUDIT còn 5 mục thiếu — đừng dựng ảnh giả:

| Mục | Thiếu gì |
|---|---|
| YC2b | IaC scan `exit-code: "0"` / `soft_fail: true` — chưa chặn |
| YC2d | không có SAST |
| YC4a | 19/22 action chưa pin SHA |
| YC4b | 55 dòng FROM chưa pin digest |
| YC5 | chưa có `provenance.sh` (chặn D3) |

Không kịp sửa thì **chủ động khai** trong phần "hạn chế đã biết" — tự khai finding
được điểm cao hơn để mentor tự tìm ra.
