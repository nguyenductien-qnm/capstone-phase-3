// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System;
using System.Diagnostics.Metrics;
using System.Threading;
using System.Threading.Tasks;
using Grpc.Core;

namespace cart.services;

/// <summary>
/// Bounds both active cart RPCs and the admission queue. Requests beyond the
/// configured capacity fail immediately instead of increasing process and
/// Redis client backlog without limit.
/// </summary>
public sealed class CartRequestAdmission : IDisposable
{
    public const int DefaultMaxConcurrentRequests = 64;
    public const int DefaultMaxQueuedRequests = 64;

    private static readonly Meter CartMeter = new("OpenTelemetry.Demo.Cart");
    private static readonly UpDownCounter<long> ActiveRequests = CartMeter.CreateUpDownCounter<long>(
        "app.cart.admission.active_requests",
        unit: "request");
    private static readonly UpDownCounter<long> QueuedRequests = CartMeter.CreateUpDownCounter<long>(
        "app.cart.admission.queued_requests",
        unit: "request");
    private static readonly Counter<long> RejectedRequests = CartMeter.CreateCounter<long>(
        "app.cart.admission.rejected_requests",
        unit: "request");

    private readonly int _maximumAdmittedRequests;
    private readonly SemaphoreSlim _concurrency;
    private int _admittedRequests;
    private int _disposed;

    public CartRequestAdmission(
        int maxConcurrentRequests = DefaultMaxConcurrentRequests,
        int maxQueuedRequests = DefaultMaxQueuedRequests)
    {
        if (maxConcurrentRequests <= 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(maxConcurrentRequests),
                maxConcurrentRequests,
                "Maximum concurrent requests must be greater than zero.");
        }

        if (maxQueuedRequests < 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(maxQueuedRequests),
                maxQueuedRequests,
                "Maximum queued requests cannot be negative.");
        }

        _maximumAdmittedRequests = checked(maxConcurrentRequests + maxQueuedRequests);
        _concurrency = new SemaphoreSlim(maxConcurrentRequests, maxConcurrentRequests);
    }

    public async ValueTask<IDisposable> AcquireAsync(CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(Volatile.Read(ref _disposed) != 0, this);
        if (cancellationToken.IsCancellationRequested)
        {
            throw new RpcException(new Status(
                StatusCode.Cancelled,
                "Cart request was cancelled before admission."));
        }

        var admitted = Interlocked.Increment(ref _admittedRequests);
        if (admitted > _maximumAdmittedRequests)
        {
            Interlocked.Decrement(ref _admittedRequests);
            RejectedRequests.Add(1);
            throw new RpcException(new Status(
                StatusCode.ResourceExhausted,
                "Cart service capacity is temporarily exhausted."));
        }

        var queued = !_concurrency.Wait(0, CancellationToken.None);
        if (!queued)
        {
            ActiveRequests.Add(1);
            return new AdmissionLease(this);
        }

        QueuedRequests.Add(1);
        try
        {
            await _concurrency.WaitAsync(cancellationToken).ConfigureAwait(false);
            QueuedRequests.Add(-1);
            ActiveRequests.Add(1);
            return new AdmissionLease(this);
        }
        catch (OperationCanceledException)
        {
            QueuedRequests.Add(-1);
            Interlocked.Decrement(ref _admittedRequests);
            throw new RpcException(new Status(
                StatusCode.Cancelled,
                "Cart request was cancelled while awaiting capacity."));
        }
        catch
        {
            QueuedRequests.Add(-1);
            Interlocked.Decrement(ref _admittedRequests);
            throw;
        }
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
        {
            return;
        }

        _concurrency.Dispose();
    }

    private void Release()
    {
        ActiveRequests.Add(-1);
        Interlocked.Decrement(ref _admittedRequests);
        _concurrency.Release();
    }

    private sealed class AdmissionLease : IDisposable
    {
        private CartRequestAdmission _owner;

        public AdmissionLease(CartRequestAdmission owner)
        {
            _owner = owner;
        }

        public void Dispose()
        {
            var owner = Interlocked.Exchange(ref _owner, null);
            owner?.Release();
        }
    }
}
