package main

import (
	"context"
	"errors"
	"log/slog"
	"testing"
	"time"

	"go.opentelemetry.io/otel"
	"google.golang.org/grpc/codes"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/status"
)

func init() {
	tracer = otel.Tracer("checkout")
	logger = slog.Default()
}

func TestReadinessGateAbsorbsOneFailedPing(t *testing.T) {
	t.Parallel()

	gate := newReadinessGate()
	if status, changed := gate.observe(true); !changed || status != healthpb.HealthCheckResponse_SERVING {
		t.Fatalf("first successful ping must report SERVING, got %v changed=%v", status, changed)
	}

	// A switchover blip is absorbed by the retry path; withdrawing the pod on the
	// first failed ping would cost capacity exactly when it is needed.
	if status, changed := gate.observe(false); changed {
		t.Fatalf("one failed ping must not change readiness, got %v", status)
	}
	if status, changed := gate.observe(true); changed {
		t.Fatalf("recovery inside the threshold must not change readiness, got %v", status)
	}
}

func TestReadinessGateWithdrawsAndRecovers(t *testing.T) {
	t.Parallel()

	gate := newReadinessGate()
	gate.observe(true)

	for i := 1; i < dbReadinessFailureThreshold; i++ {
		if _, changed := gate.observe(false); changed {
			t.Fatalf("readiness changed after %d of %d failures", i, dbReadinessFailureThreshold)
		}
	}
	if status, changed := gate.observe(false); !changed || status != healthpb.HealthCheckResponse_NOT_SERVING {
		t.Fatalf("threshold failures must report NOT_SERVING, got %v changed=%v", status, changed)
	}
	if _, changed := gate.observe(false); changed {
		t.Fatal("staying down must not re-report the same status")
	}

	if status, changed := gate.observe(true); !changed || status != healthpb.HealthCheckResponse_SERVING {
		t.Fatalf("one successful ping must restore readiness, got %v changed=%v", status, changed)
	}
}

func TestReadDependencyRetriesOneTransientFailure(t *testing.T) {
	t.Parallel()

	calls := 0
	got, err := readDependency(context.Background(), checkoutDependencyTimeout, func(context.Context) (string, error) {
		calls++
		if calls == 1 {
			// What an index build looks like to the caller: the dependency is up,
			// the one cold read just outran the per-attempt timeout.
			return "", status.Error(codes.DeadlineExceeded, "cold read")
		}
		return "product", nil
	})
	if err != nil {
		t.Fatalf("second attempt must succeed, got %v", err)
	}
	if got != "product" {
		t.Fatalf("got %q, want %q", got, "product")
	}
	if calls != 2 {
		t.Fatalf("made %d calls, want 2", calls)
	}
}

func TestReadDependencyDoesNotRetryPermanentFailure(t *testing.T) {
	t.Parallel()

	calls := 0
	_, err := readDependency(context.Background(), checkoutDependencyTimeout, func(context.Context) (string, error) {
		calls++
		return "", status.Error(codes.NotFound, "no such product")
	})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("want NotFound, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("made %d calls, want 1: a missing product does not appear on a retry", calls)
	}
}

func TestReadDependencyStopsWhenCallerGaveUp(t *testing.T) {
	t.Parallel()

	ctx, cancel := context.WithCancel(context.Background())
	calls := 0
	_, err := readDependency(ctx, checkoutDependencyTimeout, func(context.Context) (string, error) {
		calls++
		cancel()
		return "", status.Error(codes.Unavailable, "dependency restarting")
	})
	if err == nil {
		t.Fatal("want the transient error back, got nil")
	}
	if calls != 1 {
		t.Fatalf("made %d calls, want 1: retrying spends budget the caller no longer owns", calls)
	}
}

func TestReadDependencyStaysInsideCallerDeadline(t *testing.T) {
	t.Parallel()

	// Half of one attempt: the retry must not be able to push past the parent.
	budget := checkoutDependencyTimeout / 2
	ctx, cancel := context.WithTimeout(context.Background(), budget)
	defer cancel()

	start := time.Now()
	_, err := readDependency(ctx, checkoutDependencyTimeout, func(rpcCtx context.Context) (string, error) {
		<-rpcCtx.Done()
		return "", status.FromContextError(rpcCtx.Err()).Err()
	})
	elapsed := time.Since(start)

	if err == nil {
		t.Fatal("want an error once the caller deadline expires")
	}
	if elapsed > checkoutDependencyTimeout {
		t.Fatalf("spent %v, which is past the caller budget of %v", elapsed, budget)
	}
	if !errors.Is(ctx.Err(), context.DeadlineExceeded) {
		t.Fatalf("caller context should be the thing that expired, got %v", ctx.Err())
	}
}

func TestDependencyChainLeavesRoomToPersistTheOrder(t *testing.T) {
	t.Parallel()

	// GrpcDeadline.ts gives checkout 10s for the whole PlaceOrder call. Raising
	// the product read has to stay inside that with room left to write the row,
	// otherwise a slow dependency turns into a lost order instead of a slow one.
	retried := func(perAttempt time.Duration) time.Duration {
		return perAttempt * time.Duration(checkoutDependencyAttempts)
	}
	convert := retried(checkoutDependencyTimeout)

	// prepareOrderItemsAndShippingQuoteFromCart fans these two out and waits for
	// both, so the slower one sets the pace.
	productBranch := retried(checkoutProductReadTimeout) + convert
	shippingBranch := 3*time.Second + convert
	prepare := productBranch
	if shippingBranch > prepare {
		prepare = shippingBranch
	}

	// getUserCart, then the fan-out, then charging the card and emptying the cart.
	worstCase := retried(checkoutDependencyTimeout) + prepare +
		checkoutDependencyTimeout + checkoutDependencyTimeout

	const placeOrderDeadline = 10 * time.Second
	if worstCase >= placeOrderDeadline {
		t.Fatalf("dependency chain spans %s of the %s deadline, leaving nothing to persist the order",
			worstCase, placeOrderDeadline)
	}
	// The persist path retries too, and waitForDBRetry needs more than the last
	// gasp of the budget to be worth entering at all.
	if left := placeOrderDeadline - worstCase; left < dbRetryBaseDelay*4 {
		t.Fatalf("only %s left to persist the order after dependencies; raise a timeout back down", left)
	}
}
