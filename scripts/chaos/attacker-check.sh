#!/usr/bin/env bash
# CDO-231/234/236 (Mandate 17 — R3/R4 verify): chạy pod "attacker" chứng minh containment.
# Yêu cầu: đã bật networkPolicy.enabled=true trên cluster.
# Kỳ vọng:
#   - Không kết nối được sang service khác không nằm trong allow-rules (lateral movement bị chặn).
#   - Không gọi ra Internet (không có label egress-internet).
#   - Không gọi được K8s API ngoài quyền tối thiểu (R4).
#
# KHÔNG chạy tự động.  ./attacker-check.sh [namespace]
set -euo pipefail
NS="${1:-techx-develop}"

echo ">> Tạo pod attacker (netshoot) trong namespace $NS ..."
echo "   Chạy các lệnh sau BÊN TRONG pod và chụp kết quả:"
cat <<'EOF'
  # (1) Lateral movement — PHẢI timeout/refused:
  nc -zv -w5 cart 7070
  nc -zv -w5 checkout 5050
  nc -zv -w5 payment 50051

  # (2) Egress ra Internet — PHẢI fail (không có label egress-internet: "true"):
  curl -m5 https://www.google.com

  # (3) DNS vẫn phải hoạt động (được phép):
  nslookup cart

  # (4) Least-privilege K8s API (R4) — PHẢI "no":
  kubectl auth can-i list pods -A 2>/dev/null || echo "kubectl bị chặn / không có token (mong đợi)"
EOF

echo
echo ">> Mở shell attacker (Ctrl-D để thoát, pod tự xoá):"
kubectl -n "$NS" run attacker --rm -it --image=nicolaka/netshoot --restart=Never -- /bin/bash
