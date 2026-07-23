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

	"golang.org/x/sync/errgroup"
	"golang.org/x/sync/singleflight"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/log/global"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"

	"github.com/IBM/sarama"
	"github.com/google/uuid"
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
	"google.golang.org/grpc/status"
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
	maxOrderItemConcurrency  = 4
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
	orderEventPublisher     OrderEventPublisher
	shippingSvcClient       pb.ShippingServiceClient
	productCatalogSvcClient pb.ProductCatalogServiceClient
	cartSvcClient           pb.CartServiceClient
	currencySvcClient       pb.CurrencyServiceClient
	emailSvcClient          pb.EmailServiceClient
	paymentSvcClient        pb.PaymentServiceClient
	
	dbPool                  *pgxpool.Pool
	productCatalogGroup     singleflight.Group
	currencyGroup           singleflight.Group
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

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL != "" {
		poolConfig, err := pgxpool.ParseConfig(dbURL)
		if err != nil {
			logger.Error(fmt.Sprintf("Unable to parse DATABASE_URL: %v", err))
		} else {
			dbPool, err := pgxpool.NewWithConfig(context.Background(), poolConfig)
			if err != nil {
				logger.Error(fmt.Sprintf("Unable to create connection pool: %v", err))
			} else {
				svc.dbPool = dbPool
				defer dbPool.Close()
			}
		}
	} else {
		logger.Warn("DATABASE_URL not set, DB features disabled")
	}

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

	mustMapEnv(&svc.emailSvcAddr, "EMAIL_ADDR")
	c = mustCreateClient(svc.emailSvcAddr)
	svc.emailSvcClient = pb.NewEmailServiceClient(c)
	defer c.Close()

	mustMapEnv(&svc.paymentSvcAddr, "PAYMENT_ADDR")
	c = mustCreateClient(svc.paymentSvcAddr)
	svc.paymentSvcClient = pb.NewPaymentServiceClient(c)
	defer c.Close()

	svc.kafkaBrokerSvcAddr = os.Getenv("KAFKA_ADDR")

	if svc.kafkaBrokerSvcAddr != "" {
		brokers := strings.Split(svc.kafkaBrokerSvcAddr, ",")
		producer, producerErr := kafka.CreateKafkaProducer(brokers, logger)
		svc.orderEventPublisher = newKafkaOrderEventPublisher(producer, kafkaPublishTimeout())
		if producerErr != nil {
			logger.Error(producerErr.Error())
		}
		defer func() {
			if closeErr := svc.orderEventPublisher.Close(); closeErr != nil {
				logger.Error(fmt.Sprintf("failed to close Kafka publisher: %v", closeErr))
			}
		}()
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
	healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_SERVING)
	// Keep compatibility with probes that omit the service name.
	healthcheck.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)
	return healthcheck
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

	// Makes a synchronous HTTP request to the Shipping Service (POST /validate-address) to verify all shipping fields are present
	if err := cs.validateAddress(ctx, req.Address); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid shipping address: %v", err)
	}
	// Makes a synchronous gRPC call to the Payment Service (Validate) to ensure the credit card is a valid Visa/Mastercard, hasn't expired, and passes standard format checks
	if err := cs.validatePayment(ctx, req.CreditCard); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid payment information: %v", err)
	}
	// If any of these validations fail, the service immediately throws an error back to the frontend, stopping the entire process 

	
	orderID, err := uuid.NewUUID()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to generate order uuid")
	}

	prep, err := cs.prepareOrderItemsAndShippingQuoteFromCart(ctx, req.UserId, req.UserCurrency, req.Address)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	// 36.75$
	// { 
    //   "currencyCode": "USD",
    //   "units": 36,
    //   "nanos": 750000000
    // }
	total := &pb.Money{CurrencyCode: req.UserCurrency, Units: 0, Nanos: 0}
	total = money.Must(money.Sum(total, prep.shippingCostLocalized))
	for _, it := range prep.orderItems {
		multPrice := money.Multiply(it.Cost, uint32(it.GetItem().GetQuantity()))
		total = money.Must(money.Sum(total, multPrice))
	}

	span.AddEvent("prepared")

	if cs.dbPool == nil {
		err := fmt.Errorf("database pool is not initialized")
		logger.Error(err.Error())
		return nil, status.Errorf(codes.Internal, "%v", err)
	}

	tx, err := cs.dbPool.Begin(ctx)
	if err != nil {
		logger.Error(fmt.Sprintf("failed to begin transaction: %v", err))
		return nil, status.Errorf(codes.Internal, "failed to begin transaction: %v", err)
	}

	// req
	// {
	//     "user_id": "usr-12345-abcde",
	//     "user_currency": "USD",
	//     "email": "customer@example.com",
	//     "address": {
	//       "street_address": "1600 Amphitheatre Parkway",
	//       "city": "Mountain View",
	//       "state": "CA",
	//       "country": "USA",
	//       "zip_code": "94043"
	//     },
	//     "credit_card": {
	//       "credit_card_number": "4111222233334444",
	//       "credit_card_cvv": 123,
	//       "credit_card_expiration_year": 2028,
	//       "credit_card_expiration_month": 10
	//     }
	// }
	orderMetadata := struct {
		*pb.PlaceOrderRequest
		OrderItems            []*pb.OrderItem `json:"orderItems"`
		CartItems             []*pb.CartItem  `json:"cartItems"`
		ShippingCostLocalized *pb.Money       `json:"shippingCostLocalized"`
		Total                 *pb.Money       `json:"total"`
	}{
		PlaceOrderRequest:     req,
		OrderItems:            prep.orderItems,
		CartItems:             prep.cartItems,
		ShippingCostLocalized: prep.shippingCostLocalized,
		Total:                 total,
	}
	// add these fields into req
	// {                                                                                                                                                                                                
	//     "orderItems": [                                                                                                                                                                                
	//       {                                                                                                                                                                                            
	//         "item": {                                                                                                                                                                                  
	//           "productId": "OLJCESPC7Z",                                                                                                                                                               
	//           "quantity": 2                                                                                                                                                                            
	//         },                                                                                                                                                                                         
	//         "cost": {                                                                                                                                                                                  
	//           "currencyCode": "EUR",                                                                                                                                                                   
	//           "units": 15,                                                                                                                                                                             
	//           "nanos": 500000000                                                                                                                                                                       
	//         }                                                                                                                                                                                          
	//       }                                                                                                                                                                                            
	//     ],                                                                                                                                                                                             
	//     "cartItems": [                                                                                                                                                                                 
	//       {                                                                                                                                                                                            
	//         "productId": "OLJCESPC7Z",                                                                                                                                                                 
	//         "quantity": 2                                                                                                                                                                              
	//       }                                                                                                                                                                                            
	//     ],                                                                                                                                                                                             
	//     "shippingCostLocalized": {                                                                                                                                                                     
	//       "currencyCode": "EUR",                                                                                                                                                                       
	//       "units": 5,                                                                                                                                                                                  
	//       "nanos": 0                                                                                                                                                                                   
	//     }                                                                                                                                                                                              
	// }
	orderMetadataBytes, err := json.Marshal(orderMetadata)
	if err != nil {
		tx.Rollback(ctx)
		logger.Error(fmt.Sprintf("failed to convert Go struct into a JSONB format: %v", err))
		return nil, status.Errorf(codes.Internal, "failed to convert Go struct into a JSONB format: %v", err)
	}

	_, err = tx.Exec(ctx, `
		INSERT INTO checkout.orders 
		(order_id, user_id, currency_code, status, order_metadata) 
		VALUES ($1, $2, $3, $4, $5)`,
		orderID.String(), req.UserId, req.UserCurrency, "PROCESSING", orderMetadataBytes,
	)
	if err != nil {
		tx.Rollback(ctx)
		logger.Error(fmt.Sprintf("failed to insert order: %v", err))
		return nil, status.Errorf(codes.Internal, "failed to insert order: %v", err)
	}

	_, err = tx.Exec(ctx, `
		INSERT INTO checkout.outbox 
		(aggregate_id, event_type, order_id) 
		VALUES ($1, $2, $3)`,
		orderID.String(), "ORDER_PLACED", orderID.String(),
	)
	if err != nil {
		tx.Rollback(ctx)
		logger.Error(fmt.Sprintf("failed to insert outbox event: %v", err))
		return nil, status.Errorf(codes.Internal, "failed to insert outbox event: %v", err)
	}

	if err := tx.Commit(ctx); err != nil {
		logger.Error(fmt.Sprintf("failed to commit transaction: %v", err))
		return nil, status.Errorf(codes.Internal, "failed to commit transaction: %v", err)
	}

	logger.Info("successfully saved order and outbox event to DB")
	
	orderResult := &pb.OrderResult{
		OrderId:            orderID.String(),
		ShippingTrackingId: "",
		ShippingCost:       prep.shippingCostLocalized,
		ShippingAddress:    req.Address,
		Items:              prep.orderItems,
	}

	shippingCostFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", prep.shippingCostLocalized.GetUnits(), prep.shippingCostLocalized.GetNanos()/1000000000), 64)
	totalPriceFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", total.GetUnits(), total.GetNanos()/1000000000), 64)

	span.SetAttributes(
		attribute.String("app.order.id", orderID.String()),
		attribute.Float64("app.shipping.amount", shippingCostFloat),
		attribute.Float64("app.order.amount", totalPriceFloat),
		attribute.Int("app.order.items.count", len(prep.orderItems)),
	)
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "order placed (asynchronous)",
		slog.String("app.order.id", orderID.String()),
		slog.Float64("app.shipping.amount", shippingCostFloat),
		slog.Float64("app.order.amount", totalPriceFloat),
		slog.Int("app.order.items.count", len(prep.orderItems)),
	)

	go cs.sendToPostProcessor(context.WithoutCancel(ctx), orderResult)

	resp := &pb.PlaceOrderResponse{Order: orderResult}
	return resp, nil
}

