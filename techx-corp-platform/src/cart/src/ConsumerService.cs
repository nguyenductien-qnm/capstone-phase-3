using Confluent.Kafka;                                                                                                                   
using Microsoft.Extensions.Hosting;                                                                                                      
using Microsoft.Extensions.Logging;                                                                                                      
using System;
using System.Collections.Concurrent;                                                                                                     
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using cart.cartstore;
                                                                                                                                         
namespace cart.services;                                                                                                                   
                                                                                                                                         
public class ConsumerService : BackgroundService                                                                              
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };
    private readonly ICartStore _cartStore;                                                                                              
    private readonly ILogger<ConsumerService> _logger;                                                                        
    private readonly ConcurrentDictionary<string, JoinState> _pendingJoins = new();                                                      
                                                                                                                                         
    public ConsumerService(ICartStore cartStore, ILogger<ConsumerService> logger)                                  
    {                                                                                                                                    
        _cartStore = cartStore;                                                                                                          
        _logger = logger;                                                                                                                
    }                                                                                                                                    
                                                                                                                                         
    protected override Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var kafkaAddr = Environment.GetEnvironmentVariable("KAFKA_ADDR");
        if (string.IsNullOrEmpty(kafkaAddr)) return Task.CompletedTask;

        _ = Task.Run(() =>
        {
            try
            {
                var config = new ConsumerConfig
                {
                    BootstrapServers = kafkaAddr,
                    GroupId = "cart-fulfillment-consumer",
                    AutoOffsetReset = AutoOffsetReset.Earliest,
                    EnableAutoCommit = true,
                    SecurityProtocol = SecurityProtocol.SaslSsl,
                    SaslMechanism = SaslMechanism.ScramSha512,
                    SaslUsername = Environment.GetEnvironmentVariable("KAFKA_USER") ?? "msk_user",
                    SaslPassword = Environment.GetEnvironmentVariable("KAFKA_PASSWORD") ?? ""
                };

                using var consumer = new ConsumerBuilder<string, string>(config).Build();
                consumer.Subscribe("domain.fulfillment.events");

                while (!stoppingToken.IsCancellationRequested)
                {
                    try
                    {
                        var consumeResult = consumer.Consume(TimeSpan.FromMilliseconds(500));
                        if (consumeResult?.Message?.Value == null) continue;

                        var eventData = JsonSerializer.Deserialize<FulfillmentEvent>(consumeResult.Message.Value, JsonOptions);
                        if (eventData == null || string.IsNullOrEmpty(eventData.OrderId)) continue;

                        var joinState = _pendingJoins.GetOrAdd(
                            eventData.OrderId,
                            id => new JoinState { OrderId = id, UserId = eventData.UserId }
                        );

                        if (!string.IsNullOrEmpty(eventData.UserId))
                        {
                            joinState.UserId = eventData.UserId;
                        }

                        if (eventData.EventType == "PAYMENT_COMPLETED") joinState.HasPayment = true;
                        if (eventData.EventType == "SHIPPING_COMPLETED") joinState.HasShipping = true;

                        if (joinState.HasPayment && joinState.HasShipping)
                        {
                            _logger.LogInformation(
                                "Payment and Shipping completed for Order {OrderId}. Clearing cart for user {UserId}...",
                                eventData.OrderId, joinState.UserId
                            );

                            var targetUserId = !string.IsNullOrEmpty(joinState.UserId) ? joinState.UserId : eventData.UserId;
                            if (!string.IsNullOrEmpty(targetUserId))
                            {
                                // Async ThreadPool safe
                                await _cartStore.EmptyCartAsync(targetUserId).ConfigureAwait(false);
                                _logger.LogInformation("Successfully cleared cart for user {UserId} (Order {OrderId})", targetUserId, eventData.OrderId);
                            }

                            _pendingJoins.TryRemove(eventData.OrderId, out _);
                        }
                    }
                    catch (OperationCanceledException) { break; }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Error processing fulfillment event in CartService consumer");
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Kafka consumer background task failed");
            }
        }, stoppingToken);

        return Task.CompletedTask;
    }
}                                                                                                                                        
                                                                                                                                         
public class FulfillmentEvent                                                                                                            
{                                                                                                                                        
    public string EventType { get; set; } = "";                                                                                          
    public string OrderId { get; set; } = "";                                                                                            
    public string UserId { get; set; } = "";                                                                                             
}                                                                                                                                        
                                                                                                                                         
public class JoinState                                                                                                                   
{                                                                                                                                        
    public string OrderId { get; set; } = "";                                                                                            
    public string UserId { get; set; } = "";
    public bool HasPayment { get; set; }
    public bool HasShipping { get; set; }
}