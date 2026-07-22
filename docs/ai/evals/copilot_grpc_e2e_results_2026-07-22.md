# Shopping Copilot Real gRPC End-to-End Latency

- Generated: 2026-07-22 10:35:39Z
- Shopping Copilot target: `localhost:50052`
- Cart verification target: `localhost:56437`
- Path: gRPC client -> Shopping Copilot -> Bedrock -> real downstream gRPC tool -> Bedrock -> gRPC client.

| Intent | Expected tool | Pass | n | E2E P50 (s) | E2E P95 (s) | Tool gRPC P50 (ms) | Tool gRPC P95 (ms) |
|---|---|---:|---:|---:|---:|---:|---:|
| catalog_search | `search_products` | 10/10 | 10 | 3.742 | 4.263 | 53.5 | 92.0 |
| product_reviews | `get_product_reviews` | 10/10 | 10 | 4.960 | 6.689 | 78.0 | 95.0 |
| cart_read | `get_cart` | 10/10 | 10 | 4.023 | 4.455 | 53.5 | 68.0 |

## Confirmation gate

- Pending token returned: `True`
- Pending product ID correct: `True`
- Cart unchanged before confirmation: `True`
- Cart written only after confirmation: `True`
- Gate result: `PASS`
- Gate/confirmation latency: `3.664s/0.095s`

Notes:
- Bedrock model selection and AWS region are owned by the target Shopping Copilot process.
- Tool latency comes from `ToolCallRecord.duration_ms` emitted by the real agent.
- This local E2E benchmark includes host-to-container networking; repeat in EKS for production network evidence.
