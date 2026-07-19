// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sync"
	"testing"
	"time"

	"github.com/IBM/sarama"
	"github.com/open-feature/go-sdk/openfeature"
	"github.com/open-feature/go-sdk/openfeature/memprovider"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"google.golang.org/protobuf/proto"
)

type fakeKafkaProducer struct {
	input     chan *sarama.ProducerMessage
	successes chan *sarama.ProducerMessage
	errors    chan *sarama.ProducerError
	closeOnce sync.Once
}

func (p *fakeKafkaProducer) Input() chan<- *sarama.ProducerMessage     { return p.input }
func (p *fakeKafkaProducer) Successes() <-chan *sarama.ProducerMessage { return p.successes }
func (p *fakeKafkaProducer) Errors() <-chan *sarama.ProducerError      { return p.errors }
func (p *fakeKafkaProducer) AsyncClose() {
	p.closeOnce.Do(func() {
		close(p.successes)
		close(p.errors)
	})
}

func newFakeKafkaProducer() *fakeKafkaProducer {
	return &fakeKafkaProducer{
		input:     make(chan *sarama.ProducerMessage, 8),
		successes: make(chan *sarama.ProducerMessage, 8),
		errors:    make(chan *sarama.ProducerError, 8),
	}
}

func TestOrderEventPublisherReturnsCorrelatedSuccess(t *testing.T) {
	producer := newFakeKafkaProducer()
	publisher := newKafkaOrderEventPublisher(producer, time.Second)
	defer publisher.Close()

	go func() {
		message := <-producer.input
		producer.successes <- message
	}()

	err := publisher.Publish(context.Background(), &pb.OrderResult{OrderId: "order-success"})
	if err != nil {
		t.Fatalf("Publish() error = %v, want nil", err)
	}
}

func TestKafkaPublishTimeoutConfiguration(t *testing.T) {
	tests := []struct {
		name  string
		value string
		want  time.Duration
	}{
		{name: "default when unset", want: defaultKafkaPublishTimeout},
		{name: "configured milliseconds", value: "75", want: 75 * time.Millisecond},
		{name: "default when invalid", value: "invalid", want: defaultKafkaPublishTimeout},
		{name: "default when non-positive", value: "0", want: defaultKafkaPublishTimeout},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Setenv("KAFKA_PUBLISH_TIMEOUT_MS", test.value)
			if got := kafkaPublishTimeout(); got != test.want {
				t.Fatalf("kafkaPublishTimeout() = %v, want %v", got, test.want)
			}
		})
	}
}

func TestOrderEventPublisherContinuouslyDrainsBurstResults(t *testing.T) {
	const messageCount = 100
	producer := newFakeKafkaProducer()
	publisher := newKafkaOrderEventPublisher(producer, time.Second)
	defer publisher.Close()

	go func() {
		for range messageCount {
			producer.successes <- <-producer.input
		}
	}()

	results := make(chan error, messageCount)
	for i := range messageCount {
		go func() {
			results <- publisher.Publish(context.Background(), &pb.OrderResult{OrderId: fmt.Sprintf("burst-%d", i)})
		}()
	}

	for range messageCount {
		if err := <-results; err != nil {
			t.Fatalf("burst Publish() error = %v, want nil", err)
		}
	}
}

func TestOrderEventPublisherCorrelatesConcurrentResults(t *testing.T) {
	producer := newFakeKafkaProducer()
	publisher := newKafkaOrderEventPublisher(producer, time.Second)
	defer publisher.Close()

	go func() {
		for range 2 {
			message := <-producer.input
			payload, _ := message.Value.Encode()
			order := new(pb.OrderResult)
			_ = proto.Unmarshal(payload, order)
			if order.OrderId == "order-failure" {
				producer.errors <- &sarama.ProducerError{Msg: message, Err: errors.New("broker unavailable")}
				continue
			}
			producer.successes <- message
		}
	}()

	type result struct {
		orderID string
		err     error
	}
	results := make(chan result, 2)
	for _, orderID := range []string{"order-success", "order-failure"} {
		go func() {
			results <- result{orderID: orderID, err: publisher.Publish(context.Background(), &pb.OrderResult{OrderId: orderID})}
		}()
	}

	for range 2 {
		got := <-results
		switch got.orderID {
		case "order-success":
			if got.err != nil {
				t.Fatalf("successful order error = %v, want nil", got.err)
			}
		case "order-failure":
			if !errors.Is(got.err, ErrKafkaPublishFailed) {
				t.Fatalf("failed order error = %v, want %v", got.err, ErrKafkaPublishFailed)
			}
		default:
			t.Fatal(fmt.Sprintf("unexpected order result %q", got.orderID))
		}
	}
}

