// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/IBM/sarama"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"github.com/open-telemetry/techx-corp/src/checkout/kafka"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	otelcodes "go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/metric"
	"google.golang.org/protobuf/proto"
)

var (
	ErrKafkaProducerUnavailable = errors.New("kafka producer unavailable")
	ErrKafkaPublishQueueFull    = errors.New("kafka publish queue full")
	ErrKafkaPublishTimeout      = errors.New("kafka publish timed out")
	ErrKafkaPublishFailed       = errors.New("kafka publish failed")
)

const defaultKafkaPublishTimeout = 250 * time.Millisecond

var (
	kafkaMetricsOnce        sync.Once
	kafkaPublishTotal       metric.Int64Counter
	kafkaPublishDuration    metric.Float64Histogram
	kafkaPublisherAvailable metric.Int64Gauge
)

type kafkaPublishOutcome string

const (
	kafkaPublishAccepted            kafkaPublishOutcome = "accepted"
	kafkaPublishProducerUnavailable kafkaPublishOutcome = "producer_unavailable"
	kafkaPublishQueueFull           kafkaPublishOutcome = "queue_full"
	kafkaPublishTimedOut            kafkaPublishOutcome = "publish_timeout"
	kafkaPublishError               kafkaPublishOutcome = "publish_error"
)

func initKafkaMetrics() {
	kafkaMetricsOnce.Do(func() {
		meter := otel.Meter("checkout.kafka")
		kafkaPublishTotal, _ = meter.Int64Counter("checkout_order_event_publish_total")
		kafkaPublishDuration, _ = meter.Float64Histogram("checkout_order_event_publish_duration_seconds")
		kafkaPublisherAvailable, _ = meter.Int64Gauge("checkout_order_event_publisher_available")
	})
}

func recordKafkaPublish(ctx context.Context, result kafkaPublishOutcome, duration time.Duration) {
	initKafkaMetrics()
	attrs := metric.WithAttributes(attribute.String("result", string(result)))
	kafkaPublishTotal.Add(ctx, 1, attrs)
	kafkaPublishDuration.Record(ctx, duration.Seconds(), attrs)
}

func recordKafkaPublisherAvailable(ctx context.Context, available bool) {
	initKafkaMetrics()
	value := int64(0)
	if available {
		value = 1
	}
	kafkaPublisherAvailable.Record(ctx, value)
}

func kafkaPublishTimeout() time.Duration {
	value, err := strconv.Atoi(os.Getenv("KAFKA_PUBLISH_TIMEOUT_MS"))
	if err != nil || value <= 0 {
		return defaultKafkaPublishTimeout
	}
	return time.Duration(value) * time.Millisecond
}

func kafkaPublishResult(err error) kafkaPublishOutcome {
	switch {
	case errors.Is(err, ErrKafkaProducerUnavailable):
		return kafkaPublishProducerUnavailable
	case errors.Is(err, ErrKafkaPublishQueueFull):
		return kafkaPublishQueueFull
	case errors.Is(err, ErrKafkaPublishTimeout):
		return kafkaPublishTimedOut
	default:
		return kafkaPublishError
	}
}

type OrderEventPublisher interface {
	Publish(context.Context, *pb.OrderResult) error
	PublishIncident(context.Context, *pb.OrderResult) error
	Close() error
}

type kafkaAsyncProducer interface {
	AsyncClose()
	Input() chan<- *sarama.ProducerMessage
	Successes() <-chan *sarama.ProducerMessage
	Errors() <-chan *sarama.ProducerError
}

type kafkaDelivery struct {
	orderID    string
	completion chan error
}

type kafkaPublishMode uint8

const (
	kafkaPublishModeNormal kafkaPublishMode = iota
	kafkaPublishModeIncident
)

type kafkaOrderEventPublisher struct {
	producer  kafkaAsyncProducer
	timeout   time.Duration
	done      chan struct{}
	closeOnce sync.Once
}

func newKafkaOrderEventPublisher(producer kafkaAsyncProducer, timeout time.Duration) *kafkaOrderEventPublisher {
	publisher := &kafkaOrderEventPublisher{
		producer: producer,
		timeout:  timeout,
		done:     make(chan struct{}),
	}
	if producer == nil {
		close(publisher.done)
		recordKafkaPublisherAvailable(context.Background(), false)
		return publisher
	}
	recordKafkaPublisherAvailable(context.Background(), true)
	go publisher.consumeResults()
	return publisher
}

