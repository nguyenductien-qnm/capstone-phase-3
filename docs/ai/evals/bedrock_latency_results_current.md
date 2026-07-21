# Bedrock Latency Measurement

- Generated: 2026-07-21 01:41:19Z
- AWS region: `us-east-1`
- AWS profile: `default credential chain`
- Runtime API: `bedrock-runtime.converse`
- Timeout rule: measured end-to-end `flow_p95_s`, rounded up to nearest 0.1s.

| Flow | Role | Model | Runtime model ID | n | Flow P50 (s) | Flow P95 (s) | Per-call P95 (s) | Timeout (s) |
|---|---|---|---|---:|---:|---:|---:|---:|
| reviews | primary | `amazon.nova-lite-v1:0` | `us.amazon.nova-lite-v1:0` | 10 | 1.741 | 2.542 | 1.434 | 2.6 |
| reviews | fallback | `amazon.nova-micro-v1:0` | `us.amazon.nova-micro-v1:0` | 10 | 1.715 | 2.253 | 0.990 | 2.3 |
| copilot | primary | `amazon.nova-pro-v1:0` | `us.amazon.nova-pro-v1:0` | 10 | 3.069 | 6.861 | 2.970 | 6.9 |
| copilot | fallback | `amazon.nova-lite-v1:0` | `us.amazon.nova-lite-v1:0` | 10 | 2.350 | 2.663 | 1.536 | 2.7 |

Notes:
- Reviews flow latency is end-to-end for two Converse rounds.
- Copilot flow latency is end-to-end for the measured tool loop until end_turn or 5-tool cap.
- Per-call latency pools all Converse calls in the measured flow.
