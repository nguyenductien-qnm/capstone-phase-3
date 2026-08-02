// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/google/uuid"
	"golang.org/x/sync/errgroup"
	"golang.org/x/sync/singleflight"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/log/global"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"

	"github.com/IBM/sarama"
	"github.com/jackc/pgx/v5/pgxpool"
	otelhooks "github.com/open-feature/go-sdk-contrib/hooks/open-telemetry/pkg"
	flagd "github.com/open-feature/go-sdk-contrib/providers/flagd/pkg"
	"github.com/open-feature/go-sdk/openfeature"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"

	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"github.com/open-telemetry/techx-corp/src/checkout/kafka"
	"github.com/open-telemetry/techx-corp/src/checkout/money"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"github.com/open-telemetry/techx-corp/src/checkout/validator"
)

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

var logger *slog.Logger
var tracer trace.Tracer
var resource *sdkresource.Resource
var initResourcesOnce sync.Once

const (
	checkoutDependencyTimeout = 750 * time.Millisecond
	// GetProduct gets longer than the other dependencies because it is the one
	// call measured going over 750ms, and because it is the only one with spare
	// budget. prepOrderItems runs in parallel with the shipping branch, and that
	// branch is the critical path at 3s for the quote plus 750ms to convert it;
	// the product branch was using 1.5s of that, so 2s plus a 750ms conversion
	// still fits underneath it and the 10s checkout deadline does not move.
	//
	// This is a mitigation, not a root cause fix. Under CREATE INDEX
	// CONCURRENTLY on the 743k-row orders table, roughly one GetProduct in
	// twenty exceeded 750ms twice in a row, while 183 consecutive checkouts with
	// no DDL running dropped nothing. RDS was not the constraint (5% CPU, 1.79ms
	// read latency), the row is one of ten in catalog.products and reads warm in
	// 5ms, a fresh connection costs 40-100ms, and product-catalog was throttled
	// 0.08% of its CFS periods. Where the time actually goes is still unknown:
	// the Jaeger query API is not serving, Prometheus only scrapes
	// infrastructure metrics, and no trace index exists in OpenSearch.
	checkoutProductReadTimeout = 2 * time.Second
	// One retry, not more: a second attempt covers a cold-cache read while still
	// leaving the 10s checkout deadline enough room to persist the order.
	checkoutDependencyAttempts = 2
	maxOrderItemConcurrency    = 4
	// Readiness polls faster than the kubelet probe (periodSeconds: 5) so a real
	// outage is noticed within one probe cycle, with a ping timeout under the
	// interval so a stuck ping cannot stall the loop.
	dbReadinessInterval    = 2 * time.Second
	dbReadinessPingTimeout = 1 * time.Second
	// A single failed ping does not pull the pod out of the Service: a switchover
	// blip is meant to be absorbed by the retry path in order_persistence.go, and
	// flapping readiness during one would cost capacity exactly when it is needed.
	dbReadinessFailureThreshold = 2
)

func initResource() *sdkresource.Resource {
	initResourcesOnce.Do(func() {
		extraResources, _ := sdkresource.New(
			context.Background(),
			sdkresource.WithOS(),
			sdkresource.WithProcess(),
			sdkresource.WithContainer(),
			sdkresource.WithHost(),
		)
		resource, _ = sdkresource.Merge(
			sdkresource.Default(),
			extraResources,
		)
	})
	return resource
}

func initTracerProvider() *sdktrace.TracerProvider {
	ctx := context.Background()

	exporter, err := otlptracegrpc.New(ctx)
	if err != nil {
		logger.Error(fmt.Sprintf("new otlp trace grpc exporter failed: %v", err))
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(initResource()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
	return tp
}

func initMeterProvider() *sdkmetric.MeterProvider {
	ctx := context.Background()

	exporter, err := otlpmetricgrpc.New(ctx)
	if err != nil {
		logger.Error(fmt.Sprintf("new otlp metric grpc exporter failed: %v", err))
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter)),
		sdkmetric.WithResource(initResource()),
	)
	otel.SetMeterProvider(mp)
	return mp
}

func initLoggerProvider() *sdklog.LoggerProvider {
	ctx := context.Background()

	logExporter, err := otlploggrpc.New(ctx)
	if err != nil {
		return nil
	}

	loggerProvider := sdklog.NewLoggerProvider(
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
	)
	global.SetLoggerProvider(loggerProvider)

	return loggerProvider
}

