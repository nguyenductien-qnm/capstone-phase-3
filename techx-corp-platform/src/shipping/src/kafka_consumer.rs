// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use rdkafka::config::ClientConfig;
use rdkafka::consumer::{Consumer, StreamConsumer};
use rdkafka::message::Message;
use rdkafka::producer::{FutureProducer, FutureRecord};
use std::time::Duration;
use tracing::{error, info};

pub fn start_kafka_consumer() {
    let kafka_addr = match std::env::var("KAFKA_ADDR") {
        Ok(val) if !val.is_empty() => val,
        _ => {
            info!("KAFKA_ADDR is not set, skipping Shipping Kafka consumer/producer initialization.");
            return;
        }
    };

    let topic = std::env::var("KAFKA_TOPIC").unwrap_or_else(|_| "domain.checkout.orders".to_string());
    let fulfillment_topic = std::env::var("KAFKA_FULFILLMENT_TOPIC").unwrap_or_else(|_| "domain.fulfillment.events".to_string());
    let group_id = std::env::var("KAFKA_GROUP_ID").unwrap_or_else(|_| "shipping".to_string());
    let kafka_user = std::env::var("KAFKA_USER").unwrap_or_default();
    let kafka_password = std::env::var("KAFKA_PASSWORD").unwrap_or_default();

    let mut config = ClientConfig::new();
    config
        .set("bootstrap.servers", &kafka_addr)
        .set("group.id", &group_id)
        .set("enable.auto.commit", "false")
        .set("auto.offset.reset", "earliest");

    if !kafka_user.is_empty() && !kafka_password.is_empty() {
        config
            .set("security.protocol", "sasl_ssl")
            .set("sasl.mechanisms", "SCRAM-SHA-512")
            .set("sasl.username", &kafka_user)
            .set("sasl.password", &kafka_password);
    }

    let consumer: StreamConsumer = match config.create() {
        Ok(c) => c,
        Err(err) => {
            error!("Failed to create Shipping Kafka consumer: {:?}", err);
            return;
        }
    };

    let producer: FutureProducer = match config.create() {
        Ok(p) => p,
        Err(err) => {
            error!("Failed to create Shipping Kafka producer: {:?}", err);
            return;
        }
    };

    if let Err(err) = consumer.subscribe(&[&topic]) {
        error!("Failed to subscribe to topic '{}': {:?}", topic, err);
        return;
    }

    info!(
        "Shipping Kafka consumer started. Subscribed to topic '{}' with group ID '{}', publishing to '{}'",
        topic, group_id, fulfillment_topic
    );

    tokio::spawn(async move {
        loop {
            match consumer.recv().await {
                Ok(m) => {
                    let payload = match m.payload_view::<str>() {
                        Some(Ok(s)) => s,
                        Some(Err(_)) => "<invalid utf-8>",
                        None => "",
                    };
                    info!(
                        "Shipping consumer group '{}' processed message: topic={}, partition={}, offset={}, payload_len={}",
                        group_id,
                        m.topic(),
                        m.partition(),
                        m.offset(),
                        payload.len()
                    );

                    // Publish fulfillment event to domain.fulfillment.events
                    let key = m.key().map(|k| String::from_utf8_lossy(k).to_string()).unwrap_or_default();
                    let record_payload = serde_json::json!({
                        "eventType": "SHIPPING_COMPLETED",
                        "source": "shipping",
                        "key": key,
                        "details": payload
                    }).to_string();
                    let record = FutureRecord::to(&fulfillment_topic)
                        .payload(&record_payload)
                        .key(&key);
                    match producer.send(record, Duration::from_secs(5)).await {
                        Ok((partition, offset)) => {
                            info!("Shipping service published fulfillment event to topic '{}' (partition {}, offset {})", fulfillment_topic, partition, offset);
                        }
                        Err((err, _)) => {
                            error!("Failed to publish fulfillment event to topic '{}': {:?}", fulfillment_topic, err);
                        }
                    }
                }
                Err(err) => {
                    error!("Kafka consumer error: {:?}", err);
                }
            }
        }
    });
}
