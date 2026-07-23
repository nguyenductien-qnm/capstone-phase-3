// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"go.opentelemetry.io/otel"
	"google.golang.org/grpc"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
)

type checkoutDependencyFake struct {
	chargeCalls int
}

func (f *checkoutDependencyFake) AddItem(context.Context, *pb.AddItemRequest, ...grpc.CallOption) (*pb.Empty, error) {
	return &pb.Empty{}, nil
}
func (f *checkoutDependencyFake) AddItemAndGetCart(context.Context, *pb.AddItemRequest, ...grpc.CallOption) (*pb.Cart, error) {
	return &pb.Cart{Items: []*pb.CartItem{{ProductId: "product-1", Quantity: 1}}}, nil
}
func (f *checkoutDependencyFake) GetCart(context.Context, *pb.GetCartRequest, ...grpc.CallOption) (*pb.Cart, error) {
	return &pb.Cart{Items: []*pb.CartItem{{ProductId: "product-1", Quantity: 1}}}, nil
}
func (f *checkoutDependencyFake) EmptyCart(context.Context, *pb.EmptyCartRequest, ...grpc.CallOption) (*pb.Empty, error) {
	return &pb.Empty{}, nil
}
func (f *checkoutDependencyFake) ListProducts(context.Context, *pb.Empty, ...grpc.CallOption) (*pb.ListProductsResponse, error) {
	return &pb.ListProductsResponse{}, nil
}
func (f *checkoutDependencyFake) GetProduct(context.Context, *pb.GetProductRequest, ...grpc.CallOption) (*pb.Product, error) {
	return &pb.Product{Id: "product-1", PriceUsd: &pb.Money{CurrencyCode: "USD", Units: 10}}, nil
}
func (f *checkoutDependencyFake) SearchProducts(context.Context, *pb.SearchProductsRequest, ...grpc.CallOption) (*pb.SearchProductsResponse, error) {
	return &pb.SearchProductsResponse{}, nil
}
func (f *checkoutDependencyFake) GetSupportedCurrencies(context.Context, *pb.Empty, ...grpc.CallOption) (*pb.GetSupportedCurrenciesResponse, error) {
	return &pb.GetSupportedCurrenciesResponse{}, nil
}
func (f *checkoutDependencyFake) Convert(_ context.Context, request *pb.CurrencyConversionRequest, _ ...grpc.CallOption) (*pb.Money, error) {
	return request.From, nil
}
func (f *checkoutDependencyFake) Charge(context.Context, *pb.ChargeRequest, ...grpc.CallOption) (*pb.ChargeResponse, error) {
	f.chargeCalls++
	return &pb.ChargeResponse{TransactionId: "transaction-1"}, nil
}

type failingOrderEventPublisher struct {
	publishCalls int
}

func (p *failingOrderEventPublisher) Publish(context.Context, *pb.OrderResult) error {
	p.publishCalls++
	return ErrKafkaProducerUnavailable
}
func (p *failingOrderEventPublisher) PublishIncident(context.Context, *pb.OrderResult) error {
	return errors.New("incident publish must not run when producer is unavailable")
}
func (p *failingOrderEventPublisher) Close() error { return nil }

func TestPlaceOrderChargesOnceWhenKafkaIsUnavailable(t *testing.T) {
	previousLogger, previousTracer := logger, tracer
	logger = slog.Default()
	tracer = otel.Tracer("checkout-test")
	t.Cleanup(func() {
		logger = previousLogger
		tracer = previousTracer
	})

	shipping := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		response.Header().Set("Content-Type", "application/json")
		switch request.URL.Path {
		case "/get-quote":
			_, _ = fmt.Fprint(response, `{"cost_usd":{"currency_code":"USD","units":1,"nanos":0}}`)
		case "/ship-order":
			_, _ = fmt.Fprint(response, `{"tracking_id":"tracking-1"}`)
		default:
			http.NotFound(response, request)
		}
	}))
	defer shipping.Close()

	email := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, _ *http.Request) {
		response.WriteHeader(http.StatusOK)
	}))
	defer email.Close()

	dependencies := new(checkoutDependencyFake)
	publisher := new(failingOrderEventPublisher)
	service := &checkout{
		shippingSvcAddr:         shipping.URL,
		emailSvcAddr:            email.URL,
		kafkaBrokerSvcAddr:      "configured-for-test",
		cartSvcClient:           dependencies,
		productCatalogSvcClient: dependencies,
		currencySvcClient:       dependencies,
		paymentSvcClient:        dependencies,
		orderEventPublisher:     publisher,
	}

	response, err := service.PlaceOrder(context.Background(), &pb.PlaceOrderRequest{
		UserId:       "user-1",
		UserCurrency: "USD",
		Address:      &pb.Address{},
		Email:        "test@example.invalid",
		CreditCard:   &pb.CreditCardInfo{},
	})
	if err != nil {
		t.Fatalf("PlaceOrder() error = %v, want nil", err)
	}
	if response.GetOrder() == nil {
		t.Fatal("PlaceOrder() order = nil, want completed order")
	}
	if dependencies.chargeCalls != 1 {
		t.Fatalf("payment Charge() calls = %d, want 1", dependencies.chargeCalls)
	}
	if publisher.publishCalls != 1 {
		t.Fatalf("publisher Publish() calls = %d, want 1", publisher.publishCalls)
	}
}

func TestCheckoutHealthKeepsServingWhenKafkaIsUnavailable(t *testing.T) {
	healthcheck := newCheckoutHealthServer()

	for _, service := range []string{"", "liveness", "readiness"} {
		response, err := healthcheck.Check(context.Background(), &healthpb.HealthCheckRequest{Service: service})
		if err != nil {
			t.Fatalf("health Check(%q) error = %v", service, err)
		}
		if response.Status != healthpb.HealthCheckResponse_SERVING {
			t.Fatalf("health Check(%q) status = %v, want SERVING", service, response.Status)
		}
	}
}
