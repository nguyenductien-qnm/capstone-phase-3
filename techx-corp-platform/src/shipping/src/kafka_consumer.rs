// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use rdkafka::config::ClientConfig;
use rdkafka::consumer::{Consumer, StreamConsumer};
use rdkafka::message::Message;
use rdkafka::producer::{FutureProducer, FutureRecord};
use std::time::Duration;
use tracing::{error, info};
use prost::Message as ProstMessage;

use crate::shipping_service::quote::create_quote_from_count;

// -----------------------------------------------------------------------------
// Protobuf Schemas (matching pb/demo.proto)
// -----------------------------------------------------------------------------

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct PaymentEvent {
    #[prost(string, tag = "1")]
    pub event_type: String,
    #[prost(string, tag = "2")]
    pub source: String,
    #[prost(string, tag = "3")]
    pub order_id: String,
    #[prost(string, tag = "4")]
    pub user_id: String,
    #[prost(message, optional, tag = "5")]
    pub order_result: Option<OrderResult>,
    #[prost(string, tag = "6")]
    pub timestamp: String,
}

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct ShippingEvent {
    #[prost(string, tag = "1")]
    pub event_type: String,
    #[prost(string, tag = "2")]
    pub source: String,
    #[prost(string, tag = "3")]
    pub order_id: String,
    #[prost(string, tag = "4")]
    pub user_id: String,
    #[prost(message, optional, tag = "5")]
    pub order_result: Option<OrderResult>,
    #[prost(string, tag = "6")]
    pub timestamp: String,
}

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct OrderResult {
    #[prost(string, tag = "1")]
    pub order_id: String,
    #[prost(message, optional, tag = "2")]
    pub total_order_cost: Option<Money>,
    #[prost(message, optional, tag = "3")]
    pub shipping_address: Option<AddressProto>,
    #[prost(message, repeated, tag = "4")]
    pub items: ::prost::alloc::vec::Vec<OrderItem>,
}

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct OrderItem {
    #[prost(message, optional, tag = "1")]
    pub item: Option<CartItem>,
    #[prost(message, optional, tag = "2")]
    pub cost: Option<Money>,
}

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct CartItem {
    #[prost(string, tag = "1")]
    pub item_id: String,
    #[prost(int32, tag = "2")]
    pub quantity: i32,
}

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct Money {
    #[prost(string, tag = "1")]
    pub currency_code: String,
    #[prost(int64, tag = "2")]
    pub units: i64,
    #[prost(int32, tag = "3")]
    pub nanos: i32,
}

#[derive(Clone, PartialEq, ::prost::Message)]
pub struct AddressProto {
    #[prost(string, tag = "1")]
    pub street_address: String,
    #[prost(string, tag = "2")]
    pub city: String,
    #[prost(string, tag = "3")]
    pub state: String,
    #[prost(string, tag = "4")]
    pub country: String,
    #[prost(string, tag = "5")]
    pub zip_code: String,
}

// -----------------------------------------------------------------------------
// Kafka Consumer & Producer Loop
// -----------------------------------------------------------------------------

