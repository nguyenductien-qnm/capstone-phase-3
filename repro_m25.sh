#!/bin/bash
# repro_m25.sh — MANDATE-25: controlled degradation
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT_DIR/techx-corp-platform"

FLAG_FILE="src/flagd/demo.flagd.json"
EVIDENCE_DIR=${M25_EVIDENCE_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/repro-m25.XXXXXX")}
FLAG_BACKUP="$EVIDENCE_DIR/demo.flagd.json.before"
RESPONSE_FILE="$EVIDENCE_DIR/response.json"
COMPOSE_LOG_FILE="$EVIDENCE_DIR/compose-up.log"
FILTERED_LOG_FILE="$EVIDENCE_DIR/m25.log"

mkdir -p "$EVIDENCE_DIR"

restore_flag() {
  [[ -f "$FLAG_BACKUP" ]] || return 0
  python3 - "$FLAG_FILE" "$FLAG_BACKUP" <<'PY_RESTORE'
import json
import sys
from pathlib import Path

flag_file, backup_file = map(Path, sys.argv[1:])
original = backup_file.read_text(encoding="utf-8")
current = flag_file.read_text(encoding="utf-8")
original_data = json.loads(original)
expected_data = json.loads(original)
expected_data["flags"]["llmFaultGarbageOutput"]["defaultVariant"] = "on"
expected = json.dumps(expected_data, indent=2, ensure_ascii=False)

if current == expected:
    flag_file.write_text(original, encoding="utf-8")
else:
    current_data = json.loads(current)
    current_data["flags"]["llmFaultGarbageOutput"]["defaultVariant"] = (
        original_data["flags"]["llmFaultGarbageOutput"]["defaultVariant"]
    )
    flag_file.write_text(json.dumps(current_data, indent=2, ensure_ascii=False), encoding="utf-8")
PY_RESTORE
  rm -f "$FLAG_BACKUP"
  unset LLM_FAULT_GARBAGE_OUTPUT
  docker compose up -d --no-deps --force-recreate shopping-copilot >/dev/null 2>&1 || true
  echo ">>> Restored llmFaultGarbageOutput"
}
trap restore_flag EXIT
trap 'exit 130' INT TERM

python3 - "$FLAG_FILE" "$FLAG_BACKUP" <<'PY_TOGGLE'
import json
import sys
from pathlib import Path

flag_file, backup_file = map(Path, sys.argv[1:])
original = flag_file.read_text(encoding="utf-8")
data = json.loads(original)
flag = data["flags"]["llmFaultGarbageOutput"]
if "on" not in flag.get("variants", {}):
    raise SystemExit("llmFaultGarbageOutput has no 'on' variant")
backup_file.write_text(original, encoding="utf-8")
flag["defaultVariant"] = "on"
flag_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
PY_TOGGLE

echo "=== MANDATE-25 Repro ==="
echo ">>> Enabled llmFaultGarbageOutput"
export LLM_FAULT_GARBAGE_OUTPUT=true
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
docker compose build shopping-copilot 2>&1 | tee "$COMPOSE_LOG_FILE"
docker compose up -d --no-deps --force-recreate flagd ml-guard shopping-copilot \
  2>&1 | tee -a "$COMPOSE_LOG_FILE"
sleep "${M25_WAIT_SECONDS:-12}"

echo ">>> Sending real gRPC request..."
PYTHONPATH=src/shopping-copilot:src/product-reviews python3 - "$RESPONSE_FILE" <<'PY_GRPC'
import json
import sys
import time

import grpc
import shopping_copilot_pb2 as pb
import shopping_copilot_pb2_grpc as grpc_pb

channel = grpc.insecure_channel("localhost:3552")
grpc.channel_ready_future(channel).result(timeout=30)
request_id = f"repro-m25-{time.time_ns()}"
response = grpc_pb.ShoppingCopilotServiceStub(channel).ChatWithCopilot(
    pb.ChatWithCopilotRequest(
        question="tim kinh thien van",
        user_id=request_id,
        session_id=request_id,
    ),
    timeout=60,
)
evidence = {
    "degraded": response.degraded,
    "actionsTaken": [action.tool_name for action in response.actions_taken],
    "traceId": response.trace_id,
    "response": response.response,
}
text = json.dumps(evidence, ensure_ascii=False, indent=2)
open(sys.argv[1], "w", encoding="utf-8").write(text + "\n")
print(text)
if not response.degraded:
    raise SystemExit("FAIL: response.degraded is false")
if response.actions_taken:
    raise SystemExit("FAIL: malformed output reached tool execution")
PY_GRPC

sleep 1
docker compose logs --no-color --since "$STARTED_AT" shopping-copilot \
  | grep -E 'M25 fault injection|Garbage output blocked|Không cache câu trả lời degraded' \
  | tee "$FILTERED_LOG_FILE"
grep -q 'M25 fault injection: garbage output' "$FILTERED_LOG_FILE"
grep -q 'Garbage output blocked:' "$FILTERED_LOG_FILE"
grep -q 'Không cache câu trả lời degraded/fallback/rỗng' "$FILTERED_LOG_FILE"

echo ">>> PASS: degraded=true, actionsTaken=[], garbage blocked before tool execution"
echo ">>> Evidence: $EVIDENCE_DIR"
echo "=== Done ==="