type checkout struct {
	productCatalogSvcAddr string
	cartSvcAddr           string
	currencySvcAddr       string
	shippingSvcAddr       string
	emailSvcAddr          string
	paymentSvcAddr        string
	kafkaBrokerSvcAddr    string
	pb.UnimplementedCheckoutServiceServer
	shippingSvcClient       pb.ShippingServiceClient
	productCatalogSvcClient pb.ProductCatalogServiceClient
	cartSvcClient           pb.CartServiceClient
	currencySvcClient       pb.CurrencyServiceClient
	emailSvcClient          pb.EmailServiceClient
	paymentSvcClient        pb.PaymentServiceClient

	productCatalogGroup singleflight.Group
	currencyGroup       singleflight.Group

	kafkaProducer sarama.AsyncProducer
	kafkaTopic string
}

func (cs *checkout) sendToPostProcessor(context context.Context, result *pb.OrderResult) any {
	panic("unimplemented")
}

func main() {
	var port string
	mustMapEnv(&port, "CHECKOUT_PORT")

	tp := initTracerProvider()
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down tracer provider: %v", err))
		}
	}()

	mp := initMeterProvider()
	defer func() {
		if err := mp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down meter provider: %v", err))
		}
	}()

	lp := initLoggerProvider()
	defer func() {
		if err := lp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down logger provider: %v", err))
		}
	}()

	// this *must* be called after the logger provider is initialized
	// otherwise the Sarama producer in kafka/producer.go will not be
	// able to log properly
	logger = otelslog.NewLogger("checkout")
	slog.SetDefault(logger)

	err := runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
	if err != nil {
		logger.Error((err.Error()))
	}

	provider, err := flagd.NewProvider()
	if err != nil {
		logger.Error(fmt.Sprintf("Error creating flagd provider: %v", err))
	}

	openfeature.SetProvider(provider)
	openfeature.AddHooks(otelhooks.NewTracesHook())

	tracer = tp.Tracer("checkout")

	svc := new(checkout)

	mustMapEnv(&svc.shippingSvcAddr, "SHIPPING_ADDR")
	c := mustCreateClient(svc.shippingSvcAddr)
	svc.shippingSvcClient = pb.NewShippingServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.productCatalogSvcAddr, "PRODUCT_CATALOG_ADDR")
	c = mustCreateClient(svc.productCatalogSvcAddr)
	svc.productCatalogSvcClient = pb.NewProductCatalogServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.cartSvcAddr, "CART_ADDR")
	c = mustCreateClient(svc.cartSvcAddr)
	svc.cartSvcClient = pb.NewCartServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.currencySvcAddr, "CURRENCY_ADDR")
	c = mustCreateClient(svc.currencySvcAddr)
	svc.currencySvcClient = pb.NewCurrencyServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.paymentSvcAddr, "PAYMENT_ADDR")
	c = mustCreateClient(svc.paymentSvcAddr)
	svc.paymentSvcClient = pb.NewPaymentServiceClient(c)
	defer c.Close()

	svc.kafkaBrokerSvcAddr = os.Getenv("KAFKA_ADDR")
	if svc.kafkaBrokerSvcAddr != "" {
		brokers := strings.Split(svc.kafkaBrokerSvcAddr, ",")
		for i := range brokers {
			brokers[i] = strings.TrimSpace(brokers[i])
		}
		if producer, err := kafka.CreateKafkaProducer(brokers, logger); err == nil {
			svc.kafkaProducer = producer
		} else {
			logger.Error(fmt.Sprintf("Failed to initialize Kafka producer: %v", err))
		}
	}
	svc.kafkaTopic = os.Getenv("KAFKA_TOPIC")
	if svc.kafkaTopic == "" {
		svc.kafkaTopic = "domain.checkout.orders"
	}

	logger.Info(fmt.Sprintf("service config: %+v", svc))

	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		logger.Error(err.Error())
	}

	var srv = grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)
	pb.RegisterCheckoutServiceServer(srv, svc)

	healthcheck := newCheckoutHealthServer()
	healthpb.RegisterHealthServer(srv, healthcheck)

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	logger.Info(fmt.Sprintf("starting to listen on tcp: %q", lis.Addr().String()))
	go func() {
		if err := srv.Serve(lis); err != nil {
			logger.Error(err.Error())
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	logger.Info("Checkout gRPC server stopped")
}

func newCheckoutHealthServer() *health.Server {
	healthcheck := health.NewServer()
	// Kafka post-processing is degraded independently through publisher metrics
	// and logs. It must not remove the revenue path from service endpoints.
	healthcheck.SetServingStatus("liveness", healthpb.HealthCheckResponse_SERVING)
	// Checkout is not ready to accept revenue traffic until durable persistence
	// answers. Without DATABASE_URL nothing ever flips this; with it,
	// watchDatabaseReadiness does. The "" entry keeps probes that omit the
	// service name in step with "readiness".
	healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_NOT_SERVING)
	healthcheck.SetServingStatus("", healthpb.HealthCheckResponse_NOT_SERVING)
	return healthcheck
}

