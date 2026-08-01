// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const path = require('path');
const { Kafka, CompressionCodecs, CompressionTypes } = require('kafkajs');
const KAFKAJS_ZSTD = require('kafkajs-zstd');
const protobuf = require('protobufjs');
const logger = require('./logger');
const { chargeWithToken } = require('./charge');

// Register ZSTD Decompression Codec in KafkaJS 
CompressionCodecs[CompressionTypes.ZSTD] = KAFKAJS_ZSTD();

// Load Protobuf Schema from pb/demo.proto
const protoPath = path.resolve(__dirname, '../../pb/demo.proto');
const root = protobuf.loadSync(protoPath);
const OrderEvent = root.lookupType("oteldemo.OrderEvent");
const PaymentEvent = root.lookupType("oteldemo.PaymentEvent");

let consumerInstance = null;
let producerInstance = null;

async function startConsumer() {
  const kafkaAddr = process.env.KAFKA_ADDR;
  if (!kafkaAddr) {
    logger.info("KAFKA_ADDR is not set, skipping Payment Kafka consumer/producer initialization.");
    return null;
  }

  const topic = process.env.KAFKA_TOPIC || 'domain.checkout.orders';
  const paymentTopic = process.env.KAFKA_PAYMENT_TOPIC || 'domain.checkout.payment';
  const groupId = process.env.KAFKA_GROUP_ID || 'payment';
  const kafkaUser = process.env.KAFKA_USER;
  const kafkaPassword = process.env.KAFKA_PASSWORD;

  const brokers = kafkaAddr.split(',').map(b => b.trim()).filter(Boolean);

  const kafkaConfig = {
    clientId: 'payment-service',
    brokers: brokers,
  };

  if (kafkaUser && kafkaPassword) {
    kafkaConfig.ssl = true;
    kafkaConfig.sasl = {
      mechanism: 'scram-sha-512',
      username: kafkaUser,
      password: kafkaPassword,
    };
  }

  const kafka = new Kafka(kafkaConfig);
  consumerInstance = kafka.consumer({ groupId });
  producerInstance = kafka.producer();

  try {
    // Connect both Consumer and Producer
    await consumerInstance.connect();
    await producerInstance.connect();
    logger.info({ brokers, topic, paymentTopic, groupId }, `Payment Kafka client connected to brokers.`);

    await consumerInstance.subscribe({ topic, fromBeginning: true });
    logger.info({ topic, groupId }, `Payment Kafka consumer subscribed to topic '${topic}' under consumer group '${groupId}'.`);

    // consumer.js calls charge.js when a Kafka message arrives
    await consumerInstance.run({
      eachMessage: async ({ topic, partition, message }) => {
        let orderEvent;

        // 1. Decode Protobuf OrderEvent
        try {
          orderEvent = OrderEvent.decode(message.value);
        } catch (err) {
          logger.error({ err }, "Failed to decode Protobuf OrderEvent message");
          return;
        }

        const { orderId, userId, orderResult, paymentSummary } = orderEvent;
        logger.info({ orderId, userId }, "Payment consumer successfully decoded Protobuf OrderEvent");

        // 2. Charge Payment Token via charge.js
        if (paymentSummary && paymentSummary.paymentToken) {
          try {
            await chargeWithToken({
              paymentToken: paymentSummary.paymentToken,
              amount: paymentSummary.amount,
              orderId: orderId,
            })
          } catch (error) {
            logger.error({ err: error, orderId }, "Failed to process token charge");
          }
        }
        
        // 3. Construct and publish PaymentEvent to domain.checkout.payment
        try {
          const paymentCompletedEvent = PaymentEvent.create({
            eventType: 'PAYMENT_COMPLETED',
            source: 'payment',
            orderId: orderId,
            userId: userId,
            orderResult: orderResult,
            timestamp: new Date().toISOString,
          })

          await publishPaymentEvent(
            PaymentEvent.encode(paymentCompletedEvent).finish(),
            orderId,
            paymentTopic
          );
        } catch (error) {
          logger.error(
						{ err: error, orderId },
						`Failed to publish PaymentEvent to topic '${paymentTopic}'`,
					);
        }        
      },
    });

    return consumerInstance;
  } catch (err) {
    logger.error({ err, topic, groupId }, `Failed to start Payment Kafka consumer for group '${groupId}' on topic '${topic}'.`);
    return null;
  }
}

// Helper function to publish result to domain.checkout.payment
async function publishPaymentEvent(encodedEvent, orderId, topic = process.env.KAFKA_PAYMENT_TOPIC || 'domain.checkout.payment') {
  if (!producerInstance) {
    logger.warn({ orderId, topic }, "Producer instance not connected, skipping publish.");
    return;
  }

  await producerInstance.send({
    topic: topic,
    messages: [
      {
        key: orderId,
        value: encodedEvent,
      },
    ],
  });
  logger.info({ topic: topic, orderId: orderId }, `Payment service published fulfillment event to topic '${topic}'.`);
}

async function stopConsumer() {
  if (consumerInstance) {
    try {
      await consumerInstance.disconnect();
      logger.info("Payment Kafka consumer disconnected cleanly");
    } catch (err) {
      logger.error({ err }, "Error disconnecting Payment Kafka consumer");
    }
  }

  if (producerInstance) {
    try {
      await producerInstance.disconnect();
      logger.info("Payment Kafka producer disconnected cleanly");
    } catch (error) {
      logger.error({ err }, "Error disconnecting PaymentKafka producer")
    }
  }
}

module.exports = { startConsumer, stopConsumer };
