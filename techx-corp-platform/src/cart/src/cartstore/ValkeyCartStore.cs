// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Google.Protobuf;
using Grpc.Core;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;

namespace cart.cartstore;

/// <summary>
/// Valkey-backed cart store.
///
/// Design goals:
/// - Reuse a small, fixed ConnectionMultiplexer pool.
/// - Never validate TLS certificates with an "always true" callback.
/// - Never log the Redis password/connection string.
/// - Fail fast when no connection is available instead of building a backlog.
/// - Preserve the existing protobuf storage schema.
/// - Prevent lost updates with optimistic Redis transactions.
/// - Commit cart data and TTL atomically in the same MULTI/EXEC transaction.
/// </summary>
public sealed class ValkeyCartStore : ICartStore, IDisposable, IAsyncDisposable
{
    private const string CartFieldName = "cart";

    private const int DefaultPoolSize = 4;
    private const int MaximumPoolSize = 16;
    private const int RedisConnectRetryCount = 3;
    private const int MaximumCartUpdateRetries = 12;

    private static readonly TimeSpan CartTtl = TimeSpan.FromMinutes(60);
    private static readonly TimeSpan RedisOperationTimeout = TimeSpan.FromSeconds(1);

    private static readonly Meter CartMeter = new("OpenTelemetry.Demo.Cart");

    private static readonly Histogram<double> AddItemHistogram = CartMeter.CreateHistogram(
        "app.cart.add_item.latency",
        unit: "s",
        advice: new InstrumentAdvice<double>
        {
            HistogramBucketBoundaries =
            [
                0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25,
                0.5, 0.75, 1, 2.5, 5, 7.5, 10
            ]
        });

    private static readonly Histogram<double> GetCartHistogram = CartMeter.CreateHistogram(
        "app.cart.get_cart.latency",
        unit: "s",
        advice: new InstrumentAdvice<double>
        {
            HistogramBucketBoundaries =
            [
                0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25,
                0.5, 0.75, 1, 2.5, 5, 7.5, 10
            ]
        });

    private static readonly Histogram<double> EmptyCartHistogram = CartMeter.CreateHistogram(
        "app.cart.empty_cart.latency",
        unit: "s");

    private static readonly Counter<long> CartUpdateConflictCounter = CartMeter.CreateCounter<long>(
        "app.cart.update_conflicts",
        unit: "conflict");

    private readonly ILogger<ValkeyCartStore> _logger;
    private readonly string _valkeyAddress;
    private readonly string _valkeyToken;
    private readonly bool _valkeyTls;
    private readonly int _poolSize;
    private readonly string _safeEndpoints;
    private readonly object _lifecycleLock = new();

    private ConnectionMultiplexer[] _pool = Array.Empty<ConnectionMultiplexer>();
    private long _poolIndex = -1;
    private int _disposed;

    public ValkeyCartStore(
        ILogger<ValkeyCartStore> logger,
        string valkeyAddress,
        string valkeyToken = "",
        bool valkeyTls = false,
        int poolSize = DefaultPoolSize)
    {
        if (logger is null)
        {
            throw new ArgumentNullException(nameof(logger));
        }

        if (string.IsNullOrWhiteSpace(valkeyAddress))
        {
            throw new ArgumentException("Valkey address is required.", nameof(valkeyAddress));
        }

        if (poolSize is < 1 or > MaximumPoolSize)
        {
            throw new ArgumentOutOfRangeException(
                nameof(poolSize),
                poolSize,
                $"Pool size must be between 1 and {MaximumPoolSize}.");
        }

        _logger = logger;
        _valkeyAddress = valkeyAddress;
        _valkeyToken = valkeyToken;
        _valkeyTls = valkeyTls;
        _poolSize = poolSize;

        // Parse only to produce a safe endpoint string. Password and options are not logged.
        var parsed = ConfigurationOptions.Parse(valkeyAddress);
        _safeEndpoints = parsed.EndPoints.Count == 0
            ? "<unresolved>"
            : string.Join(",", parsed.EndPoints.Select(static endpoint => endpoint.ToString()));
    }