// watchDatabaseReadiness keeps readiness in step with what the pool can actually
// reach. Deciding once at startup meant a pod booted during a switchover stayed
// NOT_SERVING until the startup probe killed it 150s later, and a pod that was
// already running kept reporting ready long after the database stopped answering.
func watchDatabaseReadiness(ctx context.Context, pool *pgxpool.Pool, healthcheck *health.Server) {
	ticker := time.NewTicker(dbReadinessInterval)
	defer ticker.Stop()

	// Shutdown reports NOT_SERVING before the preStop drain so probes and the
	// Service stop sending work to a pod that is on its way out.
	defer setCheckoutReadiness(healthcheck, healthpb.HealthCheckResponse_NOT_SERVING)

	gate := newReadinessGate()
	for {
		pingCtx, pingCancel := context.WithTimeout(ctx, dbReadinessPingTimeout)
		pingErr := pool.Ping(pingCtx)
		pingCancel()

		if status, changed := gate.observe(pingErr == nil); changed {
			if pingErr != nil {
				logger.Warn(fmt.Sprintf("database unreachable, checkout is not ready: %v", pingErr))
			} else {
				logger.Info("database reachable, checkout is ready")
			}
			setCheckoutReadiness(healthcheck, status)
		}

		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func setCheckoutReadiness(healthcheck *health.Server, status healthpb.HealthCheckResponse_ServingStatus) {
	healthcheck.SetServingStatus("readiness", status)
	// Probes that omit the service name must see the same answer.
	healthcheck.SetServingStatus("", status)
}

// readinessGate turns a stream of ping results into readiness transitions. It
// recovers on the first success but needs dbReadinessFailureThreshold failures
// in a row before it withdraws the pod, so one blip does not flap the Service.
type readinessGate struct {
	reported healthpb.HealthCheckResponse_ServingStatus
	failures int
}

func newReadinessGate() *readinessGate {
	return &readinessGate{reported: healthpb.HealthCheckResponse_NOT_SERVING}
}

func (g *readinessGate) observe(pingOK bool) (healthpb.HealthCheckResponse_ServingStatus, bool) {
	if pingOK {
		g.failures = 0
		return g.report(healthpb.HealthCheckResponse_SERVING)
	}

	g.failures++
	if g.failures < dbReadinessFailureThreshold {
		return g.reported, false
	}
	return g.report(healthpb.HealthCheckResponse_NOT_SERVING)
}

func (g *readinessGate) report(status healthpb.HealthCheckResponse_ServingStatus) (healthpb.HealthCheckResponse_ServingStatus, bool) {
	if g.reported == status {
		return status, false
	}
	g.reported = status
	return status, true
}

func mustMapEnv(target *string, envKey string) {
	v := os.Getenv(envKey)
	if v == "" {
		panic(fmt.Sprintf("environment variable %q not set", envKey))
	}
	*target = v
}

func (cs *checkout) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (cs *checkout) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

func (cs *checkout) PlaceOrder(ctx context.Context, req *pb.PlaceOrderRequest) (*pb.PlaceOrderResponse, error) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("app.user.id", req.UserId),
		attribute.String("app.user.currency", req.UserCurrency),
	)
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "[PlaceOrder]",
		slog.String("user_id", req.UserId),
		slog.String("user_currency", req.UserCurrency),
	)

	var err error
	defer func() {
		if err != nil {
			span.AddEvent("error", trace.WithAttributes(semconv.ExceptionMessageKey.String(err.Error())))
		}
	}()

	span.AddEvent("prepared")

	orderId, err := uuid.NewUUID()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to generate order uuid")
	}
	
	prep, err := cs.prepareOrderItemsAndShippingQuoteFromCart(ctx, req.UserId, req.UserCurrency)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	
	// Calculate total order cost 
	total := &pb.Money{CurrencyCode: req.UserCurrency, Units: 0, Nanos: 0}
	for _, it := range prep.orderItems {
		multPrice := money.Multiply(it.Cost, uint32(it.GetItem().GetQuantity()))
		total = money.Must(money.Sum(total, multPrice))
	} 
	
	// In-memory validation
	if err := validator.ValidateCreditCard(req.CreditCard); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid payment information: %v", err)
	}
	if err := validator.ValidateAddress(req.Address); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid shipping address: %v", err)
	}

	cardNum := req.CreditCard.GetCreditCardNumber()
	lastFour := cardLastFour(cardNum)
	cardType := validator.DetectCardType(cardNum)
	// Generate single-use payment token
	paymentToken := fmt.Sprintf("tok_%s_%s", cardType, strings.ReplaceAll(uuid.New().String(), "-", ""))

	// 36.75$
	// {
	//   "currencyCode": "USD",
	//   "units": 36,
	//   "nanos": 750000000
	// }
		
	paymentSummary := &pb.PaymentSummary{
		PaymentToken: paymentToken,
		CardLastFour: lastFour,
		CardType: cardType,
		TotalAmount: total,
	}

	// 2. Construct complete OrderResult with all downstream fields
	orderResult := &pb.OrderResult{
		OrderId: orderId.String(),
		TotalOrderCost: total,
		ShippingAddress:    req.Address,
		Items:              prep.orderItems, // Pre-calculated order items array
	}

	totalPriceFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", total.GetUnits(), total.GetNanos()/1000000000), 64)

	span.SetAttributes(
		attribute.String("app.order.id", orderResult.GetOrderId()),
		attribute.Float64("app.order.amount", totalPriceFloat),
		attribute.Int("app.order.items.count", len(prep.orderItems)),
	)
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "order placed (asynchronous)",
		slog.String("app.order.id", orderResult.GetOrderId()),
		slog.Float64("app.order.amount", totalPriceFloat),
		slog.Int("app.order.items.count", len(prep.orderItems)),
	)

	err = kafka.PublishOrderEvent(
		cs.kafkaProducer,
		cs.kafkaTopic,
		req.UserId,
		orderId.String(),
		orderResult,
		paymentSummary,
	)
	if err != nil {
		logger.Error(fmt.Sprintf("Failed to publish to MSK: %v", err))
	}

	resp := &pb.PlaceOrderResponse{Order: orderResult}
	return resp, nil
}

