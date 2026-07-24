#!/usr/bin/env bash
# Dò service nào có unit test chạy được, giao với danh sách file đã đổi trong PR.
#
# Vì sao cần: matrix cứng trong platform-ci.yaml trước đây liệt kê tay
# [checkout, product-catalog] nên mắc 2 bệnh cùng lúc —
#   1. product-catalog KHÔNG có file _test.go nào, `go test ./...` in "no test files"
#      rồi trả 0, check luôn xanh, không bao giờ đỏ được (ô tích trống).
#   2. 12 file test của product-reviews/shopping-copilot/cart... viết ra từ lâu mà
#      không ai chạy, vì không ai nhớ mở workflow thêm tên vào.
# Script này chấm dứt cả hai: có test thật thì tự vào matrix, hết test thì tự rơi ra.
#
# Ghi ra GITHUB_OUTPUT 3 biến JSON array (rỗng `[]` nếu không có gì):
#   go / py / cs
#
# Dùng tay: .github/scripts/discover-tests.sh [base_ref]
#   không truyền base_ref -> quét toàn bộ, không lọc theo diff.

set -euo pipefail

SRC="techx-corp-platform/src"
BASE_REF="${1:-}"

# --------------------------------------------------------------------------- #
# Service tạm ngoài gate. CÓ file test nhưng pytest chưa chạy được — chi tiết ở
# issue #339, tác giả @dinh144. Cố ý KHÔNG sửa hộ test người khác: gỡ lớp
# try/except của recommendation có thể lộ lỗi thật, lúc đó lẫn lộn trách nhiệm.
#   recommendation : `tracer` chỉ gán trong __main__ (recommendation_server.py:202)
#                    nên gọi hàm trực tiếp -> NameError; thêm nữa try/except
#                    nuốt luôn AssertionError thành sys.exit(1).
#   ml-guard       : assert nằm trong hàm main(), pytest chỉ nhặt test_* -> collect 0.
#                    (chạy tay `python3 test_grounding_decision.py` thì OK)
#   llm            : code chạy thẳng top-level, không có hàm nào -> collect 0.
# Sửa xong thì XOÁ TÊN khỏi đây, job tự nhặt lại, không cần đụng gì khác.
# --------------------------------------------------------------------------- #
EXCLUDE="recommendation ml-guard llm"

is_excluded() {
  case " $EXCLUDE " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# Danh sách thư mục đã đổi dưới src/ (chỉ khi có base_ref).
# Không dùng mảng rỗng + `set -u` vì bash 4.3 nổ; dùng chuỗi cho an toàn.
changed_dirs=""
if [ -n "$BASE_REF" ]; then
  changed_dirs=$(git diff --name-only "$BASE_REF"...HEAD -- "$SRC" \
    | awk -F/ 'NF>3 {print $3}' | sort -u)
fi

# Service có đổi file không? Không truyền base_ref -> coi như đổi hết.
has_changed() {
  [ -z "$BASE_REF" ] && return 0
  printf '%s\n' "$changed_dirs" | grep -qx "$1"
}

go_list="" ; py_list="" ; cs_list=""

for dir in "$SRC"/*/; do
  svc=$(basename "$dir")

  is_excluded "$svc" && continue
  has_changed "$svc" || continue

  # --- Go: phải có go.mod VÀ ít nhất 1 file _test.go ---------------------- #
  # Điều kiện _test.go là thứ loại product-catalog ra: có go.mod nhưng 0 test.
  if [ -f "$dir/go.mod" ] && [ -n "$(find "$dir" -name '*_test.go' -print -quit)" ]; then
    go_list="$go_list $svc"
  fi

  # --- Python: phải có requirements.txt VÀ file test_*.py / *_test.py ----- #
  # Lưu ý: chỉ đếm file là CHƯA đủ (ml-guard/llm có file mà pytest collect 0),
  # nên bước chạy test dưới job còn kiểm lại bằng `--collect-only` và fail nếu
  # đếm về 0. Ở đây chỉ lọc thô cho nhanh.
  if [ -f "$dir/requirements.txt" ] && \
     [ -n "$(find "$dir" \( -name 'test_*.py' -o -name '*_test.py' \) -print -quit)" ]; then
    py_list="$py_list $svc"
  fi

  # --- .NET: phải có csproj test (xunit) --------------------------------- #
  # Ngoặc \( \) bắt buộc: thiếu nó thì -print -quit chỉ gắn vào nhánh -o cuối,
  # nhánh đầu khớp mà không in gì -> cart.tests.csproj bị bỏ sót.
  if [ -n "$(find "$dir" \( -name '*.tests.csproj' -o -name '*Tests.csproj' \) -print -quit 2>/dev/null)" ]; then
    cs_list="$cs_list $svc"
  fi
done

# In JSON array từ danh sách phân tách bằng khoảng trắng. Rỗng -> [].
# Tự nối chuỗi thay vì gọi jq: tên service chỉ có [a-z0-9-] nên không cần escape,
# và script chạy tay được trên máy không cài jq.
to_json() {
  local out="" svc
  for svc in $1; do
    out="$out,\"$svc\""
  done
  printf '[%s]' "${out#,}"
}

go_json=$(to_json "$go_list")
py_json=$(to_json "$py_list")
cs_json=$(to_json "$cs_list")

echo "Go     : $go_json"
echo "Python : $py_json"
echo ".NET   : $cs_json"
[ -n "$EXCLUDE" ] && echo "Bỏ qua : $EXCLUDE (xem issue #339)"

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "go=$go_json"
    echo "py=$py_json"
    echo "cs=$cs_json"
  } >> "$GITHUB_OUTPUT"
fi
