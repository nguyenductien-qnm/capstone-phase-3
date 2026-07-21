#!/usr/bin/env bash
# CDO-227/235 (Mandate 17 — R2 verify): mô phỏng mất trọn 1 AZ bằng cordon + drain toàn bộ
# node của AZ đó. Kỳ vọng pod dồn sang AZ còn lại (nhờ zone topologySpread + Karpenter
# minValues:2) và luồng ra tiền vẫn giữ SLO.
#
# KHÔNG chạy tự động. Cần AZ thật (vd: ap-southeast-1a).
#   ./drain-az.sh <zone>
set -euo pipefail

ZONE="${1:?Thiếu tên AZ, vd: ap-southeast-1a}"

echo ">> Các node thuộc AZ=$ZONE:"
kubectl get nodes -l "topology.kubernetes.io/zone=$ZONE" -o wide || true

read -r -p "Xác nhận cordon+drain các node trên? (yes/no) " ANS
[[ "$ANS" == "yes" ]] || { echo "Huỷ."; exit 1; }

for NODE in $(kubectl get nodes -l "topology.kubernetes.io/zone=$ZONE" -o name); do
  echo ">> cordon $NODE"
  kubectl cordon "$NODE"
  echo ">> drain $NODE"
  kubectl drain "$NODE" --ignore-daemonsets --delete-emptydir-data --timeout=120s || true
done

echo ">> AZ=$ZONE đã bị 'sập'. Kiểm tra: pod critical còn Running ở AZ khác, storefront + checkout vẫn chạy."
echo ">> Khôi phục sau khi đo xong: kubectl uncordon <node> cho từng node ở trên."
