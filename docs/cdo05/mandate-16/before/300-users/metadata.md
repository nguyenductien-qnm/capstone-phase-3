# Before Run — 300 Users

## Load configuration

| Field | Value | Status |
|---|---:|---|
| Virtual users | 300 | Confirmed by filename/user record |
| Spawn rate | 75 users/s | Confirmed by filename/user record |
| Duration | 15 minutes | Confirmed by Grafana window |
| Grafana window | 2026-07-21 02:36–02:51 | Confirmed |
| Timezone | UNKNOWN | Manual confirmation required |
| Target URL | UNKNOWN | Manual confirmation required |
| Historical Git commit | UNKNOWN | Cannot resolve safely until screenshot timezone is confirmed |
| Current `develop` curation reference | `1b5ab1b11ef87ee52b788bf52ee2e397ae10155b` | Observed 2026-07-22 05:00 UTC |
| Image tags | UNKNOWN | Manual confirmation required |
| Locust file/hash | UNKNOWN | Manual confirmation required |

The current `develop` reference is
`fix(product-reviews): regenerate protobuf files with 7.35.0`. It is not
claimed as the historical commit for this run because the Grafana timezone is
unknown. Likewise, `../../k8s-live-images-20260722T0500Z.txt` records live
Kubernetes image tags and pod digests during evidence curation, but must not be
used as proof of the images running during this 300-user window.

## Grafana latency snapshot

| Metric | Value |
|---|---:|
| E2E p95 | 1.95 s |
| E2E p99 | 4.33 s |
| Frontend p95 | 1.39 s |
| Cart p95 | 354 ms |
| Checkout p95 | 278 ms |
| Product Catalog p95 | 78.4 ms |
| Shipping p95 | 43.7 ms |
| Currency p95 | 15.1 ms |
| Payment p95 | 7.32 ms |

Observed errors in the screenshot:

- flagd: 1.41 req/s;
- frontend-proxy: 0.0792 req/s;
- cart, checkout, frontend, payment and product-catalog: 0 req/s at capture time.

The dashboard request-rate panel is an internal per-service rate. It must not be
reported as the external Locust request rate.

## Kubernetes snapshot

| Metric | Value |
|---|---:|
| Current / ready nodes | 4 / 4 |
| Running / pending pods | 72 / 0 |
| Container restarts | 2 |
| HPAs at maximum replicas | 1 |
| Node-count changes | 0 |
| Highest visible node CPU | approximately 77% |

The screenshot is filtered to Namespace=All and Deployment=All. A second
snapshot filtered to `techx-develop` and the critical-path deployments is
required for the final resource comparison.

## Jaeger findings

### Recommendations trace

- Root operation: `user_get_recommendations`.
- Root duration: 2.27 s.
- Recommendation client span: approximately 822 ms.
- Recommendation server work: approximately 195 ms.
- Frontend performs multiple ProductCatalog `GetProduct` calls, each roughly
  225–300 ms. This is evidence of request fan-out/N+1 enrichment.
- Trace ID visible prefix: `8459a1b...`; the full ID and JSON are missing.

### Checkout trace

- Root operation: `user_checkout_single`.
- Root duration: 2.89 s, but this root includes load-generator time before the
  actual HTTP request and must not be used as HTTP E2E latency.
- Frontend-proxy HTTP span: approximately 1.19 s.
- Frontend `/api/checkout`: approximately 890 ms.
- Checkout backend server: approximately 61 ms.
- Frontend ProductCatalog enrichment after checkout: approximately 688 ms.
- Trace ID visible prefix: `cd97d7e...`; the full ID and JSON are missing.

## Preliminary bottleneck statement

The strongest current evidence points to frontend orchestration and catalog
fan-out, not checkout backend compute. The after run must show the same spans
reduced under the same 300-user profile without higher CPU, replicas or node
count and without a higher error rate.