func idempotencyKeyFromContext(ctx context.Context) (string, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return "", fmt.Errorf("%s metadata is required", idempotencyMetadataKey)
	}
	values := md.Get(idempotencyMetadataKey)
	if len(values) != 1 || strings.TrimSpace(values[0]) == "" {
		if len(values) > 1 {
			return "", fmt.Errorf("%s metadata must contain exactly one value", idempotencyMetadataKey)
		}
		return "", fmt.Errorf("%s metadata is required", idempotencyMetadataKey)
	}
	key := strings.TrimSpace(values[0])
	if err := validateIdempotencyKey(key); err != nil {
		return "", err
	}
	return key, nil
}


type orderPrep struct {
	orderItems            []*pb.OrderItem
	cartItems             []*pb.CartItem
	shippingCostLocalized *pb.Money
}

// In checkout service
//  1. getUserCart:
//     - Calls Cart service using userID to retrieve the current list of items in the user's cart
//  2. prepOrderItems:
//     - For each item in the cart, calls the Product Catalog service to fetch the product's base price (USD).
//     - It then calls the Currency service to convert that base price into the user's local currency (userCurrency).
func (cs *checkout) prepareOrderItemsAndShippingQuoteFromCart(ctx context.Context, userID, userCurrency string) (orderPrep, error) {

	ctx, span := tracer.Start(ctx, "prepareOrderItemsAndShippingQuoteFromCart")
	defer span.End()

	var out orderPrep
	cartItems, err := cs.getUserCart(ctx, userID)
	if err != nil {
		return out, fmt.Errorf("cart failure: %+v", err)
	}

	group, groupCtx := errgroup.WithContext(ctx)
	var orderItems []*pb.OrderItem
	
	group.Go(func() error {
		var prepErr error
		orderItems, prepErr = cs.prepOrderItems(groupCtx, cartItems, userCurrency)
		if prepErr != nil {
			return fmt.Errorf("failed to prepare order: %+v", prepErr)
		}
		return nil
	})

	// group.Go(func() error {
	// 	shippingUSD, quoteErr := cs.quoteShipping(groupCtx, address, cartItems)
	// 	if quoteErr != nil {
	// 		return fmt.Errorf("shipping quote failure: %+v", quoteErr)
	// 	}

	// 	var conversionErr error
	// 	shippingPrice, conversionErr = cs.convertCurrency(groupCtx, shippingUSD, userCurrency)
	// 	if conversionErr != nil {
	// 		return fmt.Errorf("failed to convert shipping cost to currency: %+v", conversionErr)
	// 	}
	// 	return nil
	// })

	if err := group.Wait(); err != nil {
		return out, err
	}

	// out.shippingCostLocalized = shippingPrice
	out.cartItems = cartItems
	out.orderItems = orderItems

	var totalCart int32
	for _, ci := range cartItems {
		totalCart += ci.Quantity
	}
	// shippingCostFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", shippingPrice.GetUnits(), shippingPrice.GetNanos()/1000000000), 64)

	span.SetAttributes(
		// attribute.Float64("app.shipping.amount", shippingCostFloat),
		attribute.Int("app.cart.items.count", int(totalCart)),
		attribute.Int("app.order.items.count", len(orderItems)),
	)
	return out, nil
}

