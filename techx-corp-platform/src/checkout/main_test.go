package main

import (
	"context"
	"log/slog"
	"testing"
	"time"

	"github.com/IBM/sarama/mocks"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"github.com/open-telemetry/techx-corp/src/checkout/kafka"
	"go.opentelemetry.io/otel"
)

func init() {
	tracer = otel.Tracer("checkout")
	logger = slog.Default()
}

func TestSendToPostProcessor_RoutingKey(t *testing.T) {
	_ = kafka.Topic
	config := mocks.NewTestConfig()
	config.Producer.Return.Successes = true
	producer := mocks.NewAsyncProducer(t, config)

	testOrderID := "test-order-uuid-12345"
	producer.ExpectInputAndSucceed()

	cs := &checkout{
		KafkaProducerClient: producer,
	}

	orderResult := &pb.OrderResult{
		OrderId: testOrderID,
	}

	done := make(chan struct{})
	go func() {
		cs.sendToPostProcessor(context.Background(), orderResult)
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("sendToPostProcessor timed out")
	}

	if err := producer.Close(); err != nil {
		t.Fatalf("Failed to close producer mock: %v", err)
	}
}