pub fn start_kafka_consumer() {
    let kafka_addr = match std::env::var("KAFKA_ADDR") {
        Ok(val) if !val.is_empty() => val,
        _ => {
            info!("KAFKA_ADDR is not set, skipping Shipping Kafka consumer/producer initialization.");
            return;
        }
    };

    let input_topic = std::env::var("KAFKA_PAYMENT_TOPIC")
        .or_else(|_| std::env::var("KAFKA_TOPIC"))
        .unwrap_or_else(|_| "domain.checkout.payment".to_string());
    let output_topic = std::env::var("KAFKA_SHIPPING_TOPIC")
        .or_else(|_| std::env::var("KAFKA_FULFILLMENT_TOPIC"))
        .unwrap_or_else(|_| "domain.checkout.shipping".to_string());
    let group_id = std::env::var("KAFKA_GROUP_ID").unwrap_or_else(|_| "shipping".to_string());
    let kafka_user = std::env::var("KAFKA_USER").unwrap_or_default();
    let kafka_password = std::env::var("KAFKA_PASSWORD").unwrap_or_default();

    let mut consumer_config = ClientConfig::new();
    consumer_config
        .set("bootstrap.servers", &kafka_addr)
        .set("group.id", &group_id)
        .set("enable.auto.commit", "false")
        .set("auto.offset.reset", "earliest");

    if !kafka_user.is_empty() && !kafka_password.is_empty() {
        consumer_config
            .set("security.protocol", "sasl_ssl")
            .set("sasl.mechanisms", "SCRAM-SHA-512")
            .set("sasl.username", &kafka_user)
            .set("sasl.password", &kafka_password);
    }

    let consumer: StreamConsumer = match consumer_config.create() {
        Ok(c) => c,
        Err(err) => {
            error!("Failed to create Shipping Kafka consumer: {:?}", err);
            return;
        }
    };

    let mut producer_config = ClientConfig::new();
    producer_config
        .set("bootstrap.servers", &kafka_addr)
        .set("compression.type", "zstd");
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

    if let Err(err) = consumer.subscribe(&[&input_topic]) {
        error!("Failed to subscribe to topic '{}': {:?}", input_topic, err);
        return;
    }

    info!(
        "Shipping Kafka consumer started. Subscribed to topic '{}' with group ID '{}', publishing to '{}'",
        input_topic, group_id, output_topic
    );

    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("Failed to build Tokio runtime for Shipping Kafka consumer");

        rt.block_on(async move {
            loop {
                if let Ok(msg) = consumer.recv().await {
                    let bytes = msg.payload().unwrap_or(&[]);

                    // 1. DECODE: Decode Protobuf PaymentEvent from domain.checkout.payment
                    let payment_event = match PaymentEvent::decode(bytes) {
                        Ok(evt) => evt,
                        Err(err) => {
                            error!("Failed to decode PaymentEvent from Kafka message: {:?}", err);
                            continue;
                        }
                    };

                    let order_id = if !payment_event.order_id.is_empty() {
                        payment_event.order_id.clone()
                    } else {
                        msg.key().map(|k| String::from_utf8_lossy(k).to_string()).unwrap_or_default()
                    };

                    // Extract currency code directly from incoming PaymentEvent -> OrderResult -> Money
                    let currency_code = payment_event
                        .order_result
                        .as_ref()
                        .and_then(|res| res.total_order_cost.as_ref())
                        .map(|cost| cost.currency_code.clone())
                        .filter(|c| !c.is_empty())
                        .unwrap_or_else(|| "USD".to_string());

                    // Calculate total items count from OrderResult
                    let item_count: u32 = payment_event
                        .order_result
                        .as_ref()
                        .map(|res| res.items.iter().map(|item| item.item.as_ref().map(|i| i.quantity as u32).unwrap_or(1)).sum())
                        .unwrap_or(1);

                    // 2. PROCESS: Calculate shipping quote cost
                    let quote = match create_quote_from_count(item_count).await {
                        Ok(q) => q,
                        Err(_) => crate::shipping_service::quote::create_quote_from_float(5.99),
                    };

                    info!(
                        "Order {}: calculated shipping cost quote = {}.{:02} {}",
                        order_id, quote.dollars, quote.cents, currency_code
                    );

                    let shipping_cost_money = Some(Money {
                        currency_code: currency_code.clone(),
                        units: quote.dollars as i64,
                        nanos: (quote.cents * 10_000_000) as i32,
                    });

                    // 3. ENCODE & SEND: Encode ShippingEvent Protobuf to domain.checkout.shipping
                    let mut order_result = payment_event.order_result.clone();
                    if let Some(ref mut res) = order_result {
                        res.total_order_cost = shipping_cost_money;
                    }

                    let timestamp_str = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map(|d| d.as_secs().to_string())
                        .unwrap_or_default();

                    let shipping_event = ShippingEvent {
                        event_type: "SHIPPING_COMPLETED".to_string(),
                        source: "shipping".to_string(),
                        order_id: order_id.clone(),
                        user_id: payment_event.user_id.clone(),
                        order_result,
                        timestamp: timestamp_str,
                    };

                    let mut encoded_bytes = Vec::new();
                    match shipping_event.encode(&mut encoded_bytes) {
                        Ok(_) => {
                            let record = FutureRecord::<str, [u8]>::to(&output_topic)
                                .payload(&encoded_bytes)
                                .key(&order_id);

                            match producer.send(record, Duration::from_secs(5)).await {
                                Ok(_) => info!(
                                    "Successfully published Protobuf ShippingEvent ({} bytes) to '{}' for order {}",
                                    encoded_bytes.len(),
                                    output_topic,
                                    order_id
                                ),
                                Err((err, _)) => error!("Failed to publish Protobuf message to Kafka: {:?}", err),
                            }
                        }
                        Err(err) => {
                            error!("Protobuf encoding failed for ShippingEvent: {:?}", err);
                        }
                    }
                }
            }
        });
    });
}
