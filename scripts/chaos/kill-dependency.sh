#!/usr/bin/env bash
# CDO-224/235 (Mandate 17 — R1 verify): giết 1 dependency không-thiết-yếu rồi kiểm tra
# luồng ra tiền vẫn giữ SLO (nhờ circuit breaker + fallback ở frontend).
#
# KHÔNG chạy tự động. Chạy thủ công khi có cluster + kubeconfig đúng context.
#   ./kill-dependency.sh <service> [namespace] [seconds]
# Ví dụ:  ./kill-dependency.sh ad techx-develop 120
set -euo pipefail

SVC="${1:?Thiếu tên service, vd: ad hoặc recommendation}"
NS="${2:-techx-develop}"
DURATION="${3:-120}"

echo ">> Ghi lại số replica hiện tại của deploy/$SVC ..."
ORIG=$(kubectl -n "$NS" get deploy "$SVC" -o jsonpath='{.spec.replicas}')
echo "   replicas hiện tại = $ORIG"

echo ">> Giết dependency: scale deploy/$SVC về 0 (mô phỏng chết bất ngờ)"
kubectl -n "$NS" scale deploy "$SVC" --replicas=0

echo ">> Trong ${DURATION}s tới: MỞ storefront + thử browse -> cart -> checkout."
echo "   Kỳ vọng: trang vẫn load, block $SVC trống (degrade), checkout vẫn xong, SLO giữ trên Grafana."
sleep "$DURATION"

echo ">> Phục hồi: scale deploy/$SVC về $ORIG"
kubectl -n "$NS" scale deploy "$SVC" --replicas="$ORIG"

echo ">> Xong. Chụp Grafana (SLO/latency) trong khoảng thời gian trên làm evidence."
