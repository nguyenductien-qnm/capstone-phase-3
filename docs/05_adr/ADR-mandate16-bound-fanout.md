# ADR-M16-001: Bound fan-out and downstream waiting on the storefront critical path

- Status: Accepted
- Date: 2026-07-22
- Decision owners: DANG NHAT MINH
- Scope: browse -> cart -> checkout under sustained load
- Implementation branch: `feat/mandate16`
- Evidence image revision: `e80b0dc`

## Context

The 300-user baseline exceeded the Mandate 16 server-side latency budget:
E2E p95 was 1.95 s and p99 was 4.33 s. The frontend alone contributed
1.39 s p95, while the checkout backend in the captured trace completed in
about 61 ms and the frontend then spent about 688 ms enriching the response
from Product Catalog.

Jaeger also showed repeated Product Catalog lookups in recommendation and
cart-oriented flows. Under load, independent calls were serialized, identical
catalog misses were duplicated, cart mutations caused another cart read, and
RPCs had no short client deadline. These effects amplified queueing even when
the downstream server work itself was short.

The solution must not change the Locust workload or the BTC/flagd behavior and
must not achieve the target by adding nodes.

## Decision

### 1. Use real dependency deadlines

Frontend unary RPCs use a shared `unaryWithDeadline` helper backed by the
`grpc-js` deadline option. This cancels the underlying call; it is not a
`Promise.race` that leaves work running after the caller has timed out.

| Dependency | Frontend deadline |
|---|---:|
| Cart | 750 ms |
| Product Catalog | 1,000 ms |
| Recommendation | 1,000 ms |
| Checkout | 2,000 ms |

Transient failure of optional recommendation/catalog enrichment returns an
empty fallback. Required cart and checkout failures are translated into a
controlled 503 or 504 response. Checkout additionally bounds its gRPC
dependency calls to 750 ms; shipping retains its separate 3-second HTTP
timeout.

No automatic retry is introduced in frontend or Envoy. A retry at these layers
would multiply downstream load precisely when a dependency is saturated.

### 2. Reduce and bound request fan-out

- `GET /api/cart` obtains Cart and the Product Catalog list concurrently.
- `GET /api/recommendations` obtains Recommendation and Product Catalog data
  concurrently.
- Checkout prepares order items concurrently with the shipping quote and its
  currency conversion.
- Checkout processes order items with a maximum concurrency of four instead of
  launching unbounded work or processing every item serially.
- Product Catalog currency conversion in frontend is bounded to 16 workers.

Cart mutation uses `AddItemAndGetCart`. This removes the second
frontend-to-cart RPC after `AddItem`. The cart server still reads the updated
cart after writing it, so the decision removes a network round trip and
frontend fan-out; it does not claim to remove the internal Valkey read.

### 3. Apply Cache-Aside with Singleflight

`ProductCatalog.service.ts` owns four per-frontend-process LRU caches:

| Cache | Capacity | TTL |
|---|---:|---:|
| Base product list | 1 | 10 seconds |
| Base products | 500 | 10 seconds |
| Converted product lists | 32 | 10 seconds |
| Converted products | 1,000 | 10 seconds |

The loading pattern is Cache-Aside. A per-key Singleflight map coalesces
concurrent misses, then double-checks the cache before loading. Listing products
primes the item cache, so later checkout enrichment normally reuses data rather
than issuing one catalog RPC per item. USD is a fast path and skips Currency.

Checkout response enrichment still calls `listProducts`; therefore the
post-checkout enrichment step was mitigated through reuse, not deleted from the
API contract.

The frontend-proxy adds an Envoy filesystem HTTP cache. Next.js marks product
API responses `public, max-age=3600, stale-while-revalidate=86400`. This cache
is local to each proxy replica and applies only to cacheable HTTP product
responses. It is not a shared Valkey cache and it is not a standalone currency
exchange-rate cache.

### 4. Bound cart admission and Valkey backlog

Cart admits at most 64 active and 64 queued requests per pod. Excess work fails
fast with gRPC `RESOURCE_EXHAUSTED` instead of growing an unbounded process
queue. Valkey uses a four-connection round-robin pool, a 2-second connection
timeout, a 1-second async/sync operation timeout, and
`BacklogPolicy.FailFast`.

This is overload protection, not a promise that every overload request will
succeed. The frontend maps saturation to a controlled response so the system
remains bounded.

### 5. Bound Kafka acknowledgement without weakening BTC flags

