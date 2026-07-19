# Design: Checkout Kafka Failure Containment

Status: Draft

Requirements: [requirements.md](./requirements.md)

Implementation order: [tasks.md](./tasks.md)

## 1. Design summary

Introduce a small `OrderEventPublisher` boundary between `PlaceOrder` and Sarama. `PlaceOrder` remains responsible for the existing synchronous order workflow and the protected BTC flag lookup, while Kafka is treated as bounded post-processing on the normal path. The publisher owns producer lifecycle, delivery-result consumption, correlation, timeout handling, and metrics.

The first release is a containment patch, not a distributed transaction. It prevents the observed nil-pointer crash and retry amplification. A durable Outbox remains the follow-up needed to guarantee event delivery.

## 2. Current failure path

```text
PlaceOrder
  -> Charge payment
  -> Ship order
  -> Empty cart
  -> Send email
  -> sendToPostProcessor
       -> KafkaProducerClient.Input()
       -> shared Successes()/Errors()
       -> nil producer or blocked channel
       -> panic / request stall / ambiguous result
```

The observed panic occurs because producer construction logs an error but leaves the client nil. The later condition checks only the broker address, not the producer. The current fan-out also starts `ffValue` goroutines without a bound.

## 3. Target flow

```text
PlaceOrder
  -> prepare cart/products/currency/shipping quote
  -> charge payment exactly once
  -> ship order
  -> empty cart
  -> send email (existing best effort)
  -> publisher.Publish(ctx, order event)
       |-- accepted: bounded enqueue / delivery worker
       |-- unavailable: metric + structured error, no panic
       |-- timeout/full: metric + bounded failure, no payment retry
  -> return the existing order response
```

The publisher is deliberately after payment and shipping, so its failure cannot replay money movement. The trade-off is that an event can be lost before the Outbox is implemented; this is explicit, observable, and tracked as follow-up work rather than hidden behind a crash.

## 4. Components and responsibilities

### 4.1 `OrderEventPublisher` interface

Define a narrow interface at the Checkout boundary:

```go
type OrderEventPublisher interface {
    Publish(ctx context.Context, event *pb.OrderResult) error
    PublishIncident(ctx context.Context, event *pb.OrderResult) error
    Close() error
}
```

`PlaceOrder` depends on this interface, not directly on Sarama. `Publish` is bounded by the request/configured timeout. `PublishIncident` deliberately preserves the BTC incident behavior without adding a timeout that would weaken the injected pressure. A fake implementation can deterministically return unavailable, timeout, queue-full, broker-error, or success for tests.

### 4.2 Sarama-backed publisher

The Sarama implementation must:

- Treat producer construction failure as an unavailable publisher, not a partially valid object.
- Consume producer success/error channels in one owner component.
- Correlate delivery results to the publish request using an internal result channel or message metadata; callers must not compete for Sarama channels.
- Do not add another unbounded internal queue. Normal-path admission to Sarama must be bounded; a blocked input is reported as queue-full/admission failure.
- Apply `min(request deadline, publish timeout)` to admission/waiting.
- Return typed errors that map to metrics and logs.
- Shut down with a bounded drain period.

The producer acknowledgement policy must be reviewed together with result handling. The current combination of `Return.Successes=true` and `RequiredAcks=NoResponse` is contradictory for a caller waiting on broker confirmation and must not be carried into a new publisher abstraction without an explicit decision.

### 4.3 `PlaceOrder` integration

Replace the direct `sendToPostProcessor` call with the interface. The integration must:

- Never call `Publish` when the publisher is unavailable without handling the error.
- Never retry the whole order workflow because `Publish` failed.
- Preserve the current response for the first release, while adding a post-processing failure metric and structured event.
- Avoid logging sensitive payment fields.
- Keep startup and liveness probes on the process-only `liveness` health service, and keep readiness process-based. Kafka post-processing availability is telemetry, not a reason to remove Checkout from Service endpoints.

The API contract should not change in this containment release. The future Outbox/Saga design can add a durable order status and explicit `POST_PROCESSING_PENDING` state.

### 4.4 Protected BTC incident injection

The existing `kafkaQueueProblems` hook remains in Checkout production code and continues to read the same OpenFeature key. When its integer value is positive, Checkout still launches `ffValue` asynchronous additional publishes. Those publishes use `PublishIncident`, so the central result consumer correlates each result without competing on Sarama channels, while the incident's fan-out and pressure are preserved. Shared EKS verification must not mutate the GitOps-managed flag source outside the BTC-controlled test procedure.

## 5. Error policy

| Condition | Publisher result | Checkout behavior | Required telemetry |
|---|---|---|---|
| Producer unavailable/nil | `ErrKafkaProducerUnavailable` | Do not panic; preserve first-release response | counter + alertable log |
| Queue full | `ErrKafkaPublishQueueFull` | Stop waiting at bound; no payment retry | counter |
| Publish timeout | `ErrKafkaPublishTimeout` | Stop waiting; no payment retry | counter + duration |
| Broker/delivery error | `ErrKafkaPublishFailed` | Do not replay workflow | counter + sanitized error |
| Normal delivery | `nil` | Existing response | success counter + duration |

No publisher error may call `Charge` again. No publisher error may trigger an unbounded goroutine or an unbounded retry loop.

## 6. Observability

Add low-cardinality metrics:

- `checkout_order_event_publish_total{result}`
- `checkout_order_event_publish_duration_seconds`
- `checkout_order_event_publisher_available`

No separate application queue is introduced, so there is no synthetic queue-depth metric. `queue_full` means normal-path admission to the existing Sarama input remained blocked until the configured bound.

Recommended log fields: `order_id`, `publish_result`, `duration_ms`, and a sanitized error class. Never log card number, CVV, raw request, or full email payload.

## 7. Verification strategy

### Unit tests

- nil/unavailable publisher does not panic;
- publisher timeout returns within the configured bound;
- queue-full behavior is deterministic;
- success/error results are correlated to the correct publish;
- `PlaceOrder` calls payment once even when publish fails.

### Integration-style test

Use the same isolated-replica pattern that reproduced the incident, but assert the post-fix behavior:

1. Start Checkout test replica with Kafka unavailable.
2. Seed one cart item.
3. Call `PlaceOrder` once.
4. Assert no process restart/panic.
5. Assert one payment call.
6. Assert bounded response latency and publish failure telemetry.
7. Delete all temporary resources.

### Load test

Run a bounded client burst only after the single-request failure test passes. Compare baseline and fault cases for Checkout p95, error rate, restarts, goroutines, and payment call count. The protected BTC flag may generate its configured incident pressure; the client harness itself remains bounded.

## 8. Rollout and rollback

Roll out the publisher change behind normal GitOps deployment controls. First verify with Kafka healthy, then run the isolated unavailable-Kafka test. Rollback is the previous Checkout image/configuration; no flag or shared Kafka mutation is required.

## 9. Follow-up architecture

The containment patch does not provide durable delivery. The next design must add an order/outbox transaction, event IDs, idempotent consumers, explicit order states, and payment status reconciliation. That work must not be smuggled into this minimal crash-containment change.