type orderPrep struct {
	orderItems            []*pb.OrderItem
	cartItems             []*pb.CartItem
	shippingCostLocalized *pb.Money
}

// In checkout service 
//   1. getUserCart: 
// 		- Calls Cart service using userID to retrieve the current list of items in the user's cart
//   2. prepOrderItems: 
// 		- For each item in the cart, calls the Product Catalog service to fetch the product's base price (USD). 
// 		- It then calls the Currency service to convert that base price into the user's local currency (userCurrency).
//   3. Gets a Shipping Quote (quoteShipping): 
// 		- It sends the cart items and the destination address to the Shipping service to get a calculated shipping cost (returned in USD).
//   4. Converts the Shipping Currency (convertCurrency): 
// 		- It calls the Currency service again to convert the USD shipping cost into the user's local userCurrency.
func (cs *checkout) prepareOrderItemsAndShippingQuoteFromCart(ctx context.Context, userID, userCurrency string, address *pb.Address) (orderPrep, error) {

	ctx, span := tracer.Start(ctx, "prepareOrderItemsAndShippingQuoteFromCart")
	defer span.End()

	var out orderPrep
	cartItems, err := cs.getUserCart(ctx, userID)
	if err != nil {
		return out, fmt.Errorf("cart failure: %+v", err)
	}

	group, groupCtx := errgroup.WithContext(ctx)
	var orderItems []*pb.OrderItem
	var shippingPrice *pb.Money

	group.Go(func() error {
		var prepErr error
		orderItems, prepErr = cs.prepOrderItems(groupCtx, cartItems, userCurrency)
		if prepErr != nil {
			return fmt.Errorf("failed to prepare order: %+v", prepErr)
		}
		return nil
	})

	group.Go(func() error {
		shippingUSD, quoteErr := cs.quoteShipping(groupCtx, address, cartItems)
		if quoteErr != nil {
			return fmt.Errorf("shipping quote failure: %+v", quoteErr)
		}

		var conversionErr error
		shippingPrice, conversionErr = cs.convertCurrency(groupCtx, shippingUSD, userCurrency)
		if conversionErr != nil {
			return fmt.Errorf("failed to convert shipping cost to currency: %+v", conversionErr)
		}
		return nil
	})

	if err := group.Wait(); err != nil {
		return out, err
	}

	out.shippingCostLocalized = shippingPrice
	out.cartItems = cartItems
	out.orderItems = orderItems

	var totalCart int32
	for _, ci := range cartItems {
		totalCart += ci.Quantity
	}
	shippingCostFloat, _ := strconv.ParseFloat(fmt.Sprintf("%d.%02d", shippingPrice.GetUnits(), shippingPrice.GetNanos()/1000000000), 64)

	span.SetAttributes(
		attribute.Float64("app.shipping.amount", shippingCostFloat),
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

func (cs *checkout) getUserCart(ctx context.Context, userID string) ([]*pb.CartItem, error) {
	rpcCtx, cancel := context.WithTimeout(ctx, checkoutDependencyTimeout)
	defer cancel()
	cart, err := cs.cartSvcClient.GetCart(rpcCtx, &pb.GetCartRequest{UserId: userID})
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
				rpcCtx, cancel := context.WithTimeout(groupCtx, checkoutDependencyTimeout)
				defer cancel()
				return cs.productCatalogSvcClient.GetProduct(rpcCtx, &pb.GetProductRequest{Id: cartItem.GetProductId()})
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
		rpcCtx, cancel := context.WithTimeout(ctx, checkoutDependencyTimeout)
		defer cancel()
		return cs.currencySvcClient.Convert(rpcCtx, &pb.CurrencyConversionRequest{
			From:   from,
			ToCode: toCurrency})
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

func (cs *checkout) sendToPostProcessor(ctx context.Context, result *pb.OrderResult) {
	if cs.KafkaProducerClient == nil {
		logger.Warn("KafkaProducerClient is nil, skipping message publish")
		return
	}

	message, err := proto.Marshal(result)
	if err != nil {
		logger.Error(fmt.Sprintf("Failed to marshal message to protobuf: %+v", err))
		return
	}

	msg := sarama.ProducerMessage{
		Topic: kafka.Topic,
		Key:   sarama.StringEncoder(result.OrderId),
		Value: sarama.ByteEncoder(message),

		// Send messages having routing_key
		Headers: []sarama.RecordHeader{
			{Key: []byte("routing_key"), Value: []byte(result.OrderId)},
		},
	}

	// Inject tracing info into message
	span := createProducerSpan(ctx, &msg)
	defer span.End()

	// Send message and handle response
	startTime := time.Now()
	select {
	case cs.KafkaProducerClient.Input() <- &msg:
		select {
		case successMsg := <-cs.KafkaProducerClient.Successes():
			span.SetAttributes(
				attribute.Bool("messaging.kafka.producer.success", true),
				attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
				attribute.KeyValue(semconv.MessagingKafkaMessageOffset(int(successMsg.Offset))),
			)
			logger.Info(fmt.Sprintf("Successful to write message. offset: %v, duration: %v", successMsg.Offset, time.Since(startTime)))
		case errMsg := <-cs.KafkaProducerClient.Errors():
			span.SetAttributes(
				attribute.Bool("messaging.kafka.producer.success", false),
				attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
			)
			span.SetStatus(otelcodes.Error, errMsg.Err.Error())
			logger.Error(fmt.Sprintf("Failed to write message: %v", errMsg.Err))
		case <-ctx.Done():
			span.SetAttributes(
				attribute.Bool("messaging.kafka.producer.success", false),
				attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
			)
			span.SetStatus(otelcodes.Error, "Context cancelled: "+ctx.Err().Error())
			logger.Warn(fmt.Sprintf("Context canceled before success message received: %v", ctx.Err()))
		}
	case <-ctx.Done():
		span.SetAttributes(
			attribute.Bool("messaging.kafka.producer.success", false),
			attribute.Int("messaging.kafka.producer.duration_ms", int(time.Since(startTime).Milliseconds())),
		)
		span.SetStatus(otelcodes.Error, "Failed to send: "+ctx.Err().Error())
		logger.Error(fmt.Sprintf("Failed to send message to Kafka within context deadline: %v", ctx.Err()))
		return
	}

	ffValue := cs.getIntFeatureFlag(ctx, "kafkaQueueProblems")
	if ffValue > 0 {
		cs.publishKafkaQueueProblems(ctx, result, ffValue)
	}

	return publishErr
}

func (cs *checkout) publishKafkaQueueProblems(ctx context.Context, result *pb.OrderResult, ffValue int) {
	logger.Info("Warning: FeatureFlag 'kafkaQueueProblems' is activated, overloading queue now.")
	for i := 0; i < ffValue; i++ {
		go func(i int) {
			incidentCtx := context.WithoutCancel(ctx)
			if err := cs.orderEventPublisher.PublishIncident(incidentCtx, result); err != nil {
				logger.Error(fmt.Sprintf("kafkaQueueProblems publish %d failed: %v", i, err))
			}
		}(i)
	}
	logger.Info(fmt.Sprintf("Done with #%d messages for overload simulation.", ffValue))
}

func createProducerSpan(ctx context.Context, msg *sarama.ProducerMessage) trace.Span {
	spanTracer := tracer
	if spanTracer == nil {
		spanTracer = otel.Tracer("checkout")
	}
	spanContext, span := spanTracer.Start(
		ctx,
		fmt.Sprintf("%s publish", msg.Topic),
		trace.WithSpanKind(trace.SpanKindProducer),
		trace.WithAttributes(
			semconv.PeerService("kafka"),
			semconv.NetworkTransportTCP,
			semconv.MessagingSystemKafka,
			semconv.MessagingDestinationName(msg.Topic),
			semconv.MessagingOperationPublish,
			semconv.MessagingKafkaDestinationPartition(int(msg.Partition)),
		),
	)

	carrier := propagation.MapCarrier{}
	propagator := otel.GetTextMapPropagator()
	propagator.Inject(spanContext, carrier)

	for key, value := range carrier {
		msg.Headers = append(msg.Headers, sarama.RecordHeader{Key: []byte(key), Value: []byte(value)})
	}

	return span
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
