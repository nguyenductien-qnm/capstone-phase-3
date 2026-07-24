# Bedrock Latency Measurement

- Generated: 2026-07-15 14:52:52Z
- AWS region: `us-east-1`
- AWS profile: `Phase3-CDO-PermissionSet-804372444787`
- Runtime API: `bedrock-runtime.converse`
- Timeout rule: measured end-to-end `flow_p95_s`, rounded up to nearest 0.1s.
- Access note: requested `us-east-1` runtime returned `ValidationException: Operation not allowed` for Nova/Titan with this SSO role. The same Nova inference profiles were invokable in `us-east-1`, so this run records real Bedrock latency there instead of using benchmark estimates.
- Resolution (2026-07-22): direct Nova Pro/Lite/Micro invocation now succeeds for the same CDO SSO profile in `us-east-1`; this note is retained only as historical context.

| Flow | Role | Model | Runtime model ID | n | Flow P50 (s) | Flow P95 (s) | Per-call P95 (s) | Timeout (s) |
|---|---|---|---|---:|---:|---:|---:|---:|
| reviews | primary | `amazon.nova-lite-v1:0` | `us.amazon.nova-lite-v1:0` | 10 | 1.571 | 3.969 | 0.859 | 4.0 |
| reviews | fallback | `amazon.nova-micro-v1:0` | `us.amazon.nova-micro-v1:0` | 10 | 1.578 | 1.938 | 1.047 | 2.0 |
| copilot | primary | `amazon.nova-pro-v1:0` | `us.amazon.nova-pro-v1:0` | 10 | 4.086 | 5.688 | 2.094 | 5.7 |
| copilot | fallback | `amazon.nova-lite-v1:0` | `us.amazon.nova-lite-v1:0` | 10 | 1.907 | 2.468 | 1.218 | 2.5 |

Notes:
- Reviews flow latency is end-to-end for two Converse rounds.
- Copilot flow latency is end-to-end for the measured tool loop until end_turn or 5-tool cap.
- Per-call latency pools all Converse calls in the measured flow.
