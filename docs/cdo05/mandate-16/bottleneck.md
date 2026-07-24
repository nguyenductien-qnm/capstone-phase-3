# Mandate 16 bottleneck analysis

## Scope and evidence rule

This report describes the browse -> cart -> checkout critical path. It uses the
curated Grafana and Jaeger artifacts under `before/` and the optimized evidence
under `after/`.

The canonical 300-user baseline is the Grafana capture in
[`before/300-users`](before/300-users): E2E p95 1.95 s and p99 4.33 s. A roughly
12-second Locust task observed during investigation was a long multi-step
workload trace/spike. It is not the aggregate E2E p99 and is not used in the
before/after calculation.

The old planning notes were useful hypotheses, but their proposed TTLs,
timeouts and Kafka implementation do not describe the final code.

## Baseline symptoms

| Metric at 300 users | Before |
|---|---:|
| E2E p95 | 1.95 s |
| E2E p99 | 4.33 s |
| Frontend p95 | 1.39 s |
| Cart p95 | 354 ms |
| Checkout p95 | 278 ms |
| Product Catalog p95 | 78.4 ms |

The frontend accounted for most of the tail. The representative checkout trace
showed approximately 890 ms in the frontend route, only about 61 ms in the
checkout backend, followed by about 688 ms of Product Catalog enrichment.
The recommendation trace showed several Product Catalog lookups of roughly
225–300 ms each.

These measurements point to orchestration and queue amplification, not one slow
database query inside checkout.

## Root-cause chain

```text
Repeated/serialized frontend work
        + identical catalog misses
        + mutation followed by another cart RPC
        + no short cancellation deadline
                              |
                              v
more concurrent downstream RPCs and longer client wait
                              |
                              v
cart/frontend queueing and inflated E2E tail latency
```

The Locust `checkout_multi` workload adds three items sequentially before
checkout. It amplified the cost of every slow add-to-cart cycle, but changing
that workload was prohibited. The optimization therefore reduced the cost and
fan-out of each server-side operation.

## Findings and disposition

### B1. Frontend catalog enrichment and duplicate misses — Mitigated

**Evidence:** checkout backend work was short relative to frontend enrichment;
recommendation traces showed repeated Product Catalog calls.

**Cause:** product lists and items were repeatedly loaded and identical
concurrent misses were not coalesced. Checkout also enriches the returned order
for the UI after `PlaceOrder`.

**Implemented:** a 10-second per-process LRU uses Cache-Aside + Singleflight.
List results prime product entries, converted results are cached separately,
and USD skips Currency. Envoy additionally caches explicitly cacheable product
HTTP responses on each proxy replica.

**Boundary:** checkout still calls `listProducts` to satisfy the current API
response contract. The network work is normally reused from cache; the
enrichment step itself was not deleted. There is no standalone currency-rate
cache and no distributed frontend Valkey cache.

### B2. Serialized independent RPCs — Resolved for identified routes

**Evidence:** cart/recommendation API routes and checkout preparation paid
independent dependency latency sequentially.

**Implemented:** Cart + Product Catalog and Recommendation + Product Catalog
run concurrently. Checkout item preparation runs concurrently with the
shipping branch. Order items use a concurrency limit of four, and frontend
currency conversion uses at most 16 workers.

The limits prevent the fix from replacing serial delay with unbounded fan-out.

### B3. Extra cart round trip and cart backlog — Mitigated

**Evidence:** cart p95 was 354 ms while individual Valkey spans in sampled
traces were much shorter. The difference indicated client/service waiting and
contention rather than raw Redis execution alone.

**Implemented:** `AddItemAndGetCart` removes the frontend's separate `GetCart`
RPC after mutation. Cart uses four Valkey connections, fail-fast Valkey backlog
behavior, 1-second operation timeouts, and bounded admission of 64 active plus
64 queued requests per pod.

**Boundary:** the cart server still reads the cart after mutation, and storage
still uses protobuf read-modify-write. The optimization reduces network and
queue amplification; it does not prove serialization was the original 354 ms
or make concurrent item updates atomic.

### B4. Missing real dependency deadlines — Resolved for the critical RPC path

**Risk:** without cancellation, slow dependencies keep work alive after the
caller no longer benefits, increasing connection and task queues.