func TestOrderEventPublisherDistinguishesQueueFullFromDeliveryTimeout(t *testing.T) {
	t.Run("queue full before admission", func(t *testing.T) {
		producer := newFakeKafkaProducer()
		producer.input = make(chan *sarama.ProducerMessage)
		publisher := newKafkaOrderEventPublisher(producer, 10*time.Millisecond)
		defer publisher.Close()

		err := publisher.Publish(context.Background(), &pb.OrderResult{OrderId: "queue-full"})
		if !errors.Is(err, ErrKafkaPublishQueueFull) {
			t.Fatalf("Publish() error = %v, want %v", err, ErrKafkaPublishQueueFull)
		}
	})

	t.Run("request deadline during admission is not queue full", func(t *testing.T) {
		producer := newFakeKafkaProducer()
		producer.input = make(chan *sarama.ProducerMessage)
		publisher := newKafkaOrderEventPublisher(producer, time.Second)
		defer publisher.Close()

		ctx, cancel := context.WithTimeout(context.Background(), time.Millisecond)
		defer cancel()
		err := publisher.Publish(ctx, &pb.OrderResult{OrderId: "request-deadline"})
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("Publish() error = %v, want %v", err, context.DeadlineExceeded)
		}
		if errors.Is(err, ErrKafkaPublishQueueFull) {
			t.Fatalf("Publish() error = %v, must not be classified as queue full", err)
		}
	})

	t.Run("delivery result timeout after admission", func(t *testing.T) {
		producer := newFakeKafkaProducer()
		publisher := newKafkaOrderEventPublisher(producer, 10*time.Millisecond)
		defer publisher.Close()

		err := publisher.Publish(context.Background(), &pb.OrderResult{OrderId: "delivery-timeout"})
		if !errors.Is(err, ErrKafkaPublishTimeout) {
			t.Fatalf("Publish() error = %v, want %v", err, ErrKafkaPublishTimeout)
		}
	})
}

func TestOrderEventPublisherIncidentPublishPreservesUnboundedWait(t *testing.T) {
	producer := newFakeKafkaProducer()
	publisher := newKafkaOrderEventPublisher(producer, time.Millisecond)
	defer publisher.Close()

	go func() {
		message := <-producer.input
		time.Sleep(20 * time.Millisecond)
		producer.successes <- message
	}()

	if err := publisher.PublishIncident(context.Background(), &pb.OrderResult{OrderId: "btc-incident"}); err != nil {
		t.Fatalf("PublishIncident() error = %v, want nil", err)
	}
}

func TestNormalAndIncidentPublishesDoNotConsumeEachOthersResults(t *testing.T) {
	producer := newFakeKafkaProducer()
	publisher := newKafkaOrderEventPublisher(producer, time.Second)
	defer publisher.Close()

	go func() {
		messages := make([]*sarama.ProducerMessage, 0, 3)
		for range 3 {
			messages = append(messages, <-producer.input)
		}
		for i := len(messages) - 1; i >= 0; i-- {
			producer.successes <- messages[i]
		}
	}()

	errorsByOrder := make(chan error, 3)
	go func() {
		errorsByOrder <- publisher.Publish(context.Background(), &pb.OrderResult{OrderId: "normal"})
	}()
	for _, orderID := range []string{"incident-1", "incident-2"} {
		go func() {
			errorsByOrder <- publisher.PublishIncident(context.Background(), &pb.OrderResult{OrderId: orderID})
		}()
	}

	for range 3 {
		if err := <-errorsByOrder; err != nil {
			t.Fatalf("mixed normal/incident publish error = %v, want nil", err)
		}
	}
}

