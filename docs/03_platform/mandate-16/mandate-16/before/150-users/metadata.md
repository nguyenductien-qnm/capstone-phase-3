# Before run — 150 users

## Run identity

- Role: baseline/before
- Users: 150 (verified from `locust-stats-history.csv`)
- Local time: 2026-07-21 06:08:32–06:23:27 (Asia/Ho_Chi_Minh)
- UTC time: 2026-07-20 23:08:32–23:23:27
- Observed duration: 14m55s
- Ramp-up recorded by the source summary: 2 minutes (1.25 users/s)
- Target recorded by the source summary: external frontend-proxy ELB
- Workload snapshot: `locustfile.py`
- Historical `develop` commit at run end:
  `4543b8f707940341b32e5bbbac4f4f4da304bc72`
  (`docs(cdo09): Add Mandate 09 TBD1-TBD4 production evidence pack`).

The historical `develop` SHA was resolved from the local `develop` ref using
the UTC run-end timestamp. The exact target URL, Locust CLI, test-workspace
branch/commit and deployed image tags were not embedded in the CSV files. Do
not infer those values from filenames. The later live inventory at
`../../k8s-live-images-20260722T0500Z.txt` is a curation reference only and is
not proof of the images running during this historical test.

## Aggregate result

- Requests: 29,044
- Failures: 7 (0.0241%)
- Throughput: 32.30 requests/s
- p50: 330 ms
- p95: 700 ms
- p99: 1,300 ms
- Maximum: 4,900 ms

## Contents

- `locust-stats.csv`: final per-endpoint and aggregate statistics.
- `locust-stats-history.csv`: time-series data.
- `locust-failures.csv`: failure groups and occurrence counts.
- `locust-exceptions.csv`: Locust exceptions (header only).
- `locustfile.py`: workload snapshot supplied with the original evidence.
- `grafana-latency.png`: exact-window E2E, service latency, request/error rate,
  CPU and memory capture.
- `grafana-k8s-overview.png`: exact-window cluster resource/scaling capture.

## Grafana observations

The latency capture uses the exact CSV window and reports E2E p95 316 ms and
p99 895 ms. Service p95 values shown include frontend 199 ms, checkout 114 ms
and cart 34.8 ms. Core service error rates are zero except frontend-proxy at
0.00417 errors/s. These Grafana values are not substitutes for Locust's
client-side p95 700 ms and p99 1,300 ms; the two instruments measure different
boundaries.

The Kubernetes capture reports 4 current/ready nodes, 70 running pods, zero
pending pods, zero restarts and one HPA at its maximum. It is only partial
resource evidence because the dashboard is filtered to Namespace `All`, one
deployment appears to scale from 2 to 6 replicas, and CPU consumption has not
been integrated over the run.

This run is suitable as a 150-user baseline only. Pair it with after evidence
only when workload, target and infrastructure equivalence are documented.