func mustCreateClient(svcAddr string) *grpc.ClientConn {
	c, err := grpc.NewClient(svcAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithStatsHandler(otelgrpc.NewClientHandler()),
	)
	if err != nil {
		logger.Error(fmt.Sprintf("could not connect to %s service, err: %+v", svcAddr, err))
	}

	return c
}

func (cs *checkout) quoteShipping(ctx context.Context, address *pb.Address, items []*pb.CartItem) (*pb.Money, error) {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	quotePayload, err := json.Marshal(map[string]interface{}{
		"address": address,
		"items":   items,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to marshal ship order request: %+v", err)
	}

	resp, err := otelhttp.Post(ctx, cs.shippingSvcAddr+"/get-quote", "application/json", bytes.NewBuffer(quotePayload))
	if err != nil {
		return nil, fmt.Errorf("failed POST to shipping service: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed POST to email service: expected 200, got %d", resp.StatusCode)
	}

	shippingQuoteBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read shipping quote response: %+v", err)
	}

	var quoteResp struct {
		CostUsd *pb.Money `json:"cost_usd"`
	}
	if err := json.Unmarshal(shippingQuoteBytes, &quoteResp); err != nil {
		return nil, fmt.Errorf("failed to unmarshal shipping quote: %+v", err)
	}
	if quoteResp.CostUsd == nil {
		return nil, fmt.Errorf("shipping quote missing cost_usd field")
	}

	return quoteResp.CostUsd, nil
}

// readDependency runs a read-only dependency call, retrying a transient failure
// once. An online index build or a failover evicts the shared buffer cache, and
// a single cold read can then outlast checkoutDependencyTimeout even though the
// dependency itself is healthy — that is one dropped order for a blip that a
// second attempt serves in milliseconds.
//
// Widening checkoutDependencyTimeout instead is not affordable: the worst-case
// serial chain (cart, shipping quote plus its conversion, charge, empty cart)
// already spends about 6s of the 10s the frontend allows, and the order still
// has to be persisted after that.
//
// Only reads go through here. Charge and EmptyCart change state and must not be
// repeated. The per-attempt context is derived from ctx, so the caller's
// deadline still caps the total, and a retry can never overrun the budget.
func readDependency[T any](ctx context.Context, perAttempt time.Duration, call func(context.Context) (T, error)) (T, error) {
	var zero T
	var err error
	for attempt := 1; attempt <= checkoutDependencyAttempts; attempt++ {
		var value T
		rpcCtx, cancel := context.WithTimeout(ctx, perAttempt)
		value, err = call(rpcCtx)
		cancel()
		if err == nil {
			return value, nil
		}
		// A cancelled parent means the order is already failing elsewhere, or the
		// caller gave up; retrying would only burn budget that is no longer ours.
		if ctx.Err() != nil || !isRetryableDependencyError(err) {
			return zero, err
		}
	}
	return zero, err
}

