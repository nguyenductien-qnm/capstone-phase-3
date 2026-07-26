#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== MANDATE-14 Reproducibility Script ==="

echo "1. Chạy Built-in Cases"
python3 eval_mandate14.py

echo "2. Chạy Hidden Cases"
python3 eval_mandate14.py --cases hidden_cases.example.json

echo "3. Kiểm toán Evidence (Trace Audit)"
python3 trace_audit.py

echo "=== HOÀN TẤT ==="
echo "Report được lưu tại: docs/ai/evals/eval_mandate14_report.md"
echo "Evidence JSON kèm Spans được lưu tại: docs/ai/evals/evidence/"
