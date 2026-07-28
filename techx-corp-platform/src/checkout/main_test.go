package main

import (
	"log/slog"
	"testing"

	"go.opentelemetry.io/otel"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
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

