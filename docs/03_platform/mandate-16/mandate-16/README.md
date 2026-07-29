# Mandate 16 — Latency under sustained load evidence

## Objective and acceptance criteria

Mandate 16 requires the browse -> cart -> checkout path to reduce tail latency
under sustained load without buying performance through additional nodes and
without trading correctness for speed.

This evidence pack adopts the following server-side E2E budget for the
sustained stepped run whose longest and highest stage is 300 users:

- p95 <= 500 ms;
- p99 <= 1 second;
- core application service panels remain at zero error rate and any client
  failures are disclosed rather than excluded;
- node count does not increase relative to the baseline.

Client-side Locust percentiles and server-side Grafana percentiles are reported
separately because they measure different boundaries.

## Evidence layout

```text
mandate-16/
├── README.md        # evidence verdict and reproduction entry point
├── adr.md           # accepted decisions, trade-offs and follow-up work
├── bottleneck.md    # trace-led diagnosis and resolution status
├── before/
│   ├── 100-users/   # dependency-failure evidence; not a clean latency baseline
│   ├── 150-users/   # healthy Locust/Grafana baseline
│   ├── 300-users/   # sustained-load bottleneck and Jaeger evidence
│   └── runs/        # raw historical captures
├── after/           # curated optimized stepped run and metadata
└── test/            # repeatable local load-test and capture scripts
```

Start with:

1. [`before/300-users/metadata.md`](before/300-users/metadata.md) for the
   high-load baseline and trace-discovered bottleneck.
2. [`after/metadata.md`](after/metadata.md) for the optimized run, provenance,
   results and evidence limitations.
3. [`bottleneck.md`](bottleneck.md) for the trace-led diagnosis and the
   resolved/mitigated/open matrix.
4. [`adr.md`](adr.md) for the accepted implementation decisions and trade-offs.
5. The matching Grafana screenshots in the before/after directories.

## Test method

The optimized run was generated locally against the public frontend-proxy load
balancer using consecutive stages:

| Users | Spawn rate | Duration |
|---:|---:|---:|
| 100 | 25 users/s | 5 minutes |
| 200 | 50 users/s | 5 minutes |
| 300 | 75 users/s | 15 minutes |

The 300-user stage is the sustained capacity test. No idle delay was inserted
between stages. Exact UTC windows are stored in
[`after/stage-windows.tsv`](after/stage-windows.tsv).

## Before versus after

The 300-user before capture and the full stepped after capture show:

| Metric | Before | After | Change |
|---|---:|---:|---:|
| E2E p95 | 1.95 s | 339 ms | -82.6% |
| E2E p99 | 4.33 s | 776 ms | -82.1% |
| frontend p95 | 1.39 s | 247 ms | -82.2% |
| cart p95 | 354 ms | 44.3 ms | -87.5% |
| checkout p95 | 278 ms | 187 ms | -32.7% |
| nodes | 4 | 4 | no increase |

The optimized full-window result passes the adopted p95/p99 budget while the
node count remains unchanged. Its screenshot includes approximately 13 minutes
of the final 300-user stage. The before capture used a broader dashboard
namespace filter and lacks matching raw Locust CSV, so this table is strong
visual evidence but not a mathematically exact client-side A/B experiment.

The healthy 150-user baseline is preserved separately. It must not be compared
directly with the stepped after aggregate because user count, duration and load
shape differ.

## Bottleneck and optimization evidence

The before traces show that the dominant delay was frontend orchestration and
fan-out rather than checkout compute alone:

- repeated ProductCatalog enrichment increased request fan-out;
- cart mutations required an additional GetCart round trip;
- downstream calls were serialized or allowed to wait without a real gRPC
  cancellation deadline;
- under load, client-side gRPC waiting greatly exceeded actual cart/catalog
  server work.

The optimized images apply true dependency deadlines, parallelize independent
calls, bound checkout fan-out and return updated cart data from the mutation
path so frontend does not immediately issue another GetCart. Product data uses
a 10-second per-process Cache-Aside LRU with Singleflight, while cacheable
product HTTP responses use the proxy's local filesystem cache. No
Envoy/frontend retry was added, avoiding retry amplification.

The historical roughly 12-second observation was a long multi-step Locust
task/trace, not the aggregate E2E p99. The canonical baseline p99 for this pack
is the 4.33-second value shown by the 300-user Grafana capture.

The remaining tail-risk is Currency during checkout fan-out. Currency performs
only in-memory arithmetic, but its synchronous OTLP log/span processors can
block the request path. A checkout can create up to five concurrent Currency
RPCs, and the server does not stop work after client cancellation. This is a
follow-up optimization, not evidence that the after E2E SLO failed.

## Reliability and cost interpretation

- Core cart, checkout, frontend, payment, product-catalog and shipping panels
  show zero error rate in the after Grafana capture.
- Locust recorded 31 failures in 67,430 requests (`0.0460%`): 28 HTTP 503 and
  three checkout HTTP 500 responses.
- The after run used four nodes throughout; no node was added.
- Frontend reached HPA max replicas at 300 users, so frontend remains the first
  capacity constraint even though E2E p95/p99 stayed within budget.
- One dashboard restart belongs to Prometheus, which was OOMKilled at
  `05:48:18Z`; application pods did not restart.
- flagd/BTC configuration was not changed. The flagd error panel and the two
  load-runner OpenFeature exceptions are documented, not hidden.

## Evidence limitations

- After-run Jaeger traces expired before export and now return HTTP 404. Trace
  IDs in `after/metadata.md` are diagnostic notes, not durable artifacts.
- The after latency screenshot ends one minute before the scheduled test end;
  the Kubernetes screenshot covers the full window.
- The final Locust aggregate includes a short contaminated drain tail; the
  canonical cutoff is `05:56:38Z`.
- Prometheus restarted during the 300-user stage, creating a possible metrics
  gap around `05:48:18Z`.
- Screenshots establish node-count parity, not an exact CPU-hour comparison;
  an exact cost comparison would require equivalent Prometheus integrations.

If the mentor requires a durable after trace, rerun a short 300-user capture
and export the Jaeger JSON and screenshot immediately while the trace remains
inside retention.

## Final disposition

Mandate 16's adopted server-side p95/p99 targets were met across the captured
stepped window, including approximately 13 minutes at 300 users, without adding
nodes and without changing BTC flags. Remaining risks—Currency tail behavior,
event durability, cart atomic updates, cache invalidation and frontend capacity
headroom—are deliberately recorded in the ADR rather than presented as
completed work.
