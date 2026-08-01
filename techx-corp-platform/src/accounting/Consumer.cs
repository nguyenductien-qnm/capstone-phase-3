// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using Confluent.Kafka;
using Microsoft.Extensions.Logging;
using Oteldemo;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;
using System.Text.Json;
using System.Threading.Tasks;

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
    private static readonly string TopicName = Environment.GetEnvironmentVariable("KAFKA_SHIPPING_TOPIC") 
                                            ?? Environment.GetEnvironmentVariable("KAFKA_TOPIC") 
                                            ?? "domain.checkout.shipping";
    private static readonly string GroupId = Environment.GetEnvironmentVariable("KAFKA_GROUP_ID") ?? "accounting";

    private ILogger _logger;
    private IConsumer<string, byte[]> _consumer;
    private bool _isListening;
    private DBContext? _dbContext;
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };
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
                    if (ProcessMessage(consumeResult.Message).GetAwaiter().GetResult())
                    {
                        _consumer.StoreOffset(consumeResult);
                    }
                    else
                    {
                        _consumer.Seek(consumeResult.TopicPartitionOffset);
                        Thread.Sleep(TimeSpan.FromSeconds(1));
                    }
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

    private static string CurrentOrderSchemaPhase()
    {
        return (Environment.GetEnvironmentVariable("ACCOUNTING_ORDER_SCHEMA_PHASE") ?? "legacy")
            .Trim()
            .ToLowerInvariant();
    }

    private static string CheckoutOrderPayloadSql()
    {
        return CurrentOrderSchemaPhase() switch
        {
            "dual_read" => "SELECT COALESCE(order_payload, order_metadata)::text AS \"Value\" FROM checkout.orders WHERE order_id = {0}",
            "read_new" => "SELECT order_payload::text AS \"Value\" FROM checkout.orders WHERE order_id = {0}",
            _ => "SELECT order_metadata::text AS \"Value\" FROM checkout.orders WHERE order_id = {0}"
        };
    }

    private async Task<bool> ProcessMessage(Message<string, byte[]> message)
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
                return true;
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

            // A logging level check 
            // is a conditional check that verifies whether the logger is configured to 
            // process logs at a specific log level before performing any work for that log statement
            if (_logger.IsEnabled(LogLevel.Information))
            {
                _logger.LogInformation("Accounting received fulfillment event for order {OrderId}. Payment: {Payment}, Shipping: {Shipping}",
                    orderId, joinState.HasPaymentEvent, joinState.HasShippingEvent);
            }

            // Kafka Streams Join condition: both Payment and Shipping events must be received for orderId
            if (joinState.HasPaymentEvent && joinState.HasShippingEvent)
            {
                _logger.LogInformation("Accounting Stream Join completed successfully for order {OrderId}. Both payment and shipping fulfillment events received.", orderId);

                if (_dbContext == null)
                {
                    _logger.LogError(
                        "Accounting database is unavailable for completed order {OrderId}; retrying",
                        orderId
                    );
                    return false;
                }

                // 1. Claim check: Query checkout.orders using orderId to get JSON metadata
                var rawJson = await _dbContext.Database
                    .SqlQueryRaw<string>(CheckoutOrderPayloadSql(), orderId)
                    .FirstOrDefaultAsync();

                if (string.IsNullOrWhiteSpace(rawJson))
                {
                    // A mixed-version pod may temporarily be unable to read the
                    // column used by checkout. Preserve the join and retry the Kafka
                    // record instead of storing its offset and losing accounting data.
                    _logger.LogWarning(
                        "Checkout payload for order {OrderId} is not visible in accounting schema phase {SchemaPhase}; retrying",
                        orderId,
                        CurrentOrderSchemaPhase()
                    );
                    return false;
                }

                // 2. Deserialize and validate before writing any accounting rows.
                var orderData = JsonSerializer.Deserialize<CheckoutOrderMetadata>(
                    rawJson, JsonOptions
                );
                var validationError = ValidateCheckoutOrderMetadata(orderData);
                if (validationError != null)
                {
                    _logger.LogWarning(
                        "Checkout payload for order {OrderId} is invalid ({ValidationError}); retrying",
                        orderId,
                        validationError
                    );
                    return false;
                }

                // 3. Write order details to accounting database tables.
                PersistOrderFromMetadata(orderId, orderData!);
                _pendingJoins.TryRemove(orderId, out _);
            }
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to process message in Accounting consumer:");
            return false;
        }
    }

