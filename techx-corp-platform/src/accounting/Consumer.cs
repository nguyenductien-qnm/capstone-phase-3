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

    private async Task<bool> ProcessMessage(Message<string, byte[]> message)
    {
        try
        {
            string orderId = message.Key ?? string.Empty;
            
            // Decode kafka message 
            ShippingEvent? shippingEvent = null;                                                                                                                             
            try                                                                                                                                                              
            {                                                                                                                                                                
                shippingEvent = ShippingEvent.Parser.ParseFrom(message.Value);                                                                                               
                if (string.IsNullOrEmpty(orderId) && shippingEvent != null)                                                                                                  
                {                                                                                                                                                            
                    orderId = shippingEvent.OrderId;                                                                                                                         
                }                                                                                                                                                            
            }                                                                                                                                                                
            catch (Exception ex)                                                                                                                                             
            {                                                                                                                                                                
                _logger.LogWarning("Failed to parse ShippingEvent Protobuf message for order {OrderId}: {Error}", orderId, ex.Message);                                      
                return true;                                                                                                                                                 
            }                                                                                                                                                                
                                                                                                                                                                             
            if (string.IsNullOrEmpty(orderId) || shippingEvent?.OrderResult == null)                                                                                         
            {                                                                                                                                                                
                _logger.LogWarning("Accounting consumed message on {Topic} without a valid orderId or OrderResult payload", TopicName);                                      
                return true;                                                                                                                                                 
            }                                                                                                                                                                
                                                                                                                                                                             
            if (_dbContext == null)                                                                                                                                          
            {                                                                                                                                                                
                _logger.LogError("Accounting database context is unavailable for completed order {OrderId}; retrying", orderId);                                             
                return false;                                                                                                                                                
            }
            
            // 3. PERSIST: Write order details directly to PostgreSQL tables (Order, CartItems, Shipping)                                                                    
            PersistOrder(shippingEvent.OrderResult);                                                                                                                         
            _logger.LogInformation("Successfully persisted order {OrderId} directly to Accounting database.", orderId);

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to process message in Accounting consumer:");
            return false;
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
                ItemCostCurrencyCode = item.Cost?.CurrencyCode ?? "USD",
                ItemCostUnits = item.Cost?.Units ?? 0,
                ItemCostNanos = item.Cost?.Nanos ?? 0,
                ProductId = item.Item?.ProductId ?? "",
                Quantity = item.Item?.Quantity ?? 1,
                OrderId = order.OrderId
            };

            _dbContext.Add(orderItem);
        }

        // Map and add shipping information
        var shippingCost = order.TotalOrderCost;
        var shipping = new ShippingEntity
        {
            ShippingTrackingId = order.OrderId,
            ShippingCostCurrencyCode = shippingCost?.CurrencyCode ?? "USD",
            ShippingCostUnits = shippingCost?.Units ?? 0,
            ShippingCostNanos = shippingCost?.Nanos ?? 0,
            StreetAddress = order.ShippingAddress?.StreetAddress ?? "",
            City = order.ShippingAddress?.City ?? "",
            State = order.ShippingAddress?.State ?? "",
            Country = order.ShippingAddress?.Country ?? "",
            ZipCode = order.ShippingAddress?.ZipCode ?? "",
            OrderId = order.OrderId
        };
        _dbContext.Add(shipping);

        // 4. Commit all INSERTs to PostgreSQL in one atomic transaction
        _dbContext.SaveChanges();
    }

    private static bool IsLikelyTransientDbFailure(Exception ex)
    {
        return ex is Npgsql.NpgsqlException || ex is DbUpdateException; 
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