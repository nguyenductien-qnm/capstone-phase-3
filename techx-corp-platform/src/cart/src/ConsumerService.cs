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
                                                                                                                                         
    public ConsumerService(ICartStore cartStore, ILogger<ConsumerService> logger)                                  
    {                                                                                                                                    
        _cartStore = cartStore;                                                                                                          
        _logger = logger;                                                                                                                
    }                                                                                                                                    
                                                                                                                                         
    protected override Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var kafkaAddr = Environment.GetEnvironmentVariable("KAFKA_ADDR");
        if (string.IsNullOrEmpty(kafkaAddr)) return Task.CompletedTask;

        _ = Task.Run(async () =>
        {
            try
            {
                var config = new ConsumerConfig
                {
                    BootstrapServers = kafkaAddr,
                    GroupId = "cart-cleanup",
                    AutoOffsetReset = AutoOffsetReset.Earliest,
                    EnableAutoCommit = true,
                    SecurityProtocol = SecurityProtocol.SaslSsl,
                    SaslMechanism = SaslMechanism.ScramSha512,
                    SaslUsername = Environment.GetEnvironmentVariable("KAFKA_USER") ?? "msk_user",
                    SaslPassword = Environment.GetEnvironmentVariable("KAFKA_PASSWORD") ?? ""
                };

                var topicName = Environment.GetEnvironmentVariable("KAFKA_SHIPPING_TOPIC")
                            ?? Environment.GetEnvironmentVariable("KAFKA_TOPIC")
                            ?? "domain.checkout.shipping";

                using var consumer = new ConsumerBuilder<string, string>(config).Build();
                consumer.Subscribe(topicName);
                _logger.LogInformation("Cart ConsumerService listening on topic '{Topic}'", topicName);

                while (!stoppingToken.IsCancellationRequested)
                {
                    try
                    {
                        var consumeResult = consumer.Consume(TimeSpan.FromMilliseconds(500));
                        if (consumeResult?.Message?.Value == null) continue;

                        // 1. Decode event from domain.checkout.shipping
                        var eventData = JsonSerializer.Deserialize<FulfillmentEvent>(consumeResult.Message.Value, JsonOptions);
                        var orderId = eventData?.OrderId ?? consumeResult.Message.Key ?? "";                                                                                 
                        var userId = eventData?.UserId;

                        var joinState = _pendingJoins.GetOrAdd(
                            eventData.OrderId,
                            id => new JoinState { OrderId = id, UserId = eventData.UserId }
                        );

                        // 2. Empty cart
                        if (!string.IsNullOrEmpty(userId))
                        {
                            _logger.LogInformation(                                                                                                                          
                                "Shipping completed for Order {OrderId}. Clearing cart for user {UserId}...",                                                                
                                orderId, userId                                                                                                                              
                            );
                           
                            // Async ThreadPool safe
                            await _cartStore.EmptyCartAsync(userId).ConfigureAwait(false);
                            _logger.LogInformation("Successfully cleared cart for user {UserId} (Order {OrderId})", userId, orderId);
                        }
                    }
                    catch (OperationCanceledException) { break; }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Error processing event in CartService consumer");
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Cart ConsumerService background task failed");
            }
        }, stoppingToken);

        return Task.CompletedTask;
    }
}                                                                                                                                        
                                                                                                                                         