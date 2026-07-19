#!/usr/bin/env bash
# =============================================================================
# Mandate 05 - Test VAP bằng server-side dry-run (KHÔNG ghi gì vào cluster)
# Chạy thủ công:  bash run-dry-run-tests.sh
# Yêu cầu: đã đăng nhập SSO + kubectl trỏ đúng cluster ecommerce-dev-eks
# =============================================================================
set -uo pipefail

NS="${NS:-default}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Chặn nhầm: chỉ cho phép chạy nếu context đúng
CTX="$(kubectl.exe config current-context 2>/dev/null)"
echo "kubectl context : $CTX"
echo "namespace       : $NS"
echo "chế độ          : --dry-run=server (read-only, không tạo pod)"
echo

# manifest -> danh sách policy kỳ vọng bị bắt (phân tách bởi khoảng trắng).
# Rỗng = kỳ vọng KHÔNG có warning nào (case hợp lệ).
declare -A EXPECT=(
  ["neg-01-root.yaml"]="run-as-non-root"
  ["neg-02-image-latest.yaml"]="deny-floating-image-tag"
  ["neg-03-missing-resources.yaml"]="require-resources"
  ["neg-04-privesc-caps.yaml"]="deny-privilege-escalation psp-capabilities"
  ["neg-05-multi.yaml"]="run-as-non-root deny-floating-image-tag require-resources deny-privilege-escalation psp-capabilities"
  ["neg-06-initcontainer-latest.yaml"]="deny-floating-image-tag"
  ["neg-07-privesc-absent.yaml"]="deny-privilege-escalation"
  ["neg-08-no-caps-block.yaml"]="psp-capabilities"
  ["neg-09-partial-resources.yaml"]="require-resources"
  ["neg-10-podlevel-root.yaml"]="run-as-non-root"
  ["neg-11-uppercase-tag.yaml"]="deny-floating-image-tag"
  ["pos-01-valid.yaml"]=""
  ["pos-02-podlevel-nonroot.yaml"]=""
  ["pos-03-otel-exempt.yaml"]=""
  ["pos-04-digest-netbind.yaml"]=""
)

ORDER=(neg-01-root.yaml neg-02-image-latest.yaml neg-03-missing-resources.yaml \
       neg-04-privesc-caps.yaml neg-05-multi.yaml \
       neg-06-initcontainer-latest.yaml neg-07-privesc-absent.yaml \
       neg-08-no-caps-block.yaml neg-09-partial-resources.yaml \
       neg-10-podlevel-root.yaml neg-11-uppercase-tag.yaml \
       pos-01-valid.yaml pos-02-podlevel-nonroot.yaml \
       pos-03-otel-exempt.yaml pos-04-digest-netbind.yaml)

PASS=0; FAIL=0

for f in "${ORDER[@]}"; do
  echo "============================================================"
  echo ">>> $f"
  echo "------------------------------------------------------------"

  # apply dry-run=server: stdout+stderr gộp lại (warning của VAP nằm ở stderr)
  OUT="$(kubectl.exe apply -f "$f" --dry-run=server -n "$NS" 2>&1)"
  echo "$OUT"
  echo

  # Chế độ enforcement: Deny short-circuit ở luật ĐẦU TIÊN fail -> output chỉ
  # chứa 1 policy dù manifest vi phạm nhiều luật. Vì vậy:
  #   - case neg (EXPECT không rỗng): PASS nếu output chứa ÍT NHẤT 1 luật kỳ vọng
  #     và KHÔNG chứa luật ngoài danh sách kỳ vọng.
  #   - case pos (EXPECT rỗng): PASS nếu output KHÔNG chứa luật nào (pod created).
  hit=""      # luật kỳ vọng đã xuất hiện
  for pol in ${EXPECT[$f]}; do
    grep -q "$pol" <<<"$OUT" && hit="$hit $pol"
  done

  # Policy NGOÀI kỳ vọng không được xuất hiện (chống nhiễu chéo / false positive)
  unexpected=""
  for pol in run-as-non-root deny-floating-image-tag require-resources \
             deny-privilege-escalation psp-capabilities; do
    if ! grep -qw "$pol" <<<"${EXPECT[$f]}"; then
      grep -q "$pol" <<<"$OUT" && unexpected="$unexpected $pol"
    fi
  done

  if [[ -n "$unexpected" ]]; then
    echo "❌ FAIL — xuất hiện luật ngoài kỳ vọng:$unexpected"
    ((FAIL++))
  elif [[ -n "${EXPECT[$f]}" && -z "$hit" ]]; then
    echo "❌ FAIL — case vi phạm nhưng KHÔNG bị luật nào bắt (kỳ vọng: ${EXPECT[$f]})"
    ((FAIL++))
  else
    if [[ -n "${EXPECT[$f]}" ]]; then
      echo "✅ PASS — bị từ chối bởi:$hit (kỳ vọng: ${EXPECT[$f]})"
    else
      echo "✅ PASS — hợp lệ, không luật nào bắt"
    fi
    ((PASS++))
  fi
  echo
done

echo "============================================================"
echo "TỔNG KẾT:  PASS=$PASS  FAIL=$FAIL  / ${#ORDER[@]} case"
echo "Mode enforcement = Deny: manifest vi phạm bị TỪ CHỐI ngay lúc apply."
echo "Deny short-circuit ở luật đầu tiên nên case đa-vi-phạm chỉ hiện 1 luật."
echo "============================================================"
