#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

export EVAL_BASE_URL="${EVAL_BASE_URL:-http://localhost:8080/api}"
JAEGER_PORT=$(docker compose -f ../../../techx-corp-platform/docker-compose.yml port jaeger 16686 | cut -d: -f2 || echo 32772)
export JAEGER_BASE_URL="${JAEGER_BASE_URL:-http://localhost:${JAEGER_PORT}}"

echo "=== MANDATE-14 Reproducibility Script ==="

echo "1. Chạy Built-in Cases"
TMP_OUT_BUILTIN=$(mktemp)
BUILTIN_STATUS=0
python3 eval_mandate14.py --enforce-hard-bars 2>&1 | tee "$TMP_OUT_BUILTIN" || BUILTIN_STATUS=$?
BUILTIN_DIR=$(grep "Evidence saved to:" "$TMP_OUT_BUILTIN" | sed 's/.*Evidence saved to: //' | tr -d '\r')
cp eval_mandate14_report.md builtin_report.md

echo "2. Chạy Hidden Cases"
TMP_OUT_HIDDEN=$(mktemp)
HIDDEN_STATUS=0
python3 eval_mandate14.py --cases hidden_cases.example.json --enforce-hard-bars 2>&1 | tee "$TMP_OUT_HIDDEN" || HIDDEN_STATUS=$?
HIDDEN_DIR=$(grep "Evidence saved to:" "$TMP_OUT_HIDDEN" | sed 's/.*Evidence saved to: //' | tr -d '\r')
cp eval_mandate14_report.md hidden_report.md

echo "3. Kiểm toán Evidence (Trace Audit)"
python3 trace_audit.py --dirs "$BUILTIN_DIR" "$HIDDEN_DIR"

echo "4. Báo cáo Chi phí & Độ trễ"
if [ -f "cost_before_after.py" ]; then
    python3 cost_before_after.py
fi

echo ""
echo "=== BẢNG TỔNG KẾT ==="

parse_report() {
    local report=$1
    local name=$2
    local status=$3
    
    local hard_bar="PASS"
    if [ "$status" -ne 0 ]; then
        hard_bar="FAIL"
    fi
    
    local pass_line=$(grep "\*\*Passed:\*\*" "$report")
    local passed=$(echo "$pass_line" | awk '{print $2}')
    local total=$(grep "\*\*Total Cases:\*\*" "$report" | awk '{print $NF}')
    local pass_rate=$(echo "$pass_line" | awk '{print $3}' | tr -d '()')
    
    local p50=$(grep "\*\*p50 Latency:\*\*" "$report" | awk '{print $NF}')
    local p95=$(grep "\*\*p95 Latency:\*\*" "$report" | awk '{print $NF}')
    local cost=$(grep "\*\*Average Cost/Req:\*\*" "$report" | awk '{print $NF}')

    local inj=$(grep "\*\*Injection Block Rate:\*\*" "$report" | awk '{print $NF}')
    local fbr=$(grep "\*\*False Block Rate:\*\*" "$report" | awk '{print $NF}')
    local faith=$(grep "\*\*Faithfulness Rate:\*\*" "$report" | awk '{print $NF}')
    local hall=$(grep "\*\*Hallucination Rate:\*\*" "$report" | awk '{print $NF}')
    local abst=$(grep "\*\*Abstention Rate:\*\*" "$report" | awk '{print $NF}')
    local task=$(grep "\*\*Task Success Rate:\*\*" "$report" | awk '{print $NF}')

    printf "| %-10s | %-14s | %-8s | %-7s | %-7s | %-7s | %-7s | %-7s | %-7s | %-8s | %-8s | %-9s |\n" \
           "$name" "$passed/$total $pass_rate" "$hard_bar" "$inj" "$fbr" "$faith" "$hall" "$abst" "$task" "$p50" "$p95" "$cost"
}

printf "| %-10s | %-14s | %-8s | %-7s | %-7s | %-7s | %-7s | %-7s | %-7s | %-8s | %-8s | %-9s |\n" \
       "Set" "Pass Rate" "Hard Bar" "Inj Blk" "Fls Blk" "Faith" "Halluc" "Abstain" "Task" "p50" "p95" "Cost/Req"
echo "|------------|----------------|----------|---------|---------|---------|---------|---------|---------|----------|----------|-----------|"
parse_report builtin_report.md "Built-in" "$BUILTIN_STATUS"
parse_report hidden_report.md "Hidden" "$HIDDEN_STATUS"
echo ""

# Clean up
rm -f "$TMP_OUT_BUILTIN" "$TMP_OUT_HIDDEN" builtin_report.md hidden_report.md

if [ "$BUILTIN_STATUS" -ne 0 ] || [ "$HIDDEN_STATUS" -ne 0 ]; then
    echo "❌ Một hoặc nhiều bộ test không vượt qua hard bar."
    exit 1
else
    echo "✅ Tất cả các bộ test đều vượt qua hard bar."
    exit 0
fi
