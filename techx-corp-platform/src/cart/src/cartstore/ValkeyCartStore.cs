// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Grpc.Core;
using StackExchange.Redis;
using Google.Protobuf;
using Microsoft.Extensions.Logging;
using System.Diagnostics.Metrics;
using System.Diagnostics;

namespace cart.cartstore;

public class ValkeyCartStore : ICartStore
{
    private readonly ILogger _logger;
    private const string CartFieldName = "cart";
    private const int RedisRetryNumber = 30;

    // FIX #1: Connection pool — N parallel sockets thay vì 1 socket dùng chung.
    // Số lượng 4 đủ cho ~500 concurrent users mà không làm ElastiCache quá tải.
    private const int PoolSize = 4;
    private ConnectionMultiplexer[] _pool = Array.Empty<ConnectionMultiplexer>();
    private long _poolIndex = 0;

    private readonly byte[] _emptyCartBytes;
    private readonly string _connectionString;

    private static readonly ActivitySource CartActivitySource = new("OpenTelemetry.Demo.Cart");
    private static readonly Meter CartMeter = new Meter("OpenTelemetry.Demo.Cart");
    private static readonly Histogram<double> addItemHistogram = CartMeter.CreateHistogram(
        "app.cart.add_item.latency",
        unit: "s",
        advice: new InstrumentAdvice<double>
        {
            HistogramBucketBoundaries = [ 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10 ]
        });
    private static readonly Histogram<double> getCartHistogram = CartMeter.CreateHistogram(
        "app.cart.get_cart.latency",
        unit: "s",
        advice: new InstrumentAdvice<double>
        {
            HistogramBucketBoundaries = [ 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10 ]
        });
    private readonly ConfigurationOptions _redisConnectionOptions;

    public ValkeyCartStore(ILogger<ValkeyCartStore> logger, string valkeyAddress, string valkeyToken = "", bool valkeyTls = false)
    {
        _logger = logger;
        // Serialize empty cart into byte array.
        var cart = new Oteldemo.Cart();
        _emptyCartBytes = cart.ToByteArray();

        string sslVal = valkeyTls ? "true" : "false";
        _connectionString = $"{valkeyAddress},ssl={sslVal},allowAdmin=true,abortConnect=false";
        if (!string.IsNullOrEmpty(valkeyToken))
        {
            _connectionString += $",password={valkeyToken}";
        }

        _redisConnectionOptions = ConfigurationOptions.Parse(_connectionString);

        if (valkeyTls)
        {
            _redisConnectionOptions.CertificateValidation += (sender, cert, chain, err) => true;
        }

        // Try to reconnect multiple times if the first retry fails.
        _redisConnectionOptions.ConnectRetry = RedisRetryNumber;
        _redisConnectionOptions.ReconnectRetryPolicy = new ExponentialRetry(1000);

        _redisConnectionOptions.KeepAlive = 180;
        _redisConnectionOptions.AbortOnConnectFail = false;

        // FIX #3: Fail fast thay vì pile-up chờ 5 giây.
        // - ConnectTimeout: thời gian thiết lập TCP+TLS. 2s đủ cho ElastiCache cùng region.
        // - SyncTimeout: thời gian chờ response cho synchronous call (dùng ở Ping).
        // - AsyncTimeout: thời gian chờ response cho async call — key nhất, tránh request
        //   xếp hàng ngâm indefinitely khi ElastiCache bị nghẽn tạm thời.
        _redisConnectionOptions.ConnectTimeout = 2000;
        _redisConnectionOptions.SyncTimeout = 1000;
        _redisConnectionOptions.AsyncTimeout = 500;
    }

    /// <summary>
    /// Trả về connection đầu tiên trong pool.
    /// Dùng cho OTel StackExchangeRedis instrumentation (chỉ cần 1 connection để trace).
    /// </summary>
    public ConnectionMultiplexer GetConnection()
    {
        if (_pool.Length == 0)
            throw new InvalidOperationException("Valkey connection pool is not initialized. Call Initialize() first.");
        return _pool[0];
    }

    /// <summary>
    /// Trả về tất cả connections trong pool.
    /// Dùng khi muốn đăng ký OTel instrumentation cho toàn bộ pool.
    /// </summary>
    public ConnectionMultiplexer[] GetAllConnections()
    {
        return _pool;
    }

    public void Initialize()
    {
        // FIX #1: Khởi tạo toàn bộ connection pool tại startup.
        // Tất cả TLS handshake xảy ra 1 lần duy nhất ở đây, không bao giờ lặp lại trong hot path.
        _logger.LogInformation("Initializing Valkey connection pool (size={PoolSize})...", PoolSize);

        var pool = new ConnectionMultiplexer[PoolSize];
        for (int i = 0; i < PoolSize; i++)
        {
            pool[i] = CreateConnection(i);
        }
        _pool = pool;

        _logger.LogInformation("Valkey connection pool ready ({PoolSize} connections).", PoolSize);
    }

