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

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/log/global"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"

	"github.com/IBM/sarama"
	"github.com/google/uuid"
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

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/status"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"github.com/open-telemetry/techx-corp/src/checkout/money"

	"github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/service/dynamodb"
)

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

var logger *slog.Logger
var tracer trace.Tracer
var resource *sdkresource.Resource
var initResourcesOnce sync.Once

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
	KafkaProducerClient     sarama.AsyncProducer
	shippingSvcClient       pb.ShippingServiceClient
	productCatalogSvcClient pb.ProductCatalogServiceClient
	cartSvcClient           pb.CartServiceClient
	currencySvcClient       pb.CurrencyServiceClient
	emailSvcClient          pb.EmailServiceClient
	paymentSvcClient        pb.PaymentServiceClient

	// DynamoDB 
	dynamoClient *dynamodb.Client
	tableName string
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

	// Load AWS Config and initialize DynamoDB Client
	cfg, err := config.LoadDefaultConfig(context.Background())
	if err != nil {
		logger.Error(fmt.Sprintf("Unable to load AWS SDK config: %v", err))
	}
	svc.dynamoClient = dynamodb.NewFromConfig(cfg)
 
	// Get Dynamodb table name from environment variable
	mustMapEnv(&svc.tableName, "DYNAMODB_TABLE_NAME")

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

	// svc.kafkaBrokerSvcAddr = os.Getenv("KAFKA_ADDR")

	// if svc.kafkaBrokerSvcAddr != "" {
	// 	brokers := strings.Split(svc.kafkaBrokerSvcAddr, ",")
	// 	svc.KafkaProducerClient, err = kafka.CreateKafkaProducer(brokers, logger)
	// 	if err != nil {
	// 		logger.Error(err.Error())
	// 	}
	// }

	logger.Info(fmt.Sprintf("service config: %+v", svc))

	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		logger.Error(err.Error())
	}

	var srv = grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)
	pb.RegisterCheckoutServiceServer(srv, svc)

	healthcheck := health.NewServer()
	healthpb.RegisterHealthServer(srv, healthcheck)

	// CDO-80 (Option C): tách liveness khỏi readiness để dependency (Kafka) giật
	// không gây restart pod (cascade-restart). Liveness chỉ phản ánh "process còn sống".
	healthcheck.SetServingStatus("liveness", healthpb.HealthCheckResponse_SERVING)
	// Giữ tương thích ngược cho probe không truyền service name.
	healthcheck.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)

	// When checkout pod restarts and opens gRPC port
	// it is ready to handle users' traffic
	healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_SERVING) 

	// Readiness ĐỘNG: kiểm tra kết nối TCP tới broker Kafka định kỳ (giống initContainer
	// wait-for-kafka). Kafka mất → NOT_SERVING (pod bị kéo khỏi Endpoints) nhưng KHÔNG
	// restart; Kafka hồi → SERVING trở lại. sarama.AsyncProducer không có API ping nên
	// dùng net.DialTimeout thay vì phụ thuộc internals của producer.
	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()
		updateReadiness := func() {
			if svc.kafkaBrokerSvcAddr == "" { // không cấu hình Kafka → coi như sẵn sàng
				healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_SERVING)
				return
			}
			reachable := false
			for _, broker := range strings.Split(svc.kafkaBrokerSvcAddr, ",") {
				conn, err := net.DialTimeout("tcp", broker, 2*time.Second)
				if err == nil {
					conn.Close()
					reachable = true
					break
				}
			}
			if reachable {
				healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_SERVING)
			} else {
				healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_NOT_SERVING)
			}
		}
		updateReadiness()
		for range ticker.C {
			updateReadiness()
		}
	}()

	logger.Info(fmt.Sprintf("starting to listen on tcp: %q", lis.Addr().String()))
	err = srv.Serve(lis)
	logger.Error(err.Error())

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	go func() {
		if err := srv.Serve(lis); err != nil {
			logger.Error(err.Error())
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	logger.Info("Checkout gRPC server stopped")
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

	orderID, err := uuid.NewUUID()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to generate order uuid")
	}

	prep, err := cs.prepareOrderItemsAndShippingQuoteFromCart(ctx, req.UserId, req.UserCurrency, req.Address)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	span.AddEvent("prepared")

	total := &pb.Money{CurrencyCode: req.UserCurrency,
		Units: 0,
		Nanos: 0}
	total = money.Must(money.Sum(total, prep.shippingCostLocalized))
	for _, it := range prep.orderItems {
		multPrice := money.MultiplySlow(it.Cost, uint32(it.GetItem().GetQuantity()))
		total = money.Must(money.Sum(total, multPrice))
	}

	// PHASE 1: CREATE ORDER
	partialOrderResult := &pb.OrderResult{
		OrderId:            orderID.String(),
		ShippingTrackingId: "PENDING",
		ShippingCost:       prep.shippingCostLocalized,
		ShippingAddress:    req.Address,
		Items:              prep.orderItems,
		Email:              req.Email,
	}

	reconcileAt := time.Now().Add(10 * time.Minute).Format(time.RFC3339) //String
	_ = cs.putOrderState(
		ctx,
		orderID,
		"PROCESSING",
		"NOT_STARTED",
		"NOT_STARTED",
		"PENDING",
		reconcileAt,
		req, // Lambda reads this for the Credit Card info
		partialOrderResult, //Lambda reads this for the Items and Cost (order_data)
	)

	maxRetries := 3
	// PHASE 2: PAYMENT SERVICE
	var txID string
	var paymentErr error
	for i := 0; i < maxRetries; i++{
		txID, paymentErr = cs.chargeCard(ctx, total, req.CreditCard)
		if paymentErr == nil{
			break // done
		}
		logger.Warn(fmt.Sprintf("Payment attempt %d failed: %v. Retrying...", i, paymentErr))
		time.Sleep(500 * time.Millisecond) // Backoff 0.5s
	}
	if paymentErr != nil{
		logger.Error("Payment completely failed after retries. Applying fallback")

		span.AddEvent(
			"payment_fallback_applied",
			trace.WithAttributes(attribute.String("app.payment.transaction.id", txID)),
		)

		_ = cs.putOrderState(
			ctx,
			orderID,
			"PENDING_PAYMENT", 
			"NOT_STARTED", 
			"FAILED", 
			"PENDING", 
			reconcileAt, 
			req, 
			partialOrderResult,
		)

		orderResult := &pb.OrderResult{
			OrderId: orderID.String(),
			ShippingTrackingId: "PAYMENT_PROCESSING",
			ShippingCost: prep.shippingCostLocalized,
			ShippingAddress: req.Address,
			Items: prep.orderItems,
			Email: req.Email,
		}

		_ = cs.emptyUserCart(ctx, req.UserId)

		return &pb.PlaceOrderResponse{Order: orderResult}, nil
	}

	span.AddEvent("charged",
		trace.WithAttributes(attribute.String("app.payment.transaction.id", txID)))
	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "payment went through",
		slog.String("transaction_id", txID),
	)

	// PHASE 3: MONEY TAKEN, NEXT IS SHIPPING
	_ = cs.putOrderState(
		ctx, 
		orderID, 
		"PENDING_SHIPPING", 
		"NOT_STARTED", 
		"SUCCESS", 
		"PENDING", 
		reconcileAt, 
		req,
		partialOrderResult,
	)

	var shippingTrackingID string
	var shippingErr error
	for i := 0; i < maxRetries; i++ {
		shippingTrackingID, shippingErr = cs.shipOrder(ctx, req.Address, prep.cartItems)
			if shippingErr == nil{
				break
		}
		logger.Warn(fmt.Sprintf("Shipping attempt %d failed: %v. Retrying...", i, shippingTrackingID))
		time.Sleep(500 * time.Millisecond)

	}
	if shippingErr != nil{
		logger.Error("Shipping completely failed after retries. Applying fallback.")
		shippingTrackingID = "SHIPPING_PROCESSING"

		span.AddEvent(
			"shipping_fallback_applied",
			trace.WithAttributes(attribute.String("app.payment.transaction.id", txID)),
		)

		_ = cs.putOrderState(
			ctx, 
			orderID, 
			"PENDING_SHIPPING", 
			"FAILED", 
			"SUCCESS", 
			"PENDING", 
			reconcileAt, 
			req, 
			partialOrderResult,
		)

		orderResult := &pb.OrderResult{
			OrderId: orderID.String(),
			ShippingTrackingId: shippingTrackingID,
			ShippingCost: prep.shippingCostLocalized,
			ShippingAddress: req.Address,
			Items: prep.orderItems,
			Email: req.Email,
		}

		_ = cs.emptyUserCart(ctx, req.UserId)

		return &pb.PlaceOrderResponse{Order: orderResult}, nil

	}
	
	span.AddEvent(
		"shipped", 
		trace.WithAttributes(attribute.String("app.shipping.tracking.id", shippingTrackingID)),
	)

	// PHRAE 3: CREATE ORDER RESULT
	orderResult := &pb.OrderResult{
		OrderId:            orderID.String(),
		ShippingTrackingId: shippingTrackingID,
		ShippingCost:       prep.shippingCostLocalized,
		ShippingAddress:    req.Address,
		Items:              prep.orderItems,
		Email:              req.Email,
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
		slog.LevelInfo, "order placed",
		slog.String("app.order.id", orderID.String()),
		slog.Float64("app.shipping.amount", shippingCostFloat),
		slog.Float64("app.order.amount", totalPriceFloat),
		slog.Int("app.order.items.count", len(prep.orderItems)),
		slog.String("app.shipping.tracking.id", shippingTrackingID),
	)

	// PHASE 4: READY TO BE PUSHED TO KAFKA BY LAMBDA
	_ = cs.putOrderState(
		ctx, 
		orderID, 
		"COMPLETED", 
		"SUCCESS", 
		"SUCCESS", 
		"DONE", 
		reconcileAt, 
		nil, 
		orderResult,
	)

	_ = cs.emptyUserCart(ctx, req.UserId)

	resp := &pb.PlaceOrderResponse{Order: orderResult}
	return resp, nil
}

