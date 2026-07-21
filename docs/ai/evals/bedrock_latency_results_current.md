# Bedrock Latency Measurement

- Generated: 2026-07-20 17:30:52Z
- AWS region: `us-east-1`
- AWS profile: `default credential chain`
- Runtime API: `bedrock-runtime.converse`
- Timeout rule: measured end-to-end `flow_p95_s`, rounded up to nearest 0.1s.

| Flow | Role | Model | Runtime model ID | n | Flow P50 (s) | Flow P95 (s) | Per-call P95 (s) | Timeout (s) |
|---|---|---|---|---:|---:|---:|---:|---:|
| reviews | primary | `amazon.nova-lite-v1:0` | `us.amazon.nova-lite-v1:0` | 10 | 1.725 | 2.673 | 1.028 | 2.7 |
| reviews | fallback | `amazon.nova-micro-v1:0` | `us.amazon.nova-micro-v1:0` | 10 | 1.739 | 2.320 | 1.353 | 2.4 |
| copilot | primary | `amazon.nova-pro-v1:0` | `us.amazon.nova-pro-v1:0` | 10 | 2.741 | 4.771 | 1.637 | 4.8 |
| copilot | fallback | `amazon.nova-lite-v1:0` | `us.amazon.nova-lite-v1:0` | 10 | 2.446 | 4.347 | 1.751 | 4.4 |

Notes:
- Reviews flow latency is end-to-end for two Converse rounds.
- Copilot flow latency is end-to-end for the measured tool loop until end_turn or 5-tool cap.
- Per-call latency pools all Converse calls in the measured flow.
