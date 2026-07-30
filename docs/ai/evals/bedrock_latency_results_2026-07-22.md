# Bedrock Latency Measurement

- Generated: 2026-07-22 09:53:57Z
- AWS region: `us-east-1`
- AWS profile: `Phase3-CDO-PermissionSet-804372444787`
- Runtime API: `bedrock-runtime.converse`
- Timeout rule: measured end-to-end `flow_p95_s`, rounded up to nearest 0.1s.

| Flow | Role | Model | Runtime model ID | n | Flow P50 (s) | Flow P95 (s) | Per-call P95 (s) | Timeout (s) |
|---|---|---|---|---:|---:|---:|---:|---:|
| reviews | primary | `amazon.nova-lite-v1:0` | `amazon.nova-lite-v1:0` | 10 | 1.492 | 6.032 | 0.843 | 6.1 |
| reviews | fallback | `amazon.nova-micro-v1:0` | `amazon.nova-micro-v1:0` | 10 | 1.407 | 1.797 | 0.906 | 1.8 |
| copilot | primary | `amazon.nova-pro-v1:0` | `amazon.nova-pro-v1:0` | 10 | 3.101 | 10.266 | 6.078 | 10.3 |
| copilot | fallback | `amazon.nova-lite-v1:0` | `amazon.nova-lite-v1:0` | 10 | 2.047 | 2.734 | 1.421 | 2.8 |

Notes:
- Reviews flow latency is end-to-end for two Converse rounds.
- Copilot flow latency is end-to-end for the measured tool loop until end_turn or 5-tool cap.
- Per-call latency pools all Converse calls in the measured flow.
- Timeout is the raw end-to-end flow budget. Service env vars configure botocore per-call read timeouts,
  so production values must also respect per-call P95, retries, and the 30s Envoy route budget.
- This run used the direct model IDs used by the services and proves that the CDO SSO role can invoke
  Nova Pro, Lite, and Micro in `us-east-1`. It is retained as an access/outlier cross-check; deployed
  per-call timeouts remain `2.6/2.3s` for Reviews and `6.9/2.7s` for Copilot.