func (p *kafkaOrderEventPublisher) consumeResults() {
	defer close(p.done)
	successes := p.producer.Successes()
	errorsChannel := p.producer.Errors()
	for successes != nil || errorsChannel != nil {
		select {
		case message, ok := <-successes:
			if !ok {
				successes = nil
				continue
			}
			resolveKafkaDelivery(message, nil)
		case producerError, ok := <-errorsChannel:
			if !ok {
				errorsChannel = nil
				continue
			}
			if producerError == nil {
				continue
			}
			orderID := ""
			if producerError.Msg != nil {
				if delivery, ok := producerError.Msg.Metadata.(*kafkaDelivery); ok && delivery != nil {
					orderID = delivery.orderID
				}
			}
			slog.Default().LogAttrs(
				context.Background(),
				slog.LevelWarn,
				"checkout order event delivery failed",
				slog.String("order_id", orderID),
				slog.String("error_class", "kafka_delivery_error"),
			)
			resolveKafkaDelivery(producerError.Msg, fmt.Errorf("%w: %v", ErrKafkaPublishFailed, producerError.Err))
		}
	}
}

func resolveKafkaDelivery(message *sarama.ProducerMessage, err error) {
	if message == nil {
		return
	}
	delivery, ok := message.Metadata.(*kafkaDelivery)
	if !ok || delivery == nil {
		return
	}
	select {
	case delivery.completion <- err:
	default:
	}
}

func (p *kafkaOrderEventPublisher) Publish(ctx context.Context, event *pb.OrderResult) error {
	started := time.Now()
	err := p.publish(ctx, event, kafkaPublishModeNormal)
	outcome := kafkaPublishResultOrAccepted(err)
	recordKafkaPublish(ctx, outcome, time.Since(started))
	level := slog.LevelInfo
	if err != nil {
		level = slog.LevelWarn
	}
	attrs := []slog.Attr{
		slog.String("order_id", event.GetOrderId()),
		slog.String("publish_result", string(outcome)),
		slog.Int64("duration_ms", time.Since(started).Milliseconds()),
	}
	if err != nil {
		attrs = append(attrs, slog.String("error_class", string(kafkaPublishResult(err))))
	}
	slog.Default().LogAttrs(
		ctx,
		level,
		"checkout order event publish",
		attrs...,
	)
	return err
}

func (p *kafkaOrderEventPublisher) PublishIncident(ctx context.Context, event *pb.OrderResult) error {
	return p.publish(ctx, event, kafkaPublishModeIncident)
}

func (p *kafkaOrderEventPublisher) publish(ctx context.Context, event *pb.OrderResult, mode kafkaPublishMode) (err error) {
	if p == nil || p.producer == nil {
		return ErrKafkaProducerUnavailable
	}

	payload, err := proto.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal order event: %w", err)
	}
	delivery := &kafkaDelivery{orderID: event.GetOrderId(), completion: make(chan error, 1)}
	message := &sarama.ProducerMessage{
		Topic:    kafka.Topic,
		Value:    sarama.ByteEncoder(payload),
		Metadata: delivery,
	}
	started := time.Now()
	span := createProducerSpan(ctx, message)
	defer func() {
		span.SetAttributes(
			attribute.Bool("messaging.kafka.producer.accepted", err == nil),
			attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(started).Milliseconds())),
		)
		if err != nil {
			span.SetStatus(otelcodes.Error, err.Error())
		}
		span.End()
	}()

	defer func() {
		if recovered := recover(); recovered != nil {
			err = fmt.Errorf("%w: %v", ErrKafkaProducerUnavailable, recovered)
		}
	}()

	if mode == kafkaPublishModeIncident {
		p.producer.Input() <- message
		return <-delivery.completion
	}

	publishCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()
	select {
	case p.producer.Input() <- message:
	case <-publishCtx.Done():
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if errors.Is(publishCtx.Err(), context.DeadlineExceeded) {
			return ErrKafkaPublishQueueFull
		}
		return publishCtx.Err()
	}

	select {
	case err := <-delivery.completion:
		return err
	case <-publishCtx.Done():
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if errors.Is(publishCtx.Err(), context.DeadlineExceeded) {
			return ErrKafkaPublishTimeout
		}
		return publishCtx.Err()
	}
}

func kafkaPublishResultOrAccepted(err error) kafkaPublishOutcome {
	if err == nil {
		return kafkaPublishAccepted
	}
	return kafkaPublishResult(err)
}

func (p *kafkaOrderEventPublisher) Close() error {
	if p == nil || p.producer == nil {
		return nil
	}
	p.closeOnce.Do(p.producer.AsyncClose)
	select {
	case <-p.done:
		recordKafkaPublisherAvailable(context.Background(), false)
		return nil
	case <-time.After(p.timeout):
		return ErrKafkaPublishTimeout
	}
}
