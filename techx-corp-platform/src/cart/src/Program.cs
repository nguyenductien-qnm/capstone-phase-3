// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
using System;

using Grpc.Health.V1;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using System.Threading.Tasks;
using System.Threading;

using Grpc.Core;

using cart.cartstore;
using cart.services;
using cart.healthcheck;

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Logging;
using OpenTelemetry.Instrumentation.StackExchangeRedis;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using OpenFeature;
using OpenFeature.Hooks;
using OpenFeature.Contrib.Providers.Flagd;

var builder = WebApplication.CreateBuilder(args);
string valkeyAddress = builder.Configuration["VALKEY_ADDR"];
if (string.IsNullOrEmpty(valkeyAddress))
{
    Console.WriteLine("VALKEY_ADDR environment variable is required.");
    Environment.Exit(1);
}

builder.Logging
    .AddOpenTelemetry(options => options.AddOtlpExporter())
    .AddConsole();

builder.Services.AddSingleton<ICartStore>(x =>
{
    string valkeyToken = builder.Configuration["VALKEY_AUTH_TOKEN"];
    bool valkeyTls = builder.Configuration["VALKEY_TLS"]?.ToLower() == "true";
    var store = new ValkeyCartStore(x.GetRequiredService<ILogger<ValkeyCartStore>>(), valkeyAddress, valkeyToken, valkeyTls);
    store.Initialize();
    return store;
});

builder.Services.AddOpenFeature(openFeatureBuilder =>
{
    openFeatureBuilder
        .AddProvider(_ => new FlagdProvider())
        .AddHook<MetricsHook>()
        .AddHook<TraceEnricherHook>();
});

builder.Services.AddSingleton(x =>
    new CartService(
        x.GetRequiredService<ICartStore>(),
        new ValkeyCartStore(x.GetRequiredService<ILogger<ValkeyCartStore>>(), "badhost:1234"),
        x.GetRequiredService<IFeatureClient>()
));


Action<ResourceBuilder> appResourceBuilder =
    resource => resource
        .AddService(builder.Environment.ApplicationName)
        .AddContainerDetector()
        .AddHostDetector();

builder.Services.AddOpenTelemetry()
    .ConfigureResource(appResourceBuilder)
    .WithTracing(tracerBuilder => tracerBuilder
        .AddSource("OpenTelemetry.Demo.Cart")
        .AddRedisInstrumentation(
            options => options.SetVerboseDatabaseStatements = true)
        .AddAspNetCoreInstrumentation()
        .AddGrpcClientInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())
    .WithMetrics(meterBuilder => meterBuilder
        .AddMeter("OpenTelemetry.Demo.Cart")
        .AddMeter("OpenFeature")
        .AddProcessInstrumentation()
        .AddRuntimeInstrumentation()
        .AddAspNetCoreInstrumentation()
        .SetExemplarFilter(ExemplarFilterType.TraceBased)
        .AddOtlpExporter());
builder.Services.AddGrpc();
builder.Services.AddSingleton<readinessCheck>();
// CDO-80 (Option C): tách liveness khỏi readiness.
// - "liveness"  : luôn Healthy khi process sống → Valkey giật KHÔNG restart pod.
// - "readiness" : phản ánh dependency (dùng lại readinessCheck) → giật thì kéo khỏi LB, không restart.
// Giữ "oteldemo.CartService" cho tương thích ngược.
builder.Services.AddGrpcHealthChecks()
    .AddCheck<readinessCheck>("oteldemo.CartService")
    .AddCheck("liveness", () => HealthCheckResult.Healthy())
    .AddCheck<readinessCheck>("readiness");

builder.Services.AddSingleton<HealthServiceImpl>();

var app = builder.Build();

// Register OTel Redis instrumentation for all connections in the pool.
// This gives distributed tracing visibility into every socket in the pool.
var ValkeyCartStore = (ValkeyCartStore)app.Services.GetRequiredService<ICartStore>();
var redisInstrumentation = app.Services.GetRequiredService<StackExchangeRedisInstrumentation>();
foreach (var conn in ValkeyCartStore.GetAllConnections())
{
    redisInstrumentation.AddConnection(conn);
}

app.MapGrpcService<CartService>();
app.MapGrpcService<HealthServiceImpl>();

app.MapGet("/", async context =>
{
    await context.Response.WriteAsync("Communication with gRPC endpoints must be made through a gRPC client. To learn how to create a client, visit: https://go.microsoft.com/fwlink/?linkid=2086909");
});

app.Run();


