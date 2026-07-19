# Tasks: Checkout Kafka Failure Containment

Requirements: [requirements.md](./requirements.md)

Design: [design.md](./design.md)

This is an ordered implementation plan. Tasks are intentionally small and must be completed sequentially because the publisher interface is the dependency seam for the later tasks.

## Phase 0: Baseline and test seam

### CHK-001 — Capture the regression baseline

**Description:** Record the current Checkout/Kafka failure behavior and establish the test commands and telemetry queries used for comparison. Do not change production code.

**Acceptance criteria:**

- [x] The isolated unavailable-Kafka scenario is documented as a red regression: payment completes, Checkout connection closes, and the test process restarts/panics.
- [ ] The baseline normal-publish scenario is recorded. *(Publisher unit coverage exists; a sanitized live baseline artifact is still required.)*
- [ ] Test artifacts contain no card number, CVV, or full payment payload. *(No persisted live artifact has been added yet.)*

**Verification:** Run the isolated integration harness once and record sanitized status, restart count, and payment call count.

**Dependencies:** None.

**Files likely touched:** `src/checkout/test/` or an existing integration-test location; test documentation only.

**Estimated scope:** Small.

### CHK-002 — Add the publisher boundary and fake publisher

**Description:** Introduce `OrderEventPublisher` and inject it into Checkout so `PlaceOrder` can be tested without Sarama or a live Kafka broker.

**Acceptance criteria:**

- [x] `PlaceOrder` depends on the `OrderEventPublisher` interface rather than directly calling the Sarama producer.
- [x] Deterministic publisher tests cover success, unavailable, timeout, and queue-full outcomes.
- [x] Existing normal-path publisher behavior remains covered by a passing test.

**Verification:** Run the Checkout Go tests for the package and the new publisher tests.

**Dependencies:** CHK-001.

**Files likely touched:** `src/checkout/main.go`, new publisher file, test files.

**Estimated scope:** Medium.

## Phase 1: P0 containment

### CHK-003 — Make producer initialization failure safe

**Description:** Convert Sarama construction failure into an explicit unavailable publisher state. Ensure the request path cannot dereference a nil producer.

**Acceptance criteria:**

- [x] Unreachable Kafka cannot be dereferenced from the request path even when the producer remains nil.
- [x] A publish attempt returns `ErrKafkaProducerUnavailable` rather than panicking.
- [x] Checkout startup uses process liveness and readiness remains process-based; the unavailable-Kafka pod rolled out `Ready` and remained reachable through a temporary Kubernetes Service endpoint.
- [x] Checkout process remains alive after the failed publish; the isolated EKS Service-path request returned a completed order in 1.29 seconds with restart count unchanged at zero.

**Verification:** Run the regression test from CHK-001 and assert zero process restarts after the call.

**Dependencies:** CHK-002.

**Files likely touched:** `src/checkout/kafka/producer.go`, publisher implementation, tests.

**Estimated scope:** Medium.

### CHK-004 — Bound publish waiting and delivery result ownership

**Description:** Replace request-level reads from shared Sarama success/error channels with a single publisher-owned delivery loop and bounded publish admission/waiting.

**Acceptance criteria:**

- [x] A publish cannot wait beyond the configured timeout or request deadline.
- [x] The request path no longer reads shared Sarama success/error channels; one publisher result loop owns and correlates both channels.
- [x] Normal-path queue-full and post-admission timeout behavior are distinct and tested.
- [x] `RequiredAcks=NoResponse` remains explicit and success is documented as Sarama acceptance rather than broker durability.

**Verification:** Test success, broker error, timeout, and concurrent publish correlation with deterministic fakes.

**Dependencies:** CHK-003.

**Files likely touched:** `src/checkout/kafka/producer.go`, new publisher files, tests.

**Estimated scope:** Medium.

### CHK-005 — Preserve the BTC incident hook with safe result ownership

**Description:** Keep `kafkaQueueProblems` in the production Checkout path with the same key, `ffValue` additional messages, and asynchronous fan-out. Route each incident publish through the central publisher result owner so messages cannot consume another publish's result.

**Acceptance criteria:**

