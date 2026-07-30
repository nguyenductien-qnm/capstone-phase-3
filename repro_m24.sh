#!/bin/bash
# repro_m24.sh — MANDATE-24: trace every model call
set -euo pipefail
cd "$(dirname "$0")/techx-corp-platform"
echo "=== MANDATE-24 Repro ==="
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN docker compose up -d --force-recreate shopping-copilot ml-guard 2>/dev/null
sleep 12
echo ">>> Sending request..."
TRACE_ID=$(PYTHONPATH=src/shopping-copilot:src/product-reviews python3 -c "
import grpc, sys; sys.path.insert(0,'src/shopping-copilot')
import shopping_copilot_pb2 as pb, shopping_copilot_pb2_grpc as grpc_pb
ch = grpc.insecure_channel('localhost:3552')
stub = grpc_pb.ShoppingCopilotServiceStub(ch)
req = pb.ChatWithCopilotRequest(question='tim kinh thien van', session_id='repro-m24')
resp = stub.ChatWithCopilot(req, timeout=60)
print(resp.trace_id)
" 2>&1)
echo "Trace ID: $TRACE_ID"
echo ">>> Trace content:"
docker compose exec -T valkey-cart redis-cli GET "trace:$TRACE_ID" 2>/dev/null | python3 -m json.tool
echo ""
echo ">>> Session chain:"
docker compose exec -T valkey-cart redis-cli SMEMBERS "trace:session:repro-m24" 2>/dev/null
echo ""
echo "=== Done ==="
