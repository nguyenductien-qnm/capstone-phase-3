# ADR: Contain Checkout Kafka failures without altering BTC incident flags

- **Status:** Accepted for implementation
- **Date:** 2026-07-19
- **Signed by:** me-dangnhatminh
- **Pillar:** Reliability / Performance Efficiency / Auditability

## Context

Checkout can panic after payment when the Kafka producer is unavailable. Sarama also requires enabled success/error channels to be continuously drained. At the same time, `kafkaQueueProblems` is a BTC-owned production incident hook protected by `RULES.md` section 8.

## Decision

Introduce one `OrderEventPublisher` that owns the Sarama producer and exclusively consumes and correlates delivery results. Normal publication is bounded. The existing Checkout OpenFeature lookup and its `ffValue` asynchronous additional publishes remain active in production through a dedicated incident-publish method that does not weaken the injected pressure.

No flagd configuration, OpenFeature key, fan-out count, or production incident route is removed, redirected, or disabled.

## Consequences

- Normal Kafka unavailability cannot dereference a nil producer or wait indefinitely.
- Sarama success/error channels have one continuous consumer.
- Protected incident messages retain their configured pressure but receive correct result ownership.
- `RequiredAcks=NoResponse` remains unchanged; a successful result means Sarama accepted/sent the message, not broker durability.
- Durable delivery still requires the separate Outbox follow-up.

## Rollback

Roll back to the previous Checkout image through GitOps. No flagd or shared Kafka change is required.
