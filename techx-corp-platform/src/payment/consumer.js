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

    // consumer.js calls charge.js when a Kafka message arrives
    await consumerInstance.run({
      eachMessage: async ({ topic, partition, message }) => {
        // 1. Convert Kafka message buffer to string & parse JSON
        const payloadStr = message.value ? message.value.toString() : '';
        let payload = {};
        try {
          payload = JSON.parse(payloadStr);
        } catch (error) {
          logger.warn({ err: error }, "Failed to parse JSON message payload");
        }

        const dataObj = payload.after || payload.before || payload;
        const rawKey = message.key ? message.key.toString() : '';
        const orderId = dataObj.order_id || dataObj.orderId || dataObj.aggregate_id || (rawKey.includes('Struct') ? '' : rawKey);
        
        let userId = dataObj.user_id || dataObj.userId || payload.user_id || '';
        if (!userId && dataObj.order_metadata) {
          try {
            const meta = typeof dataObj.order_metadata === 'string' ? JSON.parse(dataObj.order_metadata) : dataObj.order_metadata;
            userId = meta.user_id || meta.userId || '';
          } catch (e) {}
        }
        logger.info({ orderId, userId, payloadKeys: Object.keys(payload) }, "Extracted orderId and userId in Payment consumer");
        
        // 3. 
        // When consuming from domain.checkout.orders
        // Publish fulfillment event to domain.fulfillment.events
        try { 
          const eventPayload = {
            eventType: 'PAYMENT_COMPLETED',
            source: 'payment',
            orderId: orderId,
            userId: userId,
            timestamp: new Date().toISOString(),
          };

          // Publish to domain.fulfillment.events topic
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