type orderPrep struct {
	orderItems            []*pb.OrderItem
	cartItems             []*pb.CartItem
	shippingCostLocalized *pb.Money
}

func (cs *checkout) prepareOrderItemsAndShippingQuoteFromCart(ctx context.Context, userID, userCurrency string, address *pb.Address) (orderPrep, error) {

	ctx, span := tracer.Start(ctx, "prepareOrderItemsAndShippingQuoteFromCart")
	defer span.End()

	var out orderPrep
	cartItems, err := cs.getUserCart(ctx, userID)
	if err != nil {
		return out, fmt.Errorf("cart failure: %+v", err)
	}
	orderItems, err := cs.prepOrderItems(ctx, cartItems, userCurrency)
	if err != nil {
		return out, fmt.Errorf("failed to prepare order: %+v", err)
	}
	shippingUSD, err := cs.quoteShipping(ctx, address, cartItems)
	if err != nil {
		return out, fmt.Errorf("shipping quote failure: %+v", err)
	}
	shippingPrice, err := cs.convertCurrency(ctx, shippingUSD, userCurrency)
	if err != nil {
		return out, fmt.Errorf("failed to convert shipping cost to currency: %+v", err)
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
	cart, err := cs.cartSvcClient.GetCart(ctx, &pb.GetCartRequest{UserId: userID})
	if err != nil {
		return nil, fmt.Errorf("failed to get user cart during checkout: %+v", err)
	}
	return cart.GetItems(), nil
}

func (cs *checkout) emptyUserCart(ctx context.Context, userID string) error {
	if _, err := cs.cartSvcClient.EmptyCart(ctx, &pb.EmptyCartRequest{UserId: userID}); err != nil {
		return fmt.Errorf("failed to empty user cart during checkout: %+v", err)
	}
	return nil
}

func (cs *checkout) prepOrderItems(ctx context.Context, items []*pb.CartItem, userCurrency string) ([]*pb.OrderItem, error) {
	out := make([]*pb.OrderItem, len(items))

	for i, item := range items {
		product, err := cs.productCatalogSvcClient.GetProduct(ctx, &pb.GetProductRequest{Id: item.GetProductId()})
		if err != nil {
			return nil, fmt.Errorf("failed to get product #%q", item.GetProductId())
		}
		price, err := cs.convertCurrency(ctx, product.GetPriceUsd(), userCurrency)
		if err != nil {
			return nil, fmt.Errorf("failed to convert price of %q to %s", item.GetProductId(), userCurrency)
		}
		out[i] = &pb.OrderItem{
			Item: item,
			Cost: price}
	}
	return out, nil
}

func (cs *checkout) convertCurrency(ctx context.Context, from *pb.Money, toCurrency string) (*pb.Money, error) {
	result, err := cs.currencySvcClient.Convert(ctx, &pb.CurrencyConversionRequest{
		From:   from,
		ToCode: toCurrency})
	if err != nil {
		return nil, fmt.Errorf("failed to convert currency: %+v", err)
	}
	return result, err
}

func (cs *checkout) chargeCard(ctx context.Context, amount *pb.Money, paymentInfo *pb.CreditCardInfo) (string, error) {
	paymentService := cs.paymentSvcClient
	if cs.isFeatureFlagEnabled(ctx, "paymentUnreachable") {
		badAddress := "badAddress:50051"
		c := mustCreateClient(badAddress)
		paymentService = pb.NewPaymentServiceClient(c)
	}

	paymentResp, err := paymentService.Charge(ctx, &pb.ChargeRequest{
		Amount:     amount,
		CreditCard: paymentInfo})
	if err != nil {
		return "", fmt.Errorf("could not charge the card: %+v", err)
	}
	return paymentResp.GetTransactionId(), nil
}

func (cs *checkout) sendOrderConfirmation(ctx context.Context, email string, order *pb.OrderResult) error {
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