func isRetryableDependencyError(err error) bool {
	switch status.Code(err) {
	case codes.DeadlineExceeded, codes.Unavailable, codes.ResourceExhausted, codes.Aborted:
		return true
	default:
		return false
	}
}

func (cs *checkout) getUserCart(ctx context.Context, userID string) ([]*pb.CartItem, error) {
	cart, err := readDependency(ctx, checkoutDependencyTimeout, func(rpcCtx context.Context) (*pb.Cart, error) {
		return cs.cartSvcClient.GetCart(rpcCtx, &pb.GetCartRequest{UserId: userID})
	})
	if err != nil {
		return nil, fmt.Errorf("failed to get user cart during checkout: %+v", err)
	}
	return cart.GetItems(), nil
}

func (cs *checkout) emptyUserCart(ctx context.Context, userID string) error {
	rpcCtx, cancel := context.WithTimeout(ctx, checkoutDependencyTimeout)
	defer cancel()
	if _, err := cs.cartSvcClient.EmptyCart(rpcCtx, &pb.EmptyCartRequest{UserId: userID}); err != nil {
		return fmt.Errorf("failed to empty user cart during checkout: %+v", err)
	}
	return nil
}

func (cs *checkout) prepOrderItems(ctx context.Context, items []*pb.CartItem, userCurrency string) ([]*pb.OrderItem, error) {
	out := make([]*pb.OrderItem, len(items))
	group, groupCtx := errgroup.WithContext(ctx)
	group.SetLimit(maxOrderItemConcurrency)

	for i, item := range items {
		itemIndex, cartItem := i, item
		group.Go(func() error {
			v, err, _ := cs.productCatalogGroup.Do(cartItem.GetProductId(), func() (interface{}, error) {
				return readDependency(groupCtx, checkoutProductReadTimeout, func(rpcCtx context.Context) (*pb.Product, error) {
					return cs.productCatalogSvcClient.GetProduct(rpcCtx, &pb.GetProductRequest{Id: cartItem.GetProductId()})
				})
			})
			if err != nil {
				return fmt.Errorf("failed to get product #%q: %w", cartItem.GetProductId(), err)
			}
			product := v.(*pb.Product)
			price, err := cs.convertCurrency(groupCtx, product.GetPriceUsd(), userCurrency)
			if err != nil {
				return fmt.Errorf("failed to convert price of %q to %s: %w", cartItem.GetProductId(), userCurrency, err)
			}
			out[itemIndex] = &pb.OrderItem{
				Item: cartItem,
				Cost: price,
			}
			return nil
		})
	}
	if err := group.Wait(); err != nil {
		return nil, err
	}
	return out, nil
}

func (cs *checkout) convertCurrency(ctx context.Context, from *pb.Money, toCurrency string) (*pb.Money, error) {
	key := fmt.Sprintf("%s:%d:%d:%s", from.GetCurrencyCode(), from.GetUnits(), from.GetNanos(), toCurrency)
	v, err, _ := cs.currencyGroup.Do(key, func() (interface{}, error) {
		return readDependency(ctx, checkoutDependencyTimeout, func(rpcCtx context.Context) (*pb.Money, error) {
			return cs.currencySvcClient.Convert(rpcCtx, &pb.CurrencyConversionRequest{
				From:   from,
				ToCode: toCurrency})
		})
	})
	if err != nil {
		return nil, fmt.Errorf("failed to convert currency: %+v", err)
	}
	return v.(*pb.Money), nil
}

func (cs *checkout) chargeCard(ctx context.Context, amount *pb.Money, paymentInfo *pb.CreditCardInfo) (string, error) {
	paymentService := cs.paymentSvcClient
	if cs.isFeatureFlagEnabled(ctx, "paymentUnreachable") {
		badAddress := "badAddress:50051"
		c := mustCreateClient(badAddress)
		paymentService = pb.NewPaymentServiceClient(c)
	}

	rpcCtx, cancel := context.WithTimeout(ctx, checkoutDependencyTimeout)
	defer cancel()
	paymentResp, err := paymentService.Charge(rpcCtx, &pb.ChargeRequest{
		Amount:     amount,
		CreditCard: paymentInfo})
	if err != nil {
		return "", fmt.Errorf("could not charge the card: %+v", err)
	}
	return paymentResp.GetTransactionId(), nil
}