type fakeOrderEventPublisher struct {
	incidentCalls chan struct{}
	publishErr    error
}

func (p *fakeOrderEventPublisher) Publish(context.Context, *pb.OrderResult) error {
	return p.publishErr
}
func (p *fakeOrderEventPublisher) PublishIncident(context.Context, *pb.OrderResult) error {
	p.incidentCalls <- struct{}{}
	return nil
}
func (p *fakeOrderEventPublisher) Close() error { return nil }

func TestKafkaQueueProblemsKeepsExactAsynchronousFanOut(t *testing.T) {
	previousLogger := logger
	logger = slog.Default()
	t.Cleanup(func() { logger = previousLogger })

	publisher := &fakeOrderEventPublisher{incidentCalls: make(chan struct{}, 4)}
	service := &checkout{orderEventPublisher: publisher}

	service.publishKafkaQueueProblems(context.Background(), &pb.OrderResult{OrderId: "btc-incident"}, 3)

	for i := 0; i < 3; i++ {
		select {
		case <-publisher.incidentCalls:
		case <-time.After(time.Second):
			t.Fatalf("incident publish calls = %d, want 3", i)
		}
	}
	select {
	case <-publisher.incidentCalls:
		t.Fatal("incident publisher received more than ffValue calls")
	case <-time.After(20 * time.Millisecond):
	}
}

func TestSendToPostProcessorReadsKafkaQueueProblemsFromOpenFeature(t *testing.T) {
	previousLogger := logger
	logger = slog.Default()
	t.Cleanup(func() { logger = previousLogger })

	provider := memprovider.NewInMemoryProvider(map[string]memprovider.InMemoryFlag{
		"kafkaQueueProblems": {
			Key:            "kafkaQueueProblems",
			State:          memprovider.Enabled,
			DefaultVariant: "three",
			Variants:       map[string]any{"three": 3},
		},
	})
	if err := openfeature.SetProviderAndWait(provider); err != nil {
		t.Fatalf("SetProviderAndWait() error = %v", err)
	}
	t.Cleanup(func() {
		_ = openfeature.SetProviderAndWait(openfeature.NoopProvider{})
	})

	publisher := &fakeOrderEventPublisher{
		incidentCalls: make(chan struct{}, 4),
		publishErr:    ErrKafkaProducerUnavailable,
	}
	service := &checkout{orderEventPublisher: publisher}

	err := service.sendToPostProcessor(context.Background(), &pb.OrderResult{OrderId: "btc-openfeature"})
	if !errors.Is(err, ErrKafkaProducerUnavailable) {
		t.Fatalf("sendToPostProcessor() error = %v, want %v", err, ErrKafkaProducerUnavailable)
	}
	for i := 0; i < 3; i++ {
		select {
		case <-publisher.incidentCalls:
		case <-time.After(time.Second):
			t.Fatalf("OpenFeature incident publish calls = %d, want 3", i)
		}
	}
	select {
	case <-publisher.incidentCalls:
		t.Fatal("OpenFeature incident publisher received more than ffValue calls")
	case <-time.After(20 * time.Millisecond):
	}
}

func TestOrderEventPublisherReturnsUnavailableForNilProducer(t *testing.T) {
	publisher := newKafkaOrderEventPublisher(nil, 10*time.Millisecond)
	err := publisher.Publish(context.Background(), &pb.OrderResult{OrderId: "unavailable"})
	if !errors.Is(err, ErrKafkaProducerUnavailable) {
		t.Fatalf("Publish() error = %v, want %v", err, ErrKafkaProducerUnavailable)
	}
}

func TestOrderEventPublisherConvertsClosedInputToUnavailable(t *testing.T) {
	producer := newFakeKafkaProducer()
	close(producer.input)
	publisher := newKafkaOrderEventPublisher(producer, time.Second)
	defer publisher.Close()

	err := publisher.Publish(context.Background(), &pb.OrderResult{OrderId: "closed"})
	if !errors.Is(err, ErrKafkaProducerUnavailable) {
		t.Fatalf("Publish() error = %v, want %v", err, ErrKafkaProducerUnavailable)
	}
}
