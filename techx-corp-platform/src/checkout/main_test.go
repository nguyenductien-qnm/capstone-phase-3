package main

import (
	"log/slog"

	"go.opentelemetry.io/otel"
)

func init() {
	tracer = otel.Tracer("checkout")
	logger = slog.Default()
}

