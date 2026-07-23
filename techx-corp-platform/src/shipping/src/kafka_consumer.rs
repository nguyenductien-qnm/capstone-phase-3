// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use rdkafka::config::ClientConfig;
use rdkafka::consumer::{Consumer, StreamConsumer};
use rdkafka::message::Message;
use tracing::{error, info};

pub fn start_kafka_consumer() {
    let kafka_addr = match std::env::var("KAFKA_ADDR") {
        Ok(val) if !val.is_empty() => val,
        _ => {
            info!("KAFKA_ADDR is not set, skipping Shipping Kafka consumer initialization.");
            return;
        }
    };

    let topic = std::env::var("KAFKA_TOPIC").unwrap_or_else(|_| "domain.checkout.orders".to_string());
    let group_id = std::env::var("KAFKA_GROUP_ID").unwrap_or_else(|_| "shipping".to_string());
    let kafka_user = std::env::var("KAFKA_USER").unwrap_or_default();
    let kafka_password = std::env::var("KAFKA_PASSWORD").unwrap_or_default();

    let mut config = ClientConfig::new();
    config
        .set("bootstrap.servers", &kafka_addr)
        .set("group.id", &group_id)
        .set("enable.auto.commit", "true")
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

    if let Err(err) = consumer.subscribe(&[&topic]) {
        error!("Failed to subscribe to topic '{}': {:?}", topic, err);
        return;
    }

    info!(
        "Shipping Kafka consumer started. Subscribed to topic '{}' with group ID '{}'",
        topic, group_id
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
                }
                Err(err) => {
                    error!("Kafka consumer error: {:?}", err);
                }
            }
        }
    });
}
