// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
using Microsoft.Extensions.Logging;
using Oteldemo;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;

namespace Accounting;

internal class DBContext : DbContext
{
    public DbSet<OrderEntity> Orders { get; set; }
    public DbSet<OrderItemEntity> CartItems { get; set; }
    public DbSet<ShippingEntity> Shipping { get; set; }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        var connectionString = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING");

        // CDO-TBD1: EF execution strategy retries transient Npgsql/RDS blips
        // (failover, Proxy reconnect) on SaveChanges without restarting the pod.
        optionsBuilder
            .UseNpgsql(connectionString, npgsql =>
            {
                npgsql.EnableRetryOnFailure(
                    maxRetryCount: 5,
                    maxRetryDelay: TimeSpan.FromSeconds(5),
                    errorCodesToAdd: null);
            })
            .UseSnakeCaseNamingConvention();
    }
}


internal class Consumer : IDisposable
{
    private static readonly string TopicName = Environment.GetEnvironmentVariable("KAFKA_TOPIC") ?? "domain.fulfillment.events";
    private static readonly string GroupId = Environment.GetEnvironmentVariable("KAFKA_GROUP_ID") ?? "accounting";

    private ILogger _logger;
    private IConsumer<string, byte[]> _consumer;
    private bool _isListening;
    private DBContext? _dbContext;
    private static readonly ActivitySource MyActivitySource = new("Accounting.Consumer");

    public Consumer(ILogger<Consumer> logger)
    {
        _logger = logger;

        var servers = Environment.GetEnvironmentVariable("KAFKA_ADDR")
            ?? throw new InvalidOperationException("The KAFKA_ADDR environment variable is not set.");

        _consumer = BuildConsumer(servers);
        _consumer.Subscribe(TopicName);

       if (_logger.IsEnabled(LogLevel.Information))
       {
           _logger.LogInformation("Accounting Consumer connecting to Kafka: {servers}, topic: {topic}, group: {group}", servers, TopicName, GroupId);
       }

        _dbContext = Environment.GetEnvironmentVariable("DB_CONNECTION_STRING") == null ? null : new DBContext();
    }

    public void StartListening()
    {
        _isListening = true;

        try
        {
            while (_isListening)
            {
                try
                {
                    using var activity = MyActivitySource.StartActivity("order-consumed",  ActivityKind.Internal);
                    var consumeResult = _consumer.Consume();
                    ProcessMessage(consumeResult.Message);
                }
                catch (ConsumeException e)
                {
                    if (_logger.IsEnabled(LogLevel.Error))
                    {
                        _logger.LogError(e, "Consume error: {reason}", e.Error.Reason);
                    }
                }
            }
        }
        catch (OperationCanceledException)
        {
            _logger.LogInformation("Closing consumer");

            _consumer.Close();
        }
    }

    private readonly System.Collections.Concurrent.ConcurrentDictionary<string, OrderFulfillmentJoinState> _pendingJoins = new();

