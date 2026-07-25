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
                                                                                                                                         
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)                                                          
    {                                                                                                                                    
        var kafkaAddr = Environment.GetEnvironmentVariable("KAFKA_ADDR");                                                                
        if (string.IsNullOrEmpty(kafkaAddr)) return;                                                                                     
                                                                                                                                         
        var config = new ConsumerConfig                                                                                                  
        {                                                                                                                                
            BootstrapServers = kafkaAddr,                                                                                                
            GroupId = "cart-fulfillment-consumer", // Independent consumer group                                                         
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
                var consumeResult = consumer.Consume(stoppingToken);                                                                     
                if (consumeResult?.Message?.Value == null) continue;                                                                     
                                                                                                                                         
                var eventData = JsonSerializer.Deserialize<FulfillmentEvent>(consumeResult.Message.Value, JsonOptions);                               
                if (eventData == null || string.IsNullOrEmpty(eventData.OrderId)) continue;                                              
                                                                                                                                         
                // 1. Maintain Stream Join state per orderId                                                                             
                var joinState = _pendingJoins.GetOrAdd(
                    eventData.OrderId, 
                    id => new JoinState { OrderId = id, UserId = eventData.UserId  
                });

                if (!string.IsNullOrEmpty(eventData.UserId))
                {
                    joinState.UserId = eventData.UserId;
                }
                                                                                                                                         
                if (eventData.EventType == "PAYMENT_COMPLETED")  joinState.HasPayment = true;                                            
                if (eventData.EventType == "SHIPPING_COMPLETED") joinState.HasShipping = true;                                           
                                                                                                                                         
                // 2. Once BOTH Payment & Shipping succeed, empty the cart directly!                                                     
                if (joinState.HasPayment && joinState.HasShipping)                                                                       
                {                                                                                                                        
                    _logger.LogInformation(
                        "Payment and Shipping completed for Order {OrderId}. Clearing cart for user {UserId}...",     
                        eventData.OrderId, joinState.UserId
                    );                                                                                                      
                                                                                                                                         
                    if (!string.IsNullOrEmpty(joinState.UserId))
                    {
                        await _cartStore.EmptyCartAsync(joinState.UserId);
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