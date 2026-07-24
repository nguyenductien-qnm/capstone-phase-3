// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { Kafka } = require('kafkajs');
const logger = require('./logger');

let consumerInstance = null;
let producerInstance = null;

async function startConsumer() {
  const kafkaAddr = process.env.KAFKA_ADDR;
  if (!kafkaAddr) {
    logger.info("KAFKA_ADDR is not set, skipping Payment Kafka consumer/producer initialization.");
    return null;
  }

  const topic = process.env.KAFKA_TOPIC || 'domain.checkout.orders';
  const fulfillmentTopic = process.env.KAFKA_FULFILLMENT_TOPIC || 'domain.fulfillment.events';
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
    await consumerInstance.connect();
    await producerInstance.connect();
    logger.info({ brokers, topic, fulfillmentTopic, groupId }, `Payment Kafka client connected to brokers.`);

    await consumerInstance.subscribe({ topic, fromBeginning: true });
    logger.info({ topic, groupId }, `Payment Kafka consumer subscribed to topic '${topic}' under consumer group '${groupId}'.`);

    await consumerInstance.run({
      eachMessage: async ({ topic, partition, message }) => {
        const payloadStr = message.value ? message.value.toString() : '';
        logger.info({
          topic,
          partition,
          offset: message.offset,
          key: message.key ? message.key.toString() : null,
          payloadLength: payloadStr.length,
          groupId,
        }, `Payment consumer group '${groupId}' consumed message from topic '${topic}'.`);

        // Publish fulfillment event to domain.fulfillment.events
        try {
          const orderId = message.key ? message.key.toString() : null;
          const eventPayload = {
            eventType: 'PAYMENT_COMPLETED',
            source: 'payment',
            timestamp: new Date().toISOString(),
            orderId: orderId,
            details: payloadStr,
          };
          await publishFulfillmentEvent(eventPayload, fulfillmentTopic);
        } catch (pubErr) {
          logger.error({ err: pubErr }, `Failed to publish fulfillment event to topic '${fulfillmentTopic}'`);
        }
      },
    });

    return consumerInstance;
  } catch (err) {
    logger.error({ err, topic, groupId }, `Failed to start Payment Kafka consumer for group '${groupId}' on topic '${topic}'.`);
    return null;
  }
}

async function publishFulfillmentEvent(eventPayload, fulfillmentTopic = process.env.KAFKA_FULFILLMENT_TOPIC || 'domain.fulfillment.events') {
  if (!producerInstance) return;
  await producerInstance.send({
    topic: fulfillmentTopic,
    messages: [
      {
        key: eventPayload.orderId || String(Date.now()),
        value: JSON.stringify(eventPayload),
      },
    ],
  });
  logger.info({ topic: fulfillmentTopic, orderId: eventPayload.orderId }, `Payment service published fulfillment event to topic '${fulfillmentTopic}'.`);
}

async function stopConsumer() {
  if (consumerInstance) {
    try {
      await consumerInstance.disconnect();
      logger.info("Payment Kafka consumer disconnected cleanly.");
    } catch (err) {
      logger.error({ err }, "Error disconnecting Payment Kafka consumer.");
    }
  }
  if (producerInstance) {
    try {
      await producerInstance.disconnect();
      logger.info("Payment Kafka producer disconnected cleanly.");
    } catch (err) {
      logger.error({ err }, "Error disconnecting Payment Kafka producer.");
    }
  }
}

module.exports = { startConsumer, stopConsumer, publishFulfillmentEvent };
