# Requirements: Checkout Kafka Failure Containment

Status: Draft

This document is the source of truth for the minimum-impact fix. The technical design is in [design.md](./design.md), and the ordered implementation work is in [tasks.md](./tasks.md).

## 1. Problem statement

Checkout currently treats post-processing Kafka publication as part of the synchronous request, while the payment and shipping side effects have already happened. When the Kafka producer cannot be created, `KafkaProducerClient` remains nil and `sendToPostProcessor` dereferences it. A controlled EKS test reproduced:

1. Checkout test replica configured with an unreachable Kafka broker.
2. Payment request completed before post-processing.
3. Checkout panicked at `src/checkout/main.go:672`.
4. The gRPC caller received `UNAVAILABLE: Socket closed`.
5. The test pod restarted once.

The normal path is visible at [`main.go:371-430`](../../../techx-corp-platform/src/checkout/main.go#L371-L430); payment is charged before the Kafka call at [`main.go:427-430`](../../../techx-corp-platform/src/checkout/main.go#L427-L430). The producer configuration and shared success channel are in [`kafka/producer.go:43-55`](../../../techx-corp-platform/src/checkout/kafka/producer.go#L43-L55).

## 2. Objective

Contain Kafka failure in Checkout with the smallest safe change set:

- Kafka post-processing failure must never crash the Checkout process.
- A completed payment must not be retried because Kafka failed.
- A Kafka failure must have bounded latency and be observable.
- The synchronous checkout response must not wait indefinitely for Kafka.
- Existing successful checkout behavior must remain compatible for callers.
- The design must leave a clear seam for a later durable Outbox/Saga implementation.

## 3. Scope

### In scope for the first implementation

- Guard producer initialization and publish calls against a nil/unavailable producer.
- Keep Checkout startup, readiness, and liveness independent of Kafka post-processing so an outage cannot create a restart loop or remove the revenue path from Service endpoints.
- Put a strict, configurable deadline on the Kafka publish attempt.
- Preserve the BTC-owned `kafkaQueueProblems` OpenFeature hook, key, production execution path, configured fan-out count, and asynchronous incident effect.
- Contain normal Kafka publication without disabling, redirecting, or weakening the protected incident mechanism.
- Centralize success/error consumption so one request cannot consume another request's Kafka result.
- Emit metrics and structured logs for publish accepted, publish failed, publish timed out, and producer unavailable.
- Add regression and integration-style tests for Kafka unavailable, Kafka timeout, and normal publish.
- Document the temporary delivery limitation and operational response.

### Explicitly out of scope for the first implementation

- Retrying `PaymentService.Charge`.
- Changing the public `PlaceOrder` protobuf contract.
- Introducing a database, order state machine, refund API, Outbox, or DLQ.
- Changing the central flag-control mechanism.
- Scaling or redesigning all Checkout downstream calls.

Those items are follow-up work, not prerequisites for stopping the observed panic.

## 4. Functional requirements

### FR-1: No panic on producer unavailability

If producer creation fails or the producer is nil, Checkout must remain ready and live and must not panic when a paid order reaches post-processing. Startup, readiness, and liveness must reflect process serving health rather than Kafka post-processing availability. The producer condition must be returned to the publisher layer as a typed/diagnosable error and exposed through telemetry.

### FR-2: Bounded publish

Each order event publish attempt must stop when the remaining request deadline or the configured publish timeout is reached, whichever comes first. The default timeout must be explicit and covered by tests; it must be short enough that Kafka cannot dominate checkout latency.

### FR-3: No payment retry coupling

Kafka failure must not invoke `Charge` again and must not cause Checkout to replay the entire order workflow. The regression test must assert exactly one payment call for the test order.

### FR-4: Bounded normal-path concurrency with protected incident compatibility

Normal order publication must not introduce new unbounded goroutines, buffers, or retries. The existing BTC-owned `kafkaQueueProblems` hook is an explicit protected exception: Checkout must continue reading the same flag in production and asynchronously submit exactly `ffValue` additional order messages. Refactoring result ownership must not disable, redirect, or reduce that incident effect.

### FR-5: Correct result ownership

A request must not read a shared Kafka success/error channel and assume the result belongs to its own message. Delivery results must be consumed once by a publisher component and correlated to the originating publish operation.

### FR-6: Existing order response compatibility

For a normal Kafka publish, `PlaceOrder` must preserve the current successful response shape. For Kafka post-processing failure after payment/shipping, the first implementation must not turn a completed payment into an automatic client retry signal. The response policy and its delivery limitation must be explicit in the design and runbook.

## 5. Non-functional requirements

- No new runtime dependency for the containment patch unless the existing dependency set cannot provide the required seam.
- No change to payment semantics or card data handling.
- No new unbounded memory, goroutine, or channel growth outside the protected BTC incident hook.
- Metrics must distinguish `producer_unavailable`, `queue_full`, `publish_timeout`, and `publish_error`.
- The implementation must be testable without a live Kafka cluster.
- The change must be deployable independently of the future Outbox work.

## 6. Acceptance criteria

The work is complete only when all are true:

- [ ] The reproduced unreachable-Kafka scenario no longer crashes or restarts Checkout.
- [ ] The same scenario makes exactly one payment call and produces no payment retry.
- [ ] A Kafka publish cannot hold the request beyond the configured bound.
- [ ] `kafkaQueueProblems` remains active in the production Checkout path and still asynchronously submits exactly `ffValue` additional messages without competing for another publish result.
- [ ] Normal publish tests pass, including delivery result correlation.
- [ ] Metrics/logs identify the Kafka failure mode without logging card data.
- [ ] A rollback and verification procedure is documented in [tasks.md](./tasks.md).

## 7. Constraints and safety boundaries

- Do not enable chaos flags in the shared cluster as part of implementation verification.
- Do not patch the GitOps-managed flag source for a one-off test.
- Use a fake publisher/unit seam and an isolated test replica for failure injection.
- Never include PAN, CVV, email, or full payment payloads in logs or test artifacts.
- The first release must prefer bounded post-processing loss with an explicit alert over a crash or payment replay; the durable event-delivery gap is tracked as follow-up work.

## 8. Open decisions for design review

1. Confirm the first-release response policy for an event that could not be published: return the completed order while marking post-processing pending, or return a non-retryable internal outcome through an existing field. The recommendation is to preserve the completed order response and surface the failure through metrics until an Outbox exists.
2. Set the publish timeout from measured production latency. The initial test default should be configurable and conservative, not treated as a production SLO.
3. Resolved: `kafkaQueueProblems` remains in the production Checkout path. It is protected BTC infrastructure and is not moved, disabled, bounded, or redirected by this change.
