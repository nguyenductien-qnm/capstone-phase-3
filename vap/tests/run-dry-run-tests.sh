#!/usr/bin/env bash
# =============================================================================
# Mandate 05 - Test VAP bằng server-side dry-run (KHÔNG ghi gì vào cluster)
# Chạy thủ công:  bash run-dry-run-tests.sh
# Yêu cầu: đã đăng nhập SSO + kubectl trỏ đúng cluster ecommerce-dev-eks
# =============================================================================
set -uo pipefail

NS="techx-tf1"
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
  ["pos-01-valid.yaml"]=""
  ["pos-02-podlevel-nonroot.yaml"]=""
  ["pos-03-otel-exempt.yaml"]=""
  ["pos-04-digest-netbind.yaml"]=""
)

ORDER=(neg-01-root.yaml neg-02-image-latest.yaml neg-03-missing-resources.yaml \
       neg-04-privesc-caps.yaml neg-05-multi.yaml \
       neg-06-initcontainer-latest.yaml neg-07-privesc-absent.yaml \
       neg-08-no-caps-block.yaml neg-09-partial-resources.yaml \
       neg-10-podlevel-root.yaml \
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

  # 1) Policy kỳ vọng phải xuất hiện trong output
  missing=""
  for pol in ${EXPECT[$f]}; do
    if ! grep -q "$pol" <<<"$OUT"; then
      missing="$missing $pol"
    fi
  done

  # 2) Policy NGOÀI kỳ vọng không được xuất hiện (chống nhiễu chéo / false positive)
  unexpected=""
  for pol in run-as-non-root deny-floating-image-tag require-resources \
             deny-privilege-escalation psp-capabilities; do
    if ! grep -qw "$pol" <<<"${EXPECT[$f]}"; then
      grep -q "$pol" <<<"$OUT" && unexpected="$unexpected $pol"
    fi
  done

  if [[ -n "$missing" ]]; then
    echo "❌ FAIL — thiếu warning kỳ vọng:$missing"
    ((FAIL++))
  elif [[ -n "$unexpected" ]]; then
    echo "❌ FAIL — case hợp lệ nhưng bị bắt:$unexpected"
    ((FAIL++))
  else
    echo "✅ PASS — khớp kỳ vọng [${EXPECT[$f]:-không warning}]"
    ((PASS++))
  fi
  echo
done

echo "============================================================"
echo "TỔNG KẾT:  PASS=$PASS  FAIL=$FAIL  / ${#ORDER[@]} case"
echo "Lưu ý: binding đang ở action=Warn -> vi phạm hiện dạng Warning,"
echo "       pod vẫn 'configured (server dry run)'. Khi bật Deny (Phase 3)"
echo "       các case neg sẽ bị TỪ CHỐI (error) thật."
echo "============================================================"
