# Before run — 100 users (earlier run)

## Run identity

- Role: baseline/before; retained as a failed-dependency run.
- Users: 100.
- Local time: 2026-07-22 10:09:47–10:25:07 (Asia/Ho_Chi_Minh).
- UTC time: 2026-07-22 03:09:47–03:25:07.
- Duration: 15m20s.
- Source branch/commit used by the workload: not recorded by this run.
- `develop` at run end: `1b5ab1b11ef87ee52b788bf52ee2e397ae10155b`
  (`fix(product-reviews): regenerate protobuf files with 7.35.0`).

The `develop` SHA above is resolved from the local `develop` ref at the run-end
timestamp. It is a repository provenance anchor, not proof that every running
container was built from that commit.

## Aggregate Locust result

- Requests: 17,547.
- Failures: 12,624 (71.94%).
- Throughput: 19.49 requests/s.
- p50: 300 ms.
- p95: 600 ms.
- p99: 1,400 ms.
- Maximum: 5,100 ms.
- Failure class: all 12,624 recorded failures were HTTP 500.

Because failed fast responses are included in Locust percentiles, this run must
not be used as a clean latency-capacity baseline.

## Root-cause evidence

- `grafana-latency-errors.png`: exact-window latency/error overview.
- `grafana-k8s-overview.png`: 4 nodes, 45 running pods, 19 restarts and two
  HPAs at maximum during the captured window.
- `jaeger-error-search.png`: error trace search result.
- `jaeger-product-catalog-error-fb7485fbd111ff62412d55ddfe22aee7.png`:
  trace `fb7485fbd111ff62412d55ddfe22aee7` shows frontend
  `ProductCatalogService/GetProduct` failing with gRPC status 14 `UNAVAILABLE`
  and `ECONNREFUSED 172.20.196.32:8080`.

## Image provenance

The trace screenshot proves frontend tag `1.0-frontend-ec72350` for that trace.
The run did not capture a complete deployment/pod image inventory, so tags and
digests for the other services remain historically unproven.

The later live inventory at `../../k8s-live-images-20260722T0500Z.txt` is only a
curation reference and must not be presented as an exact snapshot of this run.

