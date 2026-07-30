// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

using System.Threading;
using System.Threading.Tasks;
using cart.services;
using Grpc.Core;
using Xunit;

namespace cart.tests;

public sealed class CartRequestAdmissionTests
{
    [Fact]
    public async Task AcquireAsync_WhenActiveAndQueueAreFull_RejectsImmediately()
    {
        using var admission = new CartRequestAdmission(1, 1);
        using var active = await admission.AcquireAsync(CancellationToken.None);

        var queued = admission.AcquireAsync(CancellationToken.None).AsTask();

        var exception = await Assert.ThrowsAsync<RpcException>(
            async () => await admission.AcquireAsync(CancellationToken.None));

        Assert.Equal(StatusCode.ResourceExhausted, exception.StatusCode);

        active.Dispose();
        using var admittedFromQueue = await queued;
    }

    [Fact]
    public async Task AcquireAsync_WhenQueuedRequestIsCancelled_ReleasesQueueCapacity()
    {
        using var admission = new CartRequestAdmission(1, 1);
        using var active = await admission.AcquireAsync(CancellationToken.None);
        using var cancellation = new CancellationTokenSource();

        var queued = admission.AcquireAsync(cancellation.Token).AsTask();
        cancellation.Cancel();

        var exception = await Assert.ThrowsAsync<RpcException>(async () => await queued);
        Assert.Equal(StatusCode.Cancelled, exception.StatusCode);

        active.Dispose();
        using var next = await admission.AcquireAsync(CancellationToken.None);
    }

    [Fact]
    public async Task AcquireAsync_WhenAlreadyCancelled_DoesNotConsumeCapacity()
    {
        using var admission = new CartRequestAdmission(1, 0);
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();

        var exception = await Assert.ThrowsAsync<RpcException>(
            async () => await admission.AcquireAsync(cancellation.Token));
        Assert.Equal(StatusCode.Cancelled, exception.StatusCode);

        using var admitted = await admission.AcquireAsync(CancellationToken.None);
    }
}
