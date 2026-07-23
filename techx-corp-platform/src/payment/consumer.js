// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { Kafka } = require('kafkajs');
const logger = require('./logger');

let consumerInstance = null;

async function startConsumer() {
  const kafkaAddr = process.env.KAFKA_ADDR;
  if (!kafkaAddr) {
    logger.info("KAFKA_ADDR is not set, skipping Payment Kafka consumer initialization.");
    return null;
  }

  const topic = process.env.KAFKA_TOPIC || 'domain.checkout.orders';
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

  try {
    await consumerInstance.connect();
    logger.info({ brokers, topic, groupId }, `Payment Kafka consumer connected to brokers.`);

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
      },
    });

    return consumerInstance;
  } catch (err) {
    logger.error({ err, topic, groupId }, `Failed to start Payment Kafka consumer for group '${groupId}' on topic '${topic}'.`);
    return null;
  }
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
}

module.exports = { startConsumer, stopConsumer };
