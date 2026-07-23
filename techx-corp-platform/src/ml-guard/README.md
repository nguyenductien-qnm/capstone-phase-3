# ml-guard v2

**ml-guard** is the central AI trust & safety policy service for TechX Corp Platform.

## Architecture

In **v2**, ml-guard has been migrated to an asynchronous gRPC server (`grpc.aio`) built on top of [Guardrails AI](https://github.com/guardrails-ai/guardrails).

### Key Features
1. **gRPC Interface:** Clients (e.g., `shopping-copilot` and `product-reviews`) call `CheckInput` and `CheckOutput` RPC methods. This completely removes the HTTP connection bottlenecks from v1.
2. **Centralized Policy:** All prompt injection, PII redaction, and grounding logic (mDeBERTa-XNLI) is defined in a single place using Guardrails AI. Clients are now thin gRPC wrappers.
3. **Concurrency:** CPU-bound inference for `torch` and `presidio` is executed inside a `ThreadPoolExecutor` to unblock the main asyncio event loop, drastically improving p95 latency under high load.
4. **Custom Validator:** Includes a custom `VietnameseMDeBERTaGrounding` validator to execute NLI tasks using our specific local models.

## Local Development

Ensure you have generated the gRPC code using `grpcio-tools`:
```bash
python -m grpc_tools.protoc -I../../pb --python_out=. --grpc_python_out=. ../../pb/ml_guard.proto
```

### Running the Server
```bash
python server.py
```
The server listens on `[::]:8090` by default.

### Running Tests
Tests use `pytest` or basic python scripts.
```bash
python test_grounding_decision.py
```

## Infrastructure Settings
- **Port:** `8090`
- **CPU Request:** `400m` (optimized)
- **CPU Limit:** `2000m` (burst inference)
- **Health Probes:** gRPC probes using `grpc_health_probe`.