**Implemented:** frontend uses real `grpc-js` deadlines of 750 ms for Cart,
1 second for Product Catalog and Recommendation, and 2 seconds for Checkout.
Checkout dependency calls are also bounded. Optional data has a safe fallback;
required dependencies return a controlled error.

No frontend or Envoy retry was added.

### B5. Checkout per-item fan-out — Mitigated

**Evidence:** each cart item requires Product Catalog and Currency work, while
shipping requires another Currency conversion.

**Implemented:** item branches run with a maximum concurrency of four, shipping
runs in parallel, and checkout coalesces identical Product Catalog/Currency
requests with Go `singleflight`.

**Open tail:** one checkout can still create up to five concurrent Currency
RPCs (four item workers plus shipping), and additional items are processed in
later waves. Currency is therefore a remaining downstream tail-risk.

### B6. Kafka on the checkout path — Bounded, not durable

**Historical risk:** waiting indefinitely for Kafka can propagate queue delay
into checkout. Simply launching an untracked goroutine would hide failures and
lose delivery correlation.

**Implemented:** normal publishing correlates producer success/error and waits
for at most 250 ms. Timeout or delivery failure is logged and measured, and the
checkout response continues.

**Open correctness gap:** an accepted order event may be lost when Kafka is
unavailable. Transactional Outbox is the future durability solution. Saga is
only relevant if the broader payment/shipping/order workflow needs
compensation. The `kafkaQueueProblems` BTC incident path remains intact.

### B7. Currency tail latency — Open

Currency was not part of the optimized image rollout. After-run diagnostics
observed Currency server work continuing after the checkout client deadline,
and Currency p95 reached 74 ms in the aggregate screenshot.

Potential contributors found in code are synchronous OpenTelemetry log/span
processors, lack of server cancellation handling, and checkout fan-out. These
are supported hypotheses, not a proven single root cause because the after
Jaeger traces expired before export.

Recommended follow-up: use batch telemetry processors, honor cancellation,
add a same-currency fast path in checkout, and capture durable trace JSON before
and after the change.

## Before/after result

| Metric | Before 300 | After stepped run | Change |
|---|---:|---:|---:|
| E2E p95 | 1.95 s | 339 ms | -82.6% |
| E2E p99 | 4.33 s | 776 ms | -82.1% |
| Frontend p95 | 1.39 s | 247 ms | -82.2% |
| Cart p95 | 354 ms | 44.3 ms | -87.5% |
| Checkout p95 | 278 ms | 187 ms | -32.7% |
| Node count | 4 | 4 | unchanged |

The after capture passes the adopted server-side p95 <= 500 ms and p99 <= 1 s
budget without adding nodes. The table is strong dashboard evidence rather than
a perfectly controlled client A/B comparison: the historical before capture
lacks matching raw Locust data and its Kubernetes dashboard used a broader
namespace filter.

## Residual operational signals

- Locust recorded 31 failures out of 67,430 requests (0.0460%): 28 HTTP 503
  and three checkout HTTP 500 responses.
- Frontend reached its HPA maximum of 10 replicas at 300 users. It remains the
  first demonstrated capacity constraint even though the measured SLO passed.
- Four nodes remained ready and node count did not change.
- Prometheus, not an application pod, was OOMKilled during the after window;
  this may create a short metrics gap.
- flagd panel errors and load-runner OpenFeature exceptions are recorded as
  evidence limitations. They are not silently reclassified as storefront
  failures, and no BTC flag was changed.

## Status matrix

| Finding | Status | Proof or limitation |
|---|---|---|
| Frontend catalog fan-out | Mitigated | cache, priming, Singleflight; enrichment contract remains |
| Serialized independent calls | Resolved | parallel route and checkout branches |
| Extra frontend cart RPC | Resolved | `AddItemAndGetCart` |
| Cart/Valkey unbounded backlog | Resolved | bounded admission and fail-fast backlog |
| Missing critical RPC deadlines | Resolved | real client deadlines and cancellation |
| Checkout item fan-out | Mitigated | bounded concurrency and Singleflight |
| Kafka indefinite wait | Resolved | bounded 250 ms normal publish |
| Kafka event durability | Open | Transactional Outbox deferred |
| Currency tail/cancellation | Open | after trace unavailable; follow-up required |
| Cart atomic update schema | Open | Redis hash migration deferred |
| Durable after Jaeger artifact | Open evidence gap | observed IDs expired |

The accepted design and follow-up decisions are recorded in
[`adr.md`](adr.md).