    private void ProcessMessage(Message<string, byte[]> message)
    {
        try
        {
            string orderId = message.Key ?? string.Empty;
            string payloadStr = System.Text.Encoding.UTF8.GetString(message.Value ?? Array.Empty<byte>());

            string source = "";
            string eventType = "";
            OrderResult? parsedOrder = null;

            try
            {
                using var doc = System.Text.Json.JsonDocument.Parse(payloadStr);
                var root = doc.RootElement;

                if (root.TryGetProperty("source", out var srcProp))
                    source = srcProp.GetString() ?? "";
                if (root.TryGetProperty("eventType", out var etProp))
                    eventType = etProp.GetString() ?? "";

                if (string.IsNullOrEmpty(orderId))
                {
                    if (root.TryGetProperty("orderId", out var idProp))
                        orderId = idProp.GetString() ?? "";
                    else if (root.TryGetProperty("key", out var keyProp))
                        orderId = keyProp.GetString() ?? "";
                }

                if (root.TryGetProperty("details", out var detProp))
                {
                    var detailsStr = detProp.GetString();
                    if (!string.IsNullOrEmpty(detailsStr))
                    {
                        try
                        {
                            parsedOrder = OrderResult.Parser.ParseFrom(System.Text.Encoding.UTF8.GetBytes(detailsStr));
                        }
                        catch { }
                    }
                }
            }
            catch
            {
                try
                {
                    parsedOrder = OrderResult.Parser.ParseFrom(message.Value);
                    if (parsedOrder != null && !string.IsNullOrEmpty(parsedOrder.OrderId))
                    {
                        orderId = parsedOrder.OrderId;
                    }
                }
                catch { }
            }

            if (string.IsNullOrEmpty(orderId))
            {
                _logger.LogWarning("Accounting consumed message on {Topic} without a valid orderId key", TopicName);
                return;
            }

            var joinState = _pendingJoins.GetOrAdd(orderId, id => new OrderFulfillmentJoinState { OrderId = id });

            bool isPayment = source.Equals("payment", StringComparison.OrdinalIgnoreCase) 
                          || eventType.Contains("PAYMENT", StringComparison.OrdinalIgnoreCase);
            bool isShipping = source.Equals("shipping", StringComparison.OrdinalIgnoreCase) 
                           || eventType.Contains("SHIPPING", StringComparison.OrdinalIgnoreCase);

            if (isPayment)
            {
                joinState.HasPaymentEvent = true;
            }
            if (isShipping)
            {
                joinState.HasShippingEvent = true;
            }
            if (parsedOrder != null)
            {
                joinState.ParsedOrder = parsedOrder;
            }

            _logger.LogInformation("Accounting received fulfillment event for order {OrderId}. Payment: {Payment}, Shipping: {Shipping}",
                orderId, joinState.HasPaymentEvent, joinState.HasShippingEvent);

            // Kafka Streams Join condition: both Payment and Shipping events must be received for orderId
            if (joinState.HasPaymentEvent && joinState.HasShippingEvent)
            {
                _logger.LogInformation("Accounting Stream Join completed successfully for order {OrderId}. Both payment and shipping fulfillment events received.", orderId);
                _pendingJoins.TryRemove(orderId, out _);

                if (joinState.ParsedOrder != null)
                {
                    Log.OrderReceivedMessage(_logger, joinState.ParsedOrder);

                    if (_dbContext != null)
                    {
                        PersistOrder(joinState.ParsedOrder);
                    }
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to process message in Accounting consumer:");
        }
    }

internal class OrderFulfillmentJoinState
{
    public string OrderId { get; set; } = string.Empty;
    public bool HasPaymentEvent { get; set; }
    public bool HasShippingEvent { get; set; }
    public OrderResult? ParsedOrder { get; set; }
}

    /// <summary>
    /// CDO-TBD1: write path with EF retry strategy; if the context is poisoned
    /// after a hard disconnect, recreate once and retry the unit of work.
    /// </summary>
    private void PersistOrder(OrderResult order)
    {
        try
        {
            WriteOrderGraph(order);
        }
        catch (Exception ex) when (IsLikelyTransientDbFailure(ex))
        {
            _logger.LogWarning(ex, "Transient DB failure persisting order {OrderId}; recreating DbContext and retrying once", order.OrderId);
            try
            {
                _dbContext?.Dispose();
            }
            catch
            {
                // ignore dispose errors on a broken context
            }

            _dbContext = new DBContext();
            WriteOrderGraph(order);
        }
    }

    private void WriteOrderGraph(OrderResult order)
    {
        var orderEntity = new OrderEntity
        {
            Id = order.OrderId
        };
        _dbContext!.Add(orderEntity);
        foreach (var item in order.Items)
        {
            var orderItem = new OrderItemEntity
            {
                ItemCostCurrencyCode = item.Cost.CurrencyCode,
                ItemCostUnits = item.Cost.Units,
                ItemCostNanos = item.Cost.Nanos,
                ProductId = item.Item.ProductId,
                Quantity = item.Item.Quantity,
                OrderId = order.OrderId
            };

            _dbContext.Add(orderItem);
        }

        var shipping = new ShippingEntity
        {
            ShippingTrackingId = order.ShippingTrackingId,
            ShippingCostCurrencyCode = order.ShippingCost.CurrencyCode,
            ShippingCostUnits = order.ShippingCost.Units,
            ShippingCostNanos = order.ShippingCost.Nanos,
            StreetAddress = order.ShippingAddress.StreetAddress,
            City = order.ShippingAddress.City,
            State = order.ShippingAddress.State,
            Country = order.ShippingAddress.Country,
            ZipCode = order.ShippingAddress.ZipCode,
            OrderId = order.OrderId
        };
        _dbContext.Add(shipping);
        _dbContext.SaveChanges();
    }

    private static bool IsLikelyTransientDbFailure(Exception ex)
    {
        // String/type heuristics for a poisoned long-lived DbContext after RDS blip.
        // Permanent SQL errors (unique violation, FK, ...) should return false.
        for (Exception? e = ex; e != null; e = e.InnerException)
        {
            if (e is TimeoutException)
            {
                return true;
            }

            if (e is Npgsql.PostgresException pg)
            {
                // 08xxx = connection exception; 40001 serialization; 40P01 deadlock;
                // 57P01 admin shutdown; 57P03 cannot connect now.
                if (pg.IsTransient
                    || (pg.SqlState is not null && pg.SqlState.StartsWith("08", StringComparison.Ordinal))
                    || pg.SqlState is "40001" or "40P01" or "57P01" or "57P03")
                {
                    return true;
                }
                return false;
            }

            if (e is Npgsql.NpgsqlException)
            {
                return true;
            }

            var msg = e.Message;
            if (msg.Contains("Exception while reading from stream", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("Connection is not open", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("broken", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("timeout", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("server closed", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("connection reset", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("the database system is starting up", StringComparison.OrdinalIgnoreCase)
                || msg.Contains("the database system is in recovery mode", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }
        return false;
    }

    private static IConsumer<string, byte[]> BuildConsumer(string servers)
    {
        var conf = new ConsumerConfig
        {
            GroupId = GroupId,
            BootstrapServers = servers,
            // https://github.com/confluentinc/confluent-kafka-dotnet/tree/07de95ed647af80a0db39ce6a8891a630423b952#basic-consumer-example
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = true,
            SecurityProtocol = SecurityProtocol.SaslSsl,
            SaslMechanism = SaslMechanism.ScramSha512,
            SaslUsername = Environment.GetEnvironmentVariable("KAFKA_USER"),
            SaslPassword = Environment.GetEnvironmentVariable("KAFKA_PASSWORD")
        };

        return new ConsumerBuilder<string, byte[]>(conf)
            .Build();
    }

    public void Dispose()
    {
        _isListening = false;
        _consumer?.Dispose();
    }
}