internal class OrderFulfillmentJoinState
{
    public string OrderId { get; set; } = string.Empty;
    public bool HasPaymentEvent { get; set; }
    public bool HasShippingEvent { get; set; }
    public OrderResult? ParsedOrder { get; set; }
}

    private void PersistOrderFromMetadata(string orderId, CheckoutOrderMetadata metadata)
    // Handles transient database retry logic (IsLikelyTransientDbFailure). 
    // If PostgreSQL disconnects during writing, it disposes the poisoned DbContext, recreates a fresh instance, and retries writing.
    {
        try
        {
            WriteOrderGraphFromMetadata(
                orderId, // from kafka event 
                metadata // from checkout.orders (claim check)
            );
        }
        catch (Exception ex) when (IsLikelyTransientDbFailure(ex))
        {
            _logger.LogWarning(ex, "Transient DB failure persisting order {OrderId}; recreating DbContext and retrying once", orderId);
            try
            {
                _dbContext?.Dispose();
            }
            catch
            {
                // ignore dispose errors on a broken context
            }

            _dbContext = new DBContext();
            WriteOrderGraphFromMetadata(orderId, metadata);
        }
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
        // 1. Create Order entity
        var orderEntity = new OrderEntity
        {
            Id = order.OrderId
        };
        _dbContext!.Add(orderEntity);

        // 2. Map and add each purchased item
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

        // Map and add shipping information
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

        // 4. Commit all INSERTs to PostgreSQL in one atomic transaction
        _dbContext.SaveChanges();
    }

    private void WriteOrderGraphFromMetadata(string orderId, CheckoutOrderMetadata metadata)
    {
        // 1. Create Order entity
        var orderEntity = new OrderEntity
        {
            Id = orderId
        };
        _dbContext!.Add(orderEntity);

        // 2. Map items from orderItems JSON array
        foreach (var item in metadata.OrderItems!)
        {
            var cartItem = item.Item!;
            var cost = item.Cost!;
            var orderItem = new OrderItemEntity
            {
                OrderId = orderId,
                ProductId = cartItem.ProductId,
                Quantity = cartItem.Quantity,
                ItemCostCurrencyCode = cost.CurrencyCode,
                ItemCostUnits = cost.Units,
                ItemCostNanos = cost.Nanos
            };
            _dbContext.Add(orderItem);
        }

        // 3. Map shipping details
        var shippingCost = metadata.ShippingCostLocalized!;
        var address = metadata.Address!;
        var shipping = new ShippingEntity
        {
            OrderId = orderId,
            ShippingTrackingId = orderId,
            ShippingCostCurrencyCode = shippingCost.CurrencyCode,
            ShippingCostUnits = shippingCost.Units,
            ShippingCostNanos = shippingCost.Nanos,
            StreetAddress = address.StreetAddress,
            City = address.City,
            State = address.State,
            Country = address.Country,
            ZipCode = address.ZipCode
        };
        _dbContext.Add(shipping);

        // 4. Commit all INSERTs to PostgreSQL under 'accounting' schema
        _dbContext.SaveChanges();
    }

    internal static string? ValidateCheckoutOrderMetadata(CheckoutOrderMetadata? metadata)
    {
        if (metadata == null)
            return "payload is null";
        if (metadata.Address == null)
            return "address is missing";
        if (metadata.ShippingCostLocalized == null)
            return "shipping cost is missing";
        if (metadata.Total == null)
            return "total is missing";
        if (metadata.OrderItems == null || metadata.OrderItems.Count == 0)
            return "order items are missing";
        if (string.IsNullOrWhiteSpace(metadata.UserId))
            return "user ID is missing";
        if (string.IsNullOrWhiteSpace(metadata.UserCurrency))
            return "user currency is missing";
        if (string.IsNullOrWhiteSpace(metadata.ShippingCostLocalized.CurrencyCode))
            return "shipping currency is missing";
        if (string.IsNullOrWhiteSpace(metadata.Total.CurrencyCode))
            return "total currency is missing";

        foreach (var item in metadata.OrderItems)
        {
            if (item.Item == null)
                return "order item identity is missing";
            if (string.IsNullOrWhiteSpace(item.Item.ProductId))
                return "order item product ID is missing";
            if (item.Item.Quantity <= 0)
                return "order item quantity must be positive";
            if (item.Cost == null || string.IsNullOrWhiteSpace(item.Cost.CurrencyCode))
                return "order item cost is missing";
        }

        return null;
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
            EnableAutoOffsetStore = false,
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

public class CheckoutOrderMetadata
{
    public string UserId { get; set; } = "";
    public string UserCurrency { get; set; } = "";
    public MetadataAddress? Address { get; set; }
    public List<MetadataOrderItem>? OrderItems { get; set; }
    public MetadataMoney? ShippingCostLocalized { get; set; }
    public MetadataMoney? Total { get; set; }
}

public class MetadataOrderItem
{
    public MetadataCartItem? Item { get; set; }
    public MetadataMoney? Cost { get; set; }
}

public class MetadataCartItem
{
    public string ProductId { get; set; } = "";
    public int Quantity { get; set; }
}

public class MetadataMoney
{
    public string CurrencyCode { get; set; } = "USD";
    public long Units { get; set; }
    public int Nanos { get; set; }
}

public class MetadataAddress
{
    public string StreetAddress { get; set; } = "";
    public string City { get; set; } = "";
    public string State { get; set; } = "";
    public string Country { get; set; } = "";
    public string ZipCode { get; set; } = "";
}