    /// <summary>
    /// Initializes the connection pool once. A disconnected multiplexer is accepted when
    /// AbortOnConnectFail=false so StackExchange.Redis can reconnect in the background.
    /// Readiness should be determined through Ping().
    /// </summary>
    public void Initialize()
    {
        ThrowIfDisposed();

        lock (_lifecycleLock)
        {
            ThrowIfDisposed();

            if (_pool.Length != 0)
            {
                return;
            }

            if (_logger.IsEnabled(LogLevel.Information))
            {
    _logger.LogInformation(
                    "Initializing Valkey connection pool. Endpoints={Endpoints}, PoolSize={PoolSize}, TLS={Tls}",
                    _safeEndpoints,
                    _poolSize,
                    _valkeyTls);
            }

            var created = new ConnectionMultiplexer[_poolSize];

            try
            {
                for (var slot = 0; slot < created.Length; slot++)
                {
                    created[slot] = CreateConnection(slot);
                }

                Volatile.Write(ref _pool, created);

                var connectedCount = created.Count(static connection => connection.IsConnected);
                if (_logger.IsEnabled(LogLevel.Information))
                {
    _logger.LogInformation(
                        "Valkey connection pool initialized. Connected={ConnectedCount}/{PoolSize}",
                        connectedCount,
                        created.Length);
                }
            }
            catch
            {
                DisposeConnections(created);
                throw;
            }
        }
    }

    /// <summary>
    /// Returns one connection for compatibility with callers that expect a single multiplexer.
    /// Register Redis instrumentation against GetAllConnections() to cover the complete pool.
    /// </summary>
    public ConnectionMultiplexer GetConnection()
    {
        var pool = GetInitializedPool();

        foreach (var connection in pool)
        {
            if (connection.IsConnected)
            {
                return connection;
            }
        }

        // The multiplexer keeps reconnecting in the background. Returning a pool member allows
        // StackExchange.Redis to produce the correct fail-fast connection exception.
        return pool[0];
    }

    /// <summary>
    /// Returns a defensive copy so callers cannot modify the internal pool array.
    /// </summary>
    public ConnectionMultiplexer[] GetAllConnections()
    {
        var pool = GetInitializedPool();
        return (ConnectionMultiplexer[])pool.Clone();
    }

