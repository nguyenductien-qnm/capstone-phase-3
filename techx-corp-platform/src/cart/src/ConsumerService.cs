using Confluent.Kafka;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Oteldemo;
using System;
using System.Threading;
using System.Threading.Tasks;
using cart.cartstore;
                                                                                                                                         
namespace cart.services;                                                                                                                   
                                                                                                                                         
public class ConsumerService : BackgroundService                                                                              
{
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

                using var consumer = new ConsumerBuilder<string, byte[]>(config).Build();
                consumer.Subscribe(topicName);
                _logger.LogInformation("Cart ConsumerService listening on topic '{Topic}'", topicName);

                while (!stoppingToken.IsCancellationRequested)
                {
                    try
                    {
                        var consumeResult = consumer.Consume(TimeSpan.FromMilliseconds(500));
                        if (consumeResult?.Message?.Value == null) continue;

                        // 1. Decode Protobuf message from domain.checkout.shipping
                        ShippingEvent shippingEvent;
                        try
                        {
                            shippingEvent = ShippingEvent.Parser.ParseFrom(consumeResult.Message.Value);
                        }
                        catch (Exception parseEx)
                        {
                            _logger.LogWarning(parseEx, "Failed to parse ShippingEvent Protobuf message from topic '{Topic}'", topicName);
                            continue;
                        }

                        var orderId = !string.IsNullOrEmpty(shippingEvent.OrderId) ? shippingEvent.OrderId : (consumeResult.Message.Key ?? "");
                        var userId = shippingEvent.UserId;

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