func (cs *checkout) validatePayment(ctx context.Context, paymentInfo *pb.CreditCardInfo) error {
	paymentService := cs.paymentSvcClient
	if cs.isFeatureFlagEnabled(ctx, "paymentUnreachable") {
		badAddress := "badAddress:50051"
		c := mustCreateClient(badAddress)
		paymentService = pb.NewPaymentServiceClient(c)
	}

	resp, err := paymentService.Validate(ctx, &pb.ValidatePaymentRequest{
		CreditCard: paymentInfo,
	})
	if err != nil {
		return fmt.Errorf("could not reach payment validation: %v", err)
	}
	if !resp.GetValid() {
		return fmt.Errorf("payment validation failed: %s", resp.GetMessage())
	}
	return nil
}

func (cs *checkout) validateAddress(ctx context.Context, address *pb.Address) error {
	valPayload, err := json.Marshal(map[string]interface{}{
		"address": address,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal address validation request: %+v", err)
	}

	resp, err := otelhttp.Post(ctx, cs.shippingSvcAddr+"/validate-address", "application/json", bytes.NewBuffer(valPayload))
	if err != nil {
		return fmt.Errorf("failed POST to shipping service for validation: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed address validation: expected 200, got %d", resp.StatusCode)
	}

	valRespBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read address validation response: %+v", err)
	}

	var valResp struct {
		Valid   bool   `json:"valid"`
		Message string `json:"message"`
	}
	if err := json.Unmarshal(valRespBytes, &valResp); err != nil {
		return fmt.Errorf("failed to unmarshal address validation response: %+v", err)
	}

	if !valResp.Valid {
		return fmt.Errorf("address validation failed: %s", valResp.Message)
	}
	return nil
}

func (cs *checkout) sendOrderConfirmation(ctx context.Context, email string, order *pb.OrderResult) error {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	emailPayload, err := json.Marshal(map[string]interface{}{
		"email": email,
		"order": order,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal order to JSON: %+v", err)
	}

	resp, err := otelhttp.Post(ctx, cs.emailSvcAddr+"/send_order_confirmation", "application/json", bytes.NewBuffer(emailPayload))
	if err != nil {
		return fmt.Errorf("failed POST to email service: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed POST to email service: expected 200, got %d", resp.StatusCode)
	}

	return err
}

func (cs *checkout) shipOrder(ctx context.Context, address *pb.Address, items []*pb.CartItem) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	shipPayload, err := json.Marshal(map[string]interface{}{
		"address": address,
		"items":   items,
	})
	if err != nil {
		return "", fmt.Errorf("failed to marshal ship order request: %+v", err)
	}

	resp, err := otelhttp.Post(ctx, cs.shippingSvcAddr+"/ship-order", "application/json", bytes.NewBuffer(shipPayload))
	if err != nil {
		return "", fmt.Errorf("failed POST to shipping service: %+v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("failed POST to email service: expected 200, got %d", resp.StatusCode)
	}

	trackingRespBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read ship order response: %+v", err)
	}

	var shipResp struct {
		TrackingID string `json:"tracking_id"`
	}
	if err := json.Unmarshal(trackingRespBytes, &shipResp); err != nil {
		return "", fmt.Errorf("failed to unmarshal ship order response: %+v", err)
	}
	if shipResp.TrackingID == "" {
		return "", fmt.Errorf("ship order response missing tracking_id field")
	}

	return shipResp.TrackingID, nil
}

func (cs *checkout) isFeatureFlagEnabled(ctx context.Context, featureFlagName string) bool {
	client := openfeature.NewClient("checkout")

	// Default value is set to false, but you could also make this a parameter.
	featureEnabled, _ := client.BooleanValue(
		ctx,
		featureFlagName,
		false,
		openfeature.EvaluationContext{},
	)

	return featureEnabled
}

func (cs *checkout) getIntFeatureFlag(ctx context.Context, featureFlagName string) int {
	client := openfeature.NewClient("checkout")

	// Default value is set to 0, but you could also make this a parameter.
	featureFlagValue, _ := client.IntValue(
		ctx,
		featureFlagName,
		0,
		openfeature.EvaluationContext{},
	)

	return int(featureFlagValue)
}
