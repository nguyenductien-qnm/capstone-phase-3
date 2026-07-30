# After evidence — stepped sustained load

## Run identity

- Role: optimized/after evidence for Mandate 16.
- Runner location: local workstation; requests targeted the public
  `frontend-proxy` load balancer.
- Target: `http://k8s-techxdev-frontend-84edcba41b-35b30c8f5d0b2ce3.elb.us-east-1.amazonaws.com`.
- Timezone used by raw timestamps: UTC.
- Scheduled load window: `2026-07-22T05:31:38Z`–`05:56:38Z`
  (`12:31:38`–`12:56:38` Asia/Ho_Chi_Minh).
- Workspace branch: `feat/mandate16`.
- Workspace commit at capture time:
  `d657f726c910472dc19288cd94a7fda772886791`.
- `develop` reference at capture time:
  `1b5ab1b11ef87ee52b788bf52ee2e397ae10155b`.

The deployment intentionally used image-tag drift while Argo CD automated sync
was disabled. The following tags were observed before the load started:

| Service | Image tag |
|---|---|
| cart | `1.0-cart-e80b0dc` |
| checkout | `1.0-checkout-e80b0dc` |
| frontend | `1.0-frontend-e80b0dc` |
| frontend-proxy | `1.0-frontend-proxy-e80b0dc` |
| product-catalog | `1.0-product-catalog-e80b0dc` |

Currency was not part of this rollout. No flagd configuration or BTC flag was
changed for this test.

## Load profile

The stages ran consecutively without an idle gap:

| Stage | Users | Spawn rate | Duration | Steady-state window (UTC) |
|---|---:|---:|---:|---|
| 1 | 100 | 25 users/s | 5 minutes | `05:32:38`–`05:36:38` |
| 2 | 200 | 50 users/s | 5 minutes | `05:37:38`–`05:41:38` |
| 3 | 300 | 75 users/s | 15 minutes | `05:42:38`–`05:55:38` |

The machine-readable boundaries are in `stage-windows.tsv`.

## Results

### Grafana — server-side E2E

The latency screenshot covers `05:31:38Z`–`05:55:38Z`, one minute less than
the scheduled window. It reports:

| Metric | Value |
|---|---:|
| E2E p95 | 339 ms |
| E2E p99 | 776 ms |
| frontend p95 | 247 ms |
| checkout p95 | 187 ms |
| currency p95 | 74.0 ms |
| cart p95 | 44.3 ms |
| product-catalog p95 | 31.1 ms |
| shipping p95 | 21.2 ms |
| payment p95 | 2.27 ms |

For the adopted sustained-load budget of E2E p95 <= 500 ms and p99 <= 1 s,
the captured server-side result passes.

Grafana reports zero error rate for cart, checkout, frontend, payment,
product-catalog and shipping. It shows approximately `0.00416 errors/s` for
frontend-proxy and `1.58 errors/s` for flagd. The flagd telemetry must not be
misrepresented as failed storefront HTTP requests; Locust HTTP results are
reported separately below.

### Locust — client boundary

The final Locust aggregate contains:

| Metric | Value |
|---|---:|
| Requests | 67,430 |
| Failures | 31 (0.0460%) |
| Average throughput | 39.92 requests/s |
| Median | 310 ms |
| p95 | 1,300 ms |
| p99 | 1,800 ms |
| Maximum | 4,900 ms |

The 31 failures comprise 28 HTTP 503 responses and three checkout HTTP 500
responses. The checkout failures occurred between `05:54:03Z` and
`05:54:57Z`; tracing observed Currency RPCs exceeding the checkout dependency
deadline during that interval.

Locust and Grafana measure different boundaries. Locust includes workstation,
Internet/NLB waiting and a contaminated drain tail, while Grafana measures the
instrumented server-side request path. Their percentiles must not be mixed in
one before/after calculation.

## Kubernetes and cost evidence

The Kubernetes screenshot covers the full scheduled window and is filtered to
namespace `techx-develop`:

- four current and four ready nodes throughout the capture;
- zero pending pods and zero node-count changes;
- 49 running pods at the end of the window;
- frontend reached its HPA ceiling of 10 replicas during the 300-user stage;
- application pods in the critical path recorded zero restarts;
- the single restart shown by the dashboard was Prometheus, not an application
  service.

Immediate post-run inspection recorded Prometheus `OOMKilled`, exit code 137,
at `2026-07-22T05:48:18Z`. Grafana/Prometheus data around that instant may
therefore contain a short observability gap. This incident does not prove an
application failure, but it is a limitation of the monitoring evidence.

The node count remained four, so the result was not obtained by adding EC2
nodes. A strict CPU-hour comparison still requires equivalent before/after
Prometheus integrations; screenshots alone prove node-count parity, not exact
CPU-hour equality.

## Trace findings and retention limitation

Jaeger was queried during the run. The strongest observed traces were:

- `563ee3594a10014339fbb71cd5a7fbe4`: cart client-side wait exceeded the
  short cart/Redis server work;
- `6c757ee7b8213a9dd367cc44d83a92ad`: catalog server/PostgreSQL work was short
  relative to frontend client-side wait;
- `07e58652a64d9923b2160bd52dbfe57e` and
  `1639090364cd30fb1344e507c5974796`: Currency server work continued for about
  0.9–1.0 seconds after checkout clients reached a 750 ms deadline;
- `ba098193689d6a4f1fe4ca07eb243529`: representative frontend-proxy HTTP 503.

These traces expired from Jaeger before durable JSON/screenshot export and now
return HTTP 404. The IDs are operator notes, not submission-grade trace
artifacts. The existing `before/300-users` screenshots remain the durable trace
evidence used to identify frontend fan-out; a short targeted rerun is required
if the mentor requires an after-trace screenshot.

## Runner caveat

After the scheduled end, two Locust users remained alive because the Python
OpenFeature client raised `UnboundLocalError` while evaluating
`loadGeneratorFloodHomepage`. The process was stopped manually at approximately
`05:59:57Z`. Consequently:

- use `05:56:38Z` as the evidence cutoff;
- treat the final Locust aggregate as conservative because it includes the
  drain tail;
- retain `locust_exceptions.csv` as evidence of the runner issue;
- do not attribute this exception to a change in the BTC/flagd configuration.

## Artifact inventory

- `after-full-grafana-latency-20260722T053138Z-055538Z.png`: latency, service
  p95, request/error rate and pod resource panels.
- `after-full-grafana-k8s-20260722T053138Z-055638Z.png`: nodes, pods, HPA,
  restarts and resource overview.
- `locust_stats.csv`: final client-side endpoint and aggregate statistics.
- `locust_failures.csv`: grouped HTTP failures with first/last timestamps.
- `locust_exceptions.csv`: two load-runner exceptions during drain.
- `stage-windows.tsv`: exact stage boundaries.