    private ConnectionMultiplexer CreateConnection(int slotIndex)
    {
        _logger.LogDebug("Creating Valkey connection [slot={slotIndex}]: {connectionString}", slotIndex, _connectionString);

        var mux = ConnectionMultiplexer.Connect(_redisConnectionOptions);

        if (mux == null || !mux.IsConnected)
        {
            _logger.LogError("Valkey connection [slot={slotIndex}] failed to establish.", slotIndex);
            throw new ApplicationException($"Wasn't able to connect to Valkey (pool slot {slotIndex})");
        }

        // Validate ngay sau connect
        var db = mux.GetDatabase();
        db.StringSet($"cart:pool-init-{slotIndex}", "OK");

        mux.InternalError += (_, e) =>
            _logger.LogError(e.Exception, "Valkey internal error [slot={slotIndex}]", slotIndex);
        mux.ConnectionRestored += (_, _) =>
            _logger.LogInformation("Valkey connection [slot={slotIndex}] restored.", slotIndex);
        mux.ConnectionFailed += (_, e) =>
            _logger.LogWarning("Valkey connection [slot={slotIndex}] failed: {reason}", slotIndex, e.FailureType);

        _logger.LogDebug("Valkey connection [slot={slotIndex}] established successfully.", slotIndex);
        return mux;
    }

    /// <summary>
    /// FIX #2: Round-robin qua pool bằng Interlocked.Increment — hoàn toàn lock-free.
    /// Không còn gọi EnsureRedisConnected() (blocking lock) trên mỗi request.
    /// </summary>
    private IDatabase GetPooledDatabase()
    {
        if (_pool.Length == 0)
            throw new InvalidOperationException("Valkey connection pool is not initialized.");

        // Modulo trên pool.Length (không phải hằng PoolSize) để an toàn nếu pool ngắn hơn dự kiến.
        var idx = (int)(Interlocked.Increment(ref _poolIndex) % _pool.Length);
        return _pool[idx].GetDatabase();
    }

    public async Task AddItemAsync(string userId, string productId, int quantity)
    {
        var stopwatch = Stopwatch.StartNew();

        if (_logger.IsEnabled(LogLevel.Information))
        {
            _logger.LogInformation(
                "AddItemAsync called with userId={userId}, productId={productId}, quantity={quantity}",
                userId, productId, quantity);
        }

        try
        {
            // FIX #2: GetPooledDatabase() — không lock, không check connection mỗi lần.
            var db = GetPooledDatabase();

            // Access the cart from the cache
            var value = await db.HashGetAsync(userId, CartFieldName);

            Oteldemo.Cart cart;
            if (value.IsNull)
            {
                cart = new Oteldemo.Cart { UserId = userId };
                cart.Items.Add(new Oteldemo.CartItem { ProductId = productId, Quantity = quantity });
            }
            else
            {
                cart = Oteldemo.Cart.Parser.ParseFrom(value);
                var existingItem = cart.Items.SingleOrDefault(i => i.ProductId == productId);
                if (existingItem == null)
                {
                    cart.Items.Add(new Oteldemo.CartItem { ProductId = productId, Quantity = quantity });
                }
                else
                {
                    existingItem.Quantity += quantity;
                }
            }

            var batch = db.CreateBatch();
            var hashSetTask = batch.HashSetAsync(userId, new[] { new HashEntry(CartFieldName, cart.ToByteArray()) });
            var keyExpireTask = batch.KeyExpireAsync(userId, TimeSpan.FromMinutes(60));
            batch.Execute();
            await Task.WhenAll(hashSetTask, keyExpireTask);
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
        finally
        {
            addItemHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    public async Task EmptyCartAsync(string userId)
    {
        if (_logger.IsEnabled(LogLevel.Information))
        {
            _logger.LogInformation("EmptyCartAsync called with userId={userId}", userId);
        }

        try
        {
            // FIX #2: GetPooledDatabase() — không lock, không check connection mỗi lần.
            var db = GetPooledDatabase();

            // Update the cache with empty cart for given user
            var batch = db.CreateBatch();
            var hashSetTask = batch.HashSetAsync(userId, new[] { new HashEntry(CartFieldName, _emptyCartBytes) });
            var keyExpireTask = batch.KeyExpireAsync(userId, TimeSpan.FromMinutes(60));
            batch.Execute();
            await Task.WhenAll(hashSetTask, keyExpireTask);
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
    }

    public async Task<Oteldemo.Cart> GetCartAsync(string userId)
    {
        var stopwatch = Stopwatch.StartNew();

        if (_logger.IsEnabled(LogLevel.Information))
        {
            _logger.LogInformation("GetCartAsync called with userId={userId}", userId);
        }

        try
        {
            // FIX #2: GetPooledDatabase() — không lock, không check connection mỗi lần.
            var db = GetPooledDatabase();

            // Access the cart from the cache
            var value = await db.HashGetAsync(userId, CartFieldName);

            if (!value.IsNull)
            {
                return Oteldemo.Cart.Parser.ParseFrom(value);
            }

            // We decided to return empty cart in cases when user wasn't in the cache before
            return new Oteldemo.Cart();
        }
        catch (Exception ex)
        {
            throw new RpcException(new Status(StatusCode.FailedPrecondition, $"Can't access cart storage. {ex}"));
        }
        finally
        {
            getCartHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    public bool Ping()
    {
        try
        {
            // Ping dùng connection slot 0 (đơn giản, không cần round-robin cho health check)
            if (_pool.Length == 0) return false;
            var cache = _pool[0].GetDatabase();
            var res = cache.Ping();
            return res != TimeSpan.Zero;
        }
        catch (Exception)
        {
            return false;
        }
    }
}