- [x] Checkout still evaluates `kafkaQueueProblems` through OpenFeature in the live EKS path; the shared BTC flag remained unchanged at its `off` variant during verification.
- [x] A value of `ffValue` creates exactly `ffValue` asynchronous additional publishes in the regression test.
- [x] Normal and incident publishes cannot consume each other's Sarama delivery result, including out-of-order completions.

**Verification:** Run a race-enabled correlation test with normal and incident publishes, then verify the BTC-controlled flag on an isolated Checkout deployment without editing flagd configuration.

**Dependencies:** CHK-004.

**Files likely touched:** `src/checkout/main.go`, publisher/test harness files, feature-flag test configuration if needed.

**Estimated scope:** Small.

## Checkpoint A: P0 review

- [x] Unit tests pass, including race-enabled tests and vet.
- [x] Unavailable Kafka no longer crashes Checkout in the isolated EKS request-path test.
- [x] Payment is called exactly once when the publisher returns unavailable in the `PlaceOrder` integration-style test.
- [x] Normal Kafka publisher acceptance and result correlation remain successful.
- [x] No sensitive payment data appears in new logs.

## Phase 2: Integration and observability

### CHK-006 — Add failure telemetry and sanitized logging

**Description:** Implement the metrics and log fields defined in [design.md](./design.md), including producer availability, queue-full, timeout, broker error, and success outcomes.

**Acceptance criteria:**

- [ ] Every publisher outcome maps to one low-cardinality result label. *(`producer_unavailable` was verified in Prometheus; the remaining outcomes still need runtime verification.)*
- [x] Publish duration and publisher availability are measurable; both were observed in Prometheus for the isolated EKS pod.
- [ ] Logs include order/event correlation without card data. *(Implemented with `order_id` and error class; runtime log verification remains.)*

**Verification:** Run the fake publisher matrix and query the emitted metrics; grep test logs for PAN/CVV-like fields.

**Dependencies:** CHK-004.

**Files likely touched:** publisher implementation, telemetry setup, tests, dashboard/alert configuration if required.

**Estimated scope:** Medium.

### CHK-007 — Promote the isolated EKS regression test

**Description:** Turn the manual test that reproduced the panic into a repeatable, isolated verification procedure. It must create and delete only temporary resources.

**Acceptance criteria:**

- [ ] Test Checkout uses an unreachable Kafka endpoint without changing the main Checkout deployment. *(A one-off isolated run passed; a repeatable repository harness is still required.)*
- [ ] The test asserts no panic/restart, one payment call, bounded latency, and failure telemetry. *(The one-off run plus unit test supplied this evidence, but the assertions are not yet automated in one harness.)*
- [ ] Cleanup is idempotent and verifies temporary resources are gone. *(Manual cleanup was run twice and verified; it is not yet encoded in the repeatable harness.)*

**Verification:** Run the procedure against the development cluster after deployment; save only sanitized results.

**Dependencies:** CHK-003, CHK-006.

**Files likely touched:** `scripts/validate/` or Checkout integration-test directory, this task document.

**Estimated scope:** Medium.

### CHK-008 — Validate controlled burst behavior

**Description:** Run baseline and unavailable-Kafka bursts with a bounded independent client. Do not depend on the current load-generator until its event-loop failure is fixed.

**Acceptance criteria:**

- [ ] Baseline and fault runs have comparable request volumes.
- [ ] Fault mode does not cause Checkout restart amplification.
- [ ] Payment calls do not exceed one per submitted order.
- [ ] p95, error rate, goroutine count, and queue depth are recorded.

**Verification:** Compare the two sanitized result sets and review the metrics before/after the run.

**Dependencies:** CHK-007.

**Files likely touched:** test harness and validation documentation.

**Estimated scope:** Small.

## Checkpoint B: Release readiness

- [ ] CHK-001 through CHK-008 complete.
- [x] `go test ./...`, race tests, and vet pass from `src/checkout` in the Go builder container.
- [x] Container build and isolated EKS deployment/Service validation pass.
- [ ] Rollback procedure is exercised or verified.
- [x] The known Outbox/event-loss limitation is accepted in [adr.md](./adr.md) and tracked as CHK-009.

## Phase 3: Follow-up, not part of this hotfix

### CHK-009 — Design durable order events

Create a separate approved specification for Outbox/Saga, idempotent payment keys, order states, event IDs, consumer idempotency, retry policy, and DLQ. Do not implement this under the minimal containment change without a new review.