    public async Task AddItemAsync(string userId, string productId, int quantity)
    {
        ValidateAddItemRequest(userId, productId, quantity);

        var stopwatch = Stopwatch.StartNew();

        try
        {
            var db = GetPooledDatabase();

            for (var attempt = 0; attempt < MaximumCartUpdateRetries; attempt++)
            {
                var observedValue = await WaitForRedisAsync(
                        db.HashGetAsync(userId, CartFieldName))
                    .ConfigureAwait(false);

                var cart = ParseCart(observedValue, userId);
                AddQuantity(cart, productId, quantity);
                var updatedBytes = cart.ToByteArray();

                var transaction = db.CreateTransaction();

                transaction.AddCondition(observedValue.IsNull
                    ? Condition.HashNotExists(userId, CartFieldName)
                    : Condition.HashEqual(userId, CartFieldName, observedValue));

                var setTask = transaction.HashSetAsync(userId, CartFieldName, updatedBytes);
                var expireTask = transaction.KeyExpireAsync(userId, CartTtl);

                var committed = await WaitForRedisAsync(transaction.ExecuteAsync())
                    .ConfigureAwait(false);

                if (committed)
                {
                    await WaitForRedisAsync(Task.WhenAll(setTask, expireTask))
                        .ConfigureAwait(false);
                    return;
                }

                CartUpdateConflictCounter.Add(1);
                await DelayAfterConflictAsync(attempt).ConfigureAwait(false);

                // Select another healthy connection after a conflict or topology transition.
                db = GetPooledDatabase();
            }

            throw new RpcException(new Status(
                StatusCode.Aborted,
                "The cart was updated concurrently. Retry the request."));
        }
        catch (RpcException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw MapStorageException(exception, "add an item to the cart");
        }
        finally
        {
            AddItemHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    public async Task EmptyCartAsync(string userId)
    {
        ValidateUserId(userId);

        var stopwatch = Stopwatch.StartNew();

        try
        {
            var db = GetPooledDatabase();
            var emptyCartBytes = new Oteldemo.Cart { UserId = userId }.ToByteArray();

            // MULTI/EXEC makes the value and TTL update atomic.
            var transaction = db.CreateTransaction();
            var setTask = transaction.HashSetAsync(userId, CartFieldName, emptyCartBytes);
            var expireTask = transaction.KeyExpireAsync(userId, CartTtl);

            var committed = await WaitForRedisAsync(transaction.ExecuteAsync())
                .ConfigureAwait(false);

            if (!committed)
            {
                throw new RpcException(new Status(
                    StatusCode.Unavailable,
                    "Cart storage rejected the transaction."));
            }

            await WaitForRedisAsync(Task.WhenAll(setTask, expireTask))
                .ConfigureAwait(false);
        }
        catch (RpcException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw MapStorageException(exception, "empty the cart");
        }
        finally
        {
            EmptyCartHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    public async Task<Oteldemo.Cart> GetCartAsync(string userId)
    {
        ValidateUserId(userId);

        var stopwatch = Stopwatch.StartNew();

        try
        {
            var db = GetPooledDatabase();
            var value = await WaitForRedisAsync(db.HashGetAsync(userId, CartFieldName))
                .ConfigureAwait(false);

            return ParseCart(value, userId);
        }
        catch (RpcException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw MapStorageException(exception, "read the cart");
        }
        finally
        {
            GetCartHistogram.Record(stopwatch.Elapsed.TotalSeconds);
        }
    }

    /// <summary>
    /// Returns true when at least one pool member responds to PING.
    /// The request path also skips connections currently reported as disconnected.
    /// </summary>
    public bool Ping()
    {
        if (Volatile.Read(ref _disposed) != 0)
        {
            return false;
        }

        var pool = Volatile.Read(ref _pool);
        if (pool.Length == 0)
        {
            return false;
        }

        foreach (var connection in pool)
        {
            if (!connection.IsConnected)
            {
                continue;
            }

            try
            {
                var latency = connection.GetDatabase().Ping();
                if (latency >= TimeSpan.Zero)
                {
                    return true;
                }
            }
            catch (RedisException)
            {
                // Try another pool member.
            }
            catch (ObjectDisposedException)
            {
                return false;
            }
        }

        return false;
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
        {
            return;
        }

        ConnectionMultiplexer[] pool;

        lock (_lifecycleLock)
        {
            pool = Interlocked.Exchange(
                ref _pool,
                Array.Empty<ConnectionMultiplexer>());
        }

        DisposeConnections(pool);
        GC.SuppressFinalize(this);
    }

    public ValueTask DisposeAsync()
    {
        // ConnectionMultiplexer.Dispose is sufficient here and keeps compatibility across
        // StackExchange.Redis versions. Disposal only happens during application shutdown.
        Dispose();
        return ValueTask.CompletedTask;
    }

    private ConnectionMultiplexer CreateConnection(int slotIndex)
    {
        var options = CreateConnectionOptions(slotIndex);

        if (_logger.IsEnabled(LogLevel.Debug))
        {
    _logger.LogDebug(
                "Creating Valkey connection. Slot={Slot}, Endpoints={Endpoints}, TLS={Tls}",
                slotIndex,
                _safeEndpoints,
                _valkeyTls);
        }

        var connection = ConnectionMultiplexer.Connect(options);

        connection.InternalError += (_, args) =>
            if (_logger.IsEnabled(LogLevel.Error))
            {
    _logger.LogError(
                    args.Exception,
                    "Valkey internal error. Slot={Slot}",
                    slotIndex);
            }

        connection.ConnectionRestored += (_, args) =>
            if (_logger.IsEnabled(LogLevel.Information))
            {
    _logger.LogInformation(
                    "Valkey connection restored. Slot={Slot}, Endpoint={Endpoint}, Type={ConnectionType}",
                    slotIndex,
                    args.EndPoint,
                    args.ConnectionType);
            }

        connection.ConnectionFailed += (_, args) =>
            if (_logger.IsEnabled(LogLevel.Warning))
            {
    _logger.LogWarning(
                    args.Exception,
                    "Valkey connection failed. Slot={Slot}, Endpoint={Endpoint}, FailureType={FailureType}, Type={ConnectionType}",
                    slotIndex,
                    args.EndPoint,
                    args.FailureType,
                    args.ConnectionType);
            }

        if (connection.IsConnected)
        {
            if (_logger.IsEnabled(LogLevel.Debug))
            {
    _logger.LogDebug("Valkey connection established. Slot={Slot}", slotIndex);
            }
        }
        else
        {
            if (_logger.IsEnabled(LogLevel.Warning))
            {
    _logger.LogWarning(
                    "Valkey connection was created disconnected and will reconnect in the background. Slot={Slot}",
                    slotIndex);
            }
        }

        return connection;
    }

    private ConfigurationOptions CreateConnectionOptions(int slotIndex)
    {
        var options = ConfigurationOptions.Parse(_valkeyAddress);

        if (!string.IsNullOrWhiteSpace(_valkeyToken))
        {
            options.Password = _valkeyToken;
        }

        options.Ssl = _valkeyTls;
        options.AllowAdmin = false;
        options.AbortOnConnectFail = false;
        options.ConnectRetry = RedisConnectRetryCount;
        options.ReconnectRetryPolicy = new ExponentialRetry(1000);
        options.KeepAlive = 60;

        options.ConnectTimeout = 2000;
        options.SyncTimeout = 1000;
        options.AsyncTimeout = (int)RedisOperationTimeout.TotalMilliseconds;

        // Do not retain commands while every connection is unavailable. This bounds memory and
        // avoids replaying stale cart operations after a long outage.
        options.BacklogPolicy = BacklogPolicy.FailFast;

        options.ClientName = $"{Environment.MachineName}-cart-{slotIndex}";

        return options;
    }

    private IDatabase GetPooledDatabase()
    {
        var pool = GetInitializedPool();

        // Convert through ulong so long wraparound can never produce a negative array index.
        var sequence = unchecked((ulong)Interlocked.Increment(ref _poolIndex));
        var startIndex = (int)(sequence % (ulong)pool.Length);

        for (var offset = 0; offset < pool.Length; offset++)
        {
            var index = (startIndex + offset) % pool.Length;
            var connection = pool[index];

            if (connection.IsConnected)
            {
                return connection.GetDatabase();
            }
        }

        // BacklogPolicy.FailFast makes this fail immediately rather than queue indefinitely.
        return pool[startIndex].GetDatabase();
    }

    private ConnectionMultiplexer[] GetInitializedPool()
    {
        ThrowIfDisposed();

        var pool = Volatile.Read(ref _pool);
        if (pool.Length == 0)
        {
            throw new InvalidOperationException(
                "Valkey connection pool is not initialized. Call Initialize() first.");
        }

        return pool;
    }

    private static Oteldemo.Cart ParseCart(RedisValue value, string userId)
    {
        if (value.IsNull)
        {
            return new Oteldemo.Cart { UserId = userId };
        }

        var cart = Oteldemo.Cart.Parser.ParseFrom(value);

        if (string.IsNullOrEmpty(cart.UserId))
        {
            // Repair carts written by the previous EmptyCartAsync implementation.
            cart.UserId = userId;
        }
        else if (!string.Equals(cart.UserId, userId, StringComparison.Ordinal))
        {
            throw new InvalidProtocolBufferException(
                "The stored cart belongs to a different user identifier.");
        }

        return cart;
    }

    private static void AddQuantity(
        Oteldemo.Cart cart,
        string productId,
        int quantity)
    {
        Oteldemo.CartItem? target = null;
        List<Oteldemo.CartItem>? duplicates = null;

        foreach (var item in cart.Items)
        {
            if (!string.Equals(item.ProductId, productId, StringComparison.Ordinal))
            {
                continue;
            }

            if (target is null)
            {
                target = item;
                continue;
            }

            // Repair duplicate product rows left by older or corrupted data.
            target.Quantity = AddWithoutOverflow(target.Quantity, item.Quantity);
            (duplicates ??= new List<Oteldemo.CartItem>()).Add(item);
        }

        if (duplicates is not null)
        {
            foreach (var duplicate in duplicates)
            {
                cart.Items.Remove(duplicate);
            }
        }

        if (target is null)
        {
            cart.Items.Add(new Oteldemo.CartItem
            {
                ProductId = productId,
                Quantity = quantity
            });
            return;
        }

        target.Quantity = AddWithoutOverflow(target.Quantity, quantity);
    }

    private static int AddWithoutOverflow(int current, int increment)
    {
        var result = (long)current + increment;

        if (result > int.MaxValue || result < int.MinValue)
        {
            throw new RpcException(new Status(
                StatusCode.InvalidArgument,
                "The resulting product quantity is outside the supported range."));
        }

        return (int)result;
    }

    private static void ValidateAddItemRequest(
        string userId,
        string productId,
        int quantity)
    {
        ValidateUserId(userId);

        if (string.IsNullOrWhiteSpace(productId))
        {
            throw new RpcException(new Status(
                StatusCode.InvalidArgument,
                "Product ID is required."));
        }

        if (quantity <= 0)
        {
            throw new RpcException(new Status(
                StatusCode.InvalidArgument,
                "Quantity must be greater than zero."));
        }
    }

    private static void ValidateUserId(string userId)
    {
        if (string.IsNullOrWhiteSpace(userId))
        {
            throw new RpcException(new Status(
                StatusCode.InvalidArgument,
                "User ID is required."));
        }
    }

    private RpcException MapStorageException(Exception exception, string operation)
    {
        switch (exception)
        {
            case InvalidProtocolBufferException:
                if (_logger.IsEnabled(LogLevel.Error))
                {
    _logger.LogError(
                        exception,
                        "Stored cart data is invalid while attempting to {Operation}.",
                        operation);
                }
                return new RpcException(new Status(
                    StatusCode.DataLoss,
                    "Stored cart data is invalid."));

            case RedisTimeoutException:
            case TimeoutException:
                if (_logger.IsEnabled(LogLevel.Warning))
                {
    _logger.LogWarning(
                        exception,
                        "Valkey operation timed out while attempting to {Operation}.",
                        operation);
                }
                return new RpcException(new Status(
                    StatusCode.DeadlineExceeded,
                    "Cart storage timed out."));

            case RedisConnectionException:
            case ObjectDisposedException:
                if (_logger.IsEnabled(LogLevel.Warning))
                {
    _logger.LogWarning(
                        exception,
                        "Valkey is unavailable while attempting to {Operation}.",
                        operation);
                }
                return new RpcException(new Status(
                    StatusCode.Unavailable,
                    "Cart storage is unavailable."));

            case RedisException:
                if (_logger.IsEnabled(LogLevel.Error))
                {
    _logger.LogError(
                        exception,
                        "Valkey failed while attempting to {Operation}.",
                        operation);
                }
                return new RpcException(new Status(
                    StatusCode.Unavailable,
                    "Cart storage is unavailable."));

            default:
                if (_logger.IsEnabled(LogLevel.Error))
                {
    _logger.LogError(
                        exception,
                        "Unexpected error while attempting to {Operation}.",
                        operation);
                }
                return new RpcException(new Status(
                    StatusCode.Internal,
                    "An unexpected cart storage error occurred."));
        }
    }

    private static async Task<T> WaitForRedisAsync<T>(Task<T> operation)
    {
        return await operation.WaitAsync(RedisOperationTimeout).ConfigureAwait(false);
    }

    private static async Task WaitForRedisAsync(Task operation)
    {
        await operation.WaitAsync(RedisOperationTimeout).ConfigureAwait(false);
    }

    private static Task DelayAfterConflictAsync(int attempt)
    {
        // Small bounded jitter prevents many callers from immediately colliding again.
        var exponent = Math.Min(attempt, 4);
        var maximumDelayMilliseconds = 1 << exponent;
        var delayMilliseconds = Random.Shared.Next(1, maximumDelayMilliseconds + 2);
        return Task.Delay(delayMilliseconds);
    }

    private static void DisposeConnections(ConnectionMultiplexer[] connections)
    {
        foreach (var connection in connections)
        {
            if (connection is null)
            {
                continue;
            }

            try
            {
                connection.Dispose();
            }
            catch
            {
                // Best effort during partial initialization or process shutdown.
            }
        }
    }

    private void ThrowIfDisposed()
    {
        if (Volatile.Read(ref _disposed) != 0)
        {
            throw new ObjectDisposedException(nameof(ValkeyCartStore));
        }
    }
}