The normal order-event path waits for producer acceptance/delivery correlation
for at most 250 ms. Successes and failures are consumed centrally and recorded
with metrics and structured logs. Checkout logs a publishing failure and still
returns the order response; this favors checkout availability but does not
guarantee durable event delivery.

The `kafkaQueueProblems` incident path and `cartFailure` behavior are preserved.
No BTC/flagd flag or load-generator flag evaluation was changed as part of this
decision.

## Consequences

### Positive

- Independent latency is paid in parallel instead of cumulatively.
- Identical cache misses are coalesced within a pod.
- Real cancellation and bounded admission prevent abandoned work from growing
  queues indefinitely.
- No retry amplification is added.
- The full optimized window, including approximately 13 captured minutes at
  300 users, reached E2E p95 339 ms and p99 776 ms with four nodes, passing the
  adopted 500 ms / 1 s server-side budget.

### Trade-offs

- In-process caches are per pod; cold replicas do not share warm data.
- Proxy product responses may be one hour old and stale data may be served
  during revalidation for up to one day. This is acceptable for the demo's
  largely static product catalog, but would require explicit invalidation for
  frequently changing catalog or pricing data.
- Fail-fast admission converts excessive queueing into explicit 503/504-class
  errors. This is preferable to indefinite waiting but still requires capacity
  monitoring.
- `AddItemAndGetCart` couples mutation and readback at the RPC contract level.
- A bounded Kafka wait prevents checkout from hanging but can lose the event
  when Kafka is unavailable.

## Alternatives considered

### Add replicas or nodes

Rejected for this mandate. It would obscure the software bottleneck and add
cost; the after evidence retains four nodes.

### Add frontend or Envoy retries

Rejected because retries amplify fan-out and contention during dependency
degradation.

### Use only `Promise.race` for timeouts

Rejected because it returns control without cancelling the underlying RPC.

### Use a distributed frontend cache immediately

Deferred. It improves cross-pod hit rate but adds shared infrastructure,
failure modes and invalidation complexity. The bounded local cache was enough
to meet the measured SLO.

### Publish Kafka messages in an untracked goroutine

Rejected. It shortens the request path but loses delivery correlation and can
silently drop an event during process termination.

## Residual risks and follow-up decisions

These items are not claimed as completed by Mandate 16:

1. **Durable order events:** adopt a Transactional Outbox if an order must
   never be committed without a recoverable event. Use a relay with idempotent
   consumers and delivery observability. A Saga is a separate future option
   when payment, shipping and order creation require compensating actions; Saga
   alone is not the message-persistence mechanism.
2. **Currency tail latency:** evaluate batch OTLP processors, server-side
   cancellation checks, a USD-to-USD fast path in checkout, and lower fan-out.
   Currency was not included in the `e80b0dc` rollout.
3. **Cart write atomicity:** the store still performs protobuf
   read-modify-write. A future schema can use one Redis hash field per product
   and atomic quantity updates, with a tested migration plan.
4. **Cache correctness:** introduce versioned invalidation or a distributed
   cache only if catalog freshness requirements become stricter or per-pod
   hit-rate becomes inadequate.
5. **Capacity headroom:** frontend reached its HPA maximum at 300 users. Tune
   work and HPA policy using a controlled follow-up test before raising the
   stated capacity ceiling.
6. **Trace retention:** export Jaeger JSON immediately in a follow-up run if a
   durable after trace is required; the observed after trace IDs expired.

Product Reviews is explicitly outside this ADR. The load-generator workload,
BTC flags, node count, and business behavior are not optimization levers.

## Evidence and implementation references

- [`README.md`](README.md)
- [`bottleneck.md`](bottleneck.md)
- [`before/300-users/metadata.md`](before/300-users/metadata.md)
- [`after/metadata.md`](after/metadata.md)
- `techx-corp-platform/src/frontend/gateways/rpc/GrpcDeadline.ts`
- `techx-corp-platform/src/frontend/services/ProductCatalog.service.ts`
- `techx-corp-platform/src/frontend/pages/api/cart.ts`
- `techx-corp-platform/src/frontend/pages/api/recommendations.ts`
- `techx-corp-platform/src/checkout/main.go`
- `techx-corp-platform/src/checkout/kafka_publisher.go`
- `techx-corp-platform/src/cart/src/services/CartRequestAdmission.cs`
- `techx-corp-platform/src/cart/src/cartstore/ValkeyCartStore.cs`
- `techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml`

## Approval record

The technical interpretation and document structure were reviewed and accepted
on 2026-07-22. Repository history is the durable approval record.
