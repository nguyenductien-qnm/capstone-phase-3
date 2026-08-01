// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package kafka

import (
	"fmt"
	"log/slog"
	"os"
	"time"

	"github.com/IBM/sarama"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"                                                                                                                                  
    "google.golang.org/protobuf/proto"
)

var (
	Topic           = "domain.checkout.orders"
	ProtocolVersion = sarama.V3_0_0_0
)

type saramaLogger struct {
	logger *slog.Logger
}

func (l *saramaLogger) Printf(format string, v ...interface{}) {
	l.logger.Info(fmt.Sprintf(format, v...))
}
func (l *saramaLogger) Println(v ...interface{}) {
	l.logger.Info(fmt.Sprint(v...))
}
func (l *saramaLogger) Print(v ...interface{}) {
	l.logger.Info(fmt.Sprint(v...))
}

// Initialize Sarama AsyncProducer with ZSTD compression & MSK authentication
func CreateKafkaProducer(brokers []string, logger *slog.Logger) (sarama.AsyncProducer, error) {
	// Set the logger for sarama to use
	sarama.Logger = &saramaLogger{logger: logger}

	saramaConfig := sarama.NewConfig()
	saramaConfig.Version = ProtocolVersion
	// To know the partition and offset of messages
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Producer.Return.Errors = true

	// Enable ZSTD Compression for MSK Wire Transport
	saramaConfig.Producer.Compression = sarama.CompressionZSTD

	// Wait for leader ACK
	saramaConfig.Producer.RequiredAcks = sarama.WaitForLocal

	// Enable TLS & SASL/SCRAM authentication when credentials exist (MSK)
	saramaConfig.Net.TLS.Enable = true
	saramaConfig.Net.SASL.Enable = true	
	saramaConfig.Net.SASL.User = os.Getenv("KAFKA_USER")
	saramaConfig.Net.SASL.Password = os.Getenv("KAFKA_PASSWORD")
	saramaConfig.Net.SASL.Mechanism = sarama.SASLTypeSCRAMSHA512
	saramaConfig.Net.SASL.SCRAMClientGeneratorFunc = func() sarama.SCRAMClient { return &XDGSCRAMClient{HashGeneratorFcn: SHA512} }
	
	producer, err := sarama.NewAsyncProducer(brokers, saramaConfig)
	if err != nil {
		return nil, err
	}
	
	// Drain Successes and Errors in background goroutine to avoid channel blockage
	go func ()  {
		for {
			select {
			case succ, ok := <-producer.Successes():
				if !ok {
					return
				}
			
				logger.Info(fmt.Sprintf("Kafka producer published ZSTD Protobuf event to %s [partition %d, offset %d]", succ.Topic, succ.Partition, succ.Offset))

			case err, ok := <-producer.Errors():
				if !ok {
					return
				}
				logger.Error(fmt.Sprintf("Kafka producer error: %v", err))
			}
		}
	}()
	return producer, nil
}

// Serializes order event to Protobuf binary and pushes it to Kafka
func PublishOrderEvent(
		producer sarama.AsyncProducer, 
		topic string, 
		userID string,
		orderID string,
		orderResult *pb.OrderResult,
		paymentSummary *pb.PaymentSummary,
	) error {
	if producer == nil || orderResult == nil {
		return fmt.Errorf("producer or orderResult is nil")
	}

	// Build order event Protobuf Struct (including full order_payload in OrderResult)
	orderEvent := &pb.OrderEvent{
		OrderId: orderResult.GetOrderId(),
		UserId: userID,
		OrderResult: orderResult,
		PaymentSummary: paymentSummary,
		Timestamp: time.Now().Format(time.RFC3339),
	}

	// Serializes to binary Protobuf
	payloadBytes, err := proto.Marshal(orderEvent)
	if err != nil {
		return fmt.Errorf("failed to marshal OrderEvent to Protobuf: %w", err)
	}

	msg := &sarama.ProducerMessage{
		Topic: topic,
		Key: sarama.StringEncoder(orderResult.GetOrderId()),
		Value: sarama.ByteEncoder(payloadBytes),
	}

	producer.Input() <- msg
	return nil
}