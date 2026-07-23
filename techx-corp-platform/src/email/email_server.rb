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

# Kafka Fulfillment Stream Joiner for Email Consumer Group
def start_kafka_consumer
  kafka_addr = ENV["KAFKA_ADDR"]
  return if kafka_addr.nil? || kafka_addr.empty?

  topic = ENV.fetch("KAFKA_TOPIC", "domain.fulfillment.events")
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

      pending_joins = {}
      mutex = Mutex.new

      consumer.each_message do |message|
        order_id = message.key
        payload_str = message.value || ""

        if order_id.nil? || order_id.empty?
          begin
            json_data = JSON.parse(payload_str)
            order_id = json_data["orderId"] || json_data["key"]
          rescue StandardError
            order_id = nil
          end
        end

        next if order_id.nil? || order_id.empty?

        is_payment = payload_str.include?("payment") || payload_str.include?("PAYMENT")
        is_shipping = payload_str.include?("shipping") || payload_str.include?("SHIPPING")

        mutex.synchronize do
          state = pending_joins[order_id] ||= { payment: false, shipping: false }
          state[:payment] = true if is_payment
          state[:shipping] = true if is_shipping

          puts "Email consumer received fulfillment event for order #{order_id}. Payment: #{state[:payment]}, Shipping: #{state[:shipping]}"

          # Kafka Stream Join Condition: both payment and shipping completed for order_id
          if state[:payment] && state[:shipping]
            puts "Email Stream Join completed successfully for order #{order_id}. Both payment and shipping operations processed."
            $logger.on_emit(
              timestamp: Time.now,
              severity_text: 'INFO',
              body: "Email Stream Join completed for order #{order_id}",
              attributes: { 'app.order.id' => order_id },
            )
            $confirmation_counter.add(1) if $confirmation_counter
            pending_joins.delete(order_id)
          end
        end
      end
    rescue StandardError => e
      puts "Email Kafka consumer error or ruby-kafka not available: #{e.message}"
    end
  end
end

start_kafka_consumer
