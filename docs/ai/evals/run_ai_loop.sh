#!/bin/bash
# Runner cho AI Engineering Optimization Loop
# Chạy: bash docs/ai/evals/run_ai_loop.sh
set -uo pipefail
cd "$(dirname "$0")"

echo "========================================================="
echo "  AI ENGINEERING OPTIMIZATION LOOP - RUNNER"
echo "========================================================="

MODE="${1:-sweep}"

echo "=== 1. Thực thi AI Optimization Loop (Mode: $MODE) ==="
python3 ai_engineering_loop.py --mode "$MODE"

echo
echo "=== 2. Tổng kết Optimization Ledger ==="
if [ -f "optimization_ledger.md" ]; then
  cat optimization_ledger.md
else
  echo "❌ Chưa tìm thấy optimization_ledger.md"
  exit 1
fi

echo
echo "✅ AI Engineering Optimization Loop hoàn tất thành công!"
