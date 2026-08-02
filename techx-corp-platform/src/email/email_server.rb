# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "ostruct"
require "pony"
require "sinatra"
require "open_feature/sdk"
require "openfeature/flagd/provider"

require "opentelemetry/sdk"
require "opentelemetry-logs-sdk"
require "opentelemetry-metrics-sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry-exporter-otlp-logs"
require "opentelemetry-exporter-otlp-metrics"
require "opentelemetry/instrumentation/sinatra"

set :port, ENV["EMAIL_PORT"]

# Initialize OpenFeature SDK with flagd provider
flagd_client = OpenFeature::Flagd::Provider.build_client
flagd_client.configure do |config|
  config.host = ENV.fetch("FLAGD_HOST", "localhost")
  config.port = ENV.fetch("FLAGD_PORT", 8013).to_i
  config.tls = ENV.fetch("FLAGD_TLS", "false") == "true"
end

OpenFeature::SDK.configure do |config|
  config.set_provider(flagd_client)
end

OpenTelemetry::SDK.configure do |c|
  c.use "OpenTelemetry::Instrumentation::Sinatra"
end

$logger = OpenTelemetry.logger_provider.logger(name: 'email')

otlp_metric_exporter = OpenTelemetry::Exporter::OTLP::Metrics::MetricsExporter.new
OpenTelemetry.meter_provider.add_metric_reader(otlp_metric_exporter)
meter = OpenTelemetry.meter_provider.meter("email")
$confirmation_counter = meter.create_counter("app.confirmation.counter", unit: "1", description: "Counts the number of order confirmation emails sent")

post "/send_order_confirmation" do
  data = JSON.parse(request.body.read, object_class: OpenStruct)

  # get the current auto-instrumented span
  current_span = OpenTelemetry::Trace.current_span
  current_span.add_attributes({
    "app.order.id" => data.order.order_id,
  })

  $confirmation_counter.add(1)
  send_email(data)

end

error do
  OpenTelemetry::Trace.current_span.record_exception(env['sinatra.error'])
end

def send_email(data)
  # create and start a manual span
  tracer = OpenTelemetry.tracer_provider.tracer('email')
  tracer.in_span("send_email") do |span|
    # Check if memory leak flag is enabled
    client = OpenFeature::SDK.build_client
    memory_leak_multiplier = client.fetch_number_value(flag_key: "emailMemoryLeak", default_value: 0)

    # To speed up the memory leak we create a long email body
    confirmation_content = erb(:confirmation, locals: { order: data.order })
    whitespace_length = [0, confirmation_content.length * (memory_leak_multiplier-1)].max

    Pony.mail(
      to:       data.email,
      from:     "noreply@example.com",
      subject:  "Your confirmation email",
      body:     confirmation_content + " " * whitespace_length,
      via:      :test
    )

    # If not clearing the deliveries, the emails will accumulate in the test mailer
    # We use this to create a memory leak.
    if memory_leak_multiplier < 1
      Mail::TestMailer.deliveries.clear
    end

    span.set_attribute("app.email.recipient", data.email)
    $logger.on_emit(
      timestamp: Time.now,
      severity_text: 'INFO',
      body: 'Order confirmation email sent',
      attributes: { 'app.email.recipient' => data.email },
    )

    puts "Order confirmation email sent to: #{data.email}"
  end
  # manually created spans need to be ended
  # in Ruby, the method `in_span` ends it automatically
  # check out the OpenTelemetry Ruby docs at: 
  # https://opentelemetry.io/docs/instrumentation/ruby/manual/#creating-new-spans 
end

def to_ostruct(object)
  case object
  when Hash
    OpenStruct.new(object.transform_values { |v| to_ostruct(v) })
  when Array
    object.map { |v| to_ostruct(v) }
  else
    object
  end
end

def build_email_data(order_id, state)
  email = state[:email] || "customer@example.com"
  order = state[:order]

  unless order
    order = OpenStruct.new(
      order_id: order_id,
      shipping_tracking_id: state[:shipping_tracking_id] || "TRACK-#{order_id[0..7]}",
      shipping_cost: OpenStruct.new(
        units: 0,
        nanos: 0,
        currency_code: "USD"
      ),
      shipping_address: OpenStruct.new(
        street_address_1: "1600 Amphitheatre Parkway",
        street_address_2: "",
        city: "Mountain View",
        country: "USA",
        zip_code: "94043"
      ),
      items: []
    )
  end

  OpenStruct.new(email: email, order: order)
end

# Kafka Fulfillment Consumer for Email Service
def start_kafka_consumer
  kafka_addr = ENV["KAFKA_ADDR"]
  return if kafka_addr.nil? || kafka_addr.empty?

  topic = ENV.fetch("KAFKA_SHIPPING_TOPIC", ENV.fetch("KAFKA_TOPIC", "domain.checkout.shipping"))
  group_id = ENV.fetch("KAFKA_GROUP_ID", "email")
  kafka_user = ENV["KAFKA_USER"]
  kafka_password = ENV["KAFKA_PASSWORD"]

  brokers = kafka_addr.split(",").map(&:strip).reject(&:empty?)

  Thread.new do
    begin
      require "kafka"

      kafka_opts = {
        seed_brokers: brokers,
        client_id: "email-service",
        connect_timeout: 10
      }

      if kafka_user && !kafka_user.empty? && kafka_password && !kafka_password.empty?
        kafka_opts[:ssl] = true
        kafka_opts[:sasl_scram_username] = kafka_user
        kafka_opts[:sasl_scram_password] = kafka_password
        kafka_opts[:sasl_scram_mechanism] = "sha512"
      end

      kafka = Kafka.new(**kafka_opts)
      consumer = kafka.consumer(group_id: group_id)
      consumer.subscribe(topic, default_offset: :earliest)

      puts "Email Kafka consumer started. Subscribed to topic '#{topic}' under group '#{group_id}'."

      consumer.each_message do |message|
        order_id = message.key
        payload_str = message.value || ""

        json_data = {}
        begin
          json_data = JSON.parse(payload_str)
        rescue StandardError
          json_data = {}
        end

        if order_id.nil? || order_id.empty?
          order_id = json_data["orderId"] || json_data["key"] || json_data["order_id"] || "UNKNOWN"
        end

        puts "Email consumer received shipping event for order #{order_id} on topic '#{topic}'"

        $logger.on_emit(
          timestamp: Time.now,
          severity_text: 'INFO',
          body: "Email shipping event received for order #{order_id}",
          attributes: { 'app.order.id' => order_id }
        ) if $logger

        $confirmation_counter.add(1) if $confirmation_counter

        # Send order confirmation email directly upon receiving shipping completion event
        state = { email: json_data["email"], order_id: order_id }
        data = build_email_data(order_id, state)
        send_email(data)
        puts "Successfully sent order confirmation email for order #{order_id}"
      end
    rescue StandardError => e
      puts "Email Kafka consumer error or ruby-kafka not available: #{e.message}"
    end
  end
end

start_kafka_consumer
