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

    let mut producer_config = ClientConfig::new();
    producer_config.set("bootstrap.servers", &kafka_addr);
    if !kafka_user.is_empty() && !kafka_password.is_empty() {
        producer_config
            .set("security.protocol", "sasl_ssl")
            .set("sasl.mechanisms", "SCRAM-SHA-512")
            .set("sasl.username", &kafka_user)
            .set("sasl.password", &kafka_password);
    }

    let producer: FutureProducer = match producer_config.create() {
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

    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("Failed to build Tokio runtime for Shipping Kafka consumer");

        rt.block_on(async move {
            loop {
                match consumer.recv().await {
                    Ok(m) => {
                        let payload = match m.payload_view::<str>() {
                            Some(Ok(s)) => s,
                            _ => "{}",
                        };

                        info!(
                            "Shipping consumer group '{}' processed message: topic={}, partition={}, offset={}, payload_len={}",
                            group_id,
                            m.topic(),
                            m.partition(),
                            m.offset(),
                            payload.len()
                        );

                        // 1. Parse JSON payload to extract user_id 
                        let parsed_json: serde_json::Value = serde_json::from_str(payload)
                            .unwrap_or_else(|_| serde_json::json!({}));
                        
                        let data_obj = parsed_json.get("after").or_else(|| parsed_json.get("before")).unwrap_or(&parsed_json);
                        let user_id_owned = data_obj
                            .get("user_id")
                            .or_else(|| data_obj.get("userId"))
                            .and_then(|v| v.as_str())
                            .map(|s| s.to_string())
                            .or_else(|| {
                                data_obj.get("order_metadata")
                                    .and_then(|v| v.as_str())
                                    .and_then(|meta_str| serde_json::from_str::<serde_json::Value>(meta_str).ok())
                                    .and_then(|meta_obj| meta_obj.get("user_id").and_then(|u| u.as_str()).map(|s| s.to_string()))
                            })
                            .unwrap_or_default();
                        let user_id = user_id_owned.as_str();                                                                                                              
                                                                                                                                                 
                        let order_id_owned = data_obj
                            .get("order_id")
                            .or_else(|| data_obj.get("orderId"))
                            .or_else(|| data_obj.get("aggregate_id"))
                            .and_then(|v| v.as_str())
                            .map(|s| s.to_string())
                            .unwrap_or_else(|| {
                                m.key()
                                    .map(|k| String::from_utf8_lossy(k).to_string())
                                    .unwrap_or_default()
                            });
                        let order_id = order_id_owned.as_str();

                        info!("Shipping consumed message for orderId: {}, userId: {}", order_id, user_id);

                        // 2. Build fulfillment payload containing userId
                        let record_payload = serde_json::json!({
                            "eventType": "SHIPPING_COMPLETED",
                            "source": "shipping",
                            "orderId": order_id,
                            "userId": user_id,
                        }).to_string();

                        // 3. Publish to domain.fulfillment.events
                        let record = FutureRecord::to(&fulfillment_topic)
                            .payload(&record_payload)
                            .key(&order_id);

                        match producer.send(record, Duration::from_secs(5)).await {
                            Ok(delivery) => info!("Shipping published fulfillment event successfully: {:?}", delivery),
                            Err((err, _)) => error!("Shipping failed to publish fulfillment event: {:?}", err),
                        }
                    }
                    Err(err) => {
                        error!("Kafka consumer error: {:?}", err);
                    }
                }
            }
        });
    });
}
