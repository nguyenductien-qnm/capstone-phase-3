// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"go.opentelemetry.io/otel"
	"google.golang.org/grpc"
)

func TestPrepareOrderItemsAndShippingQuoteRunsIndependentBranchesConcurrently(t *testing.T) {
	tracer = otel.Tracer("checkout-test")
	catalogStarted := make(chan struct{})
	shippingStarted := make(chan struct{})

	shippingServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		close(shippingStarted)
		select {
		case <-catalogStarted:
			w.Header().Set("Content-Type", "application/json")
			_, _ = fmt.Fprint(w, `{"cost_usd":{"currency_code":"USD","units":5,"nanos":0}}`)
		case <-time.After(time.Second):
			http.Error(w, "product preparation did not start concurrently", http.StatusGatewayTimeout)
		}
	}))
	defer shippingServer.Close()

	service := &checkout{
		shippingSvcAddr: shippingServer.URL,
		cartSvcClient:   staticCartClient{},
		productCatalogSvcClient: synchronizedProductCatalogClient{
			started:         catalogStarted,
			shippingStarted: shippingStarted,
		},
		currencySvcClient: passThroughCurrencyClient{},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	result, err := service.prepareOrderItemsAndShippingQuoteFromCart(
		ctx,
		"test-user",
		"USD",
		&pb.Address{})
	if err != nil {
		t.Fatalf("prepare order: %v", err)
	}

	if len(result.orderItems) != 1 {
		t.Fatalf("expected one prepared item, got %d", len(result.orderItems))
	}
	if result.shippingCostLocalized.GetUnits() != 5 {
		t.Fatalf("expected shipping cost 5 USD, got %v", result.shippingCostLocalized)
	}
}

type staticCartClient struct{}

func (staticCartClient) AddItem(context.Context, *pb.AddItemRequest, ...grpc.CallOption) (*pb.Empty, error) {
	return &pb.Empty{}, nil
}

func (staticCartClient) AddItemAndGetCart(context.Context, *pb.AddItemRequest, ...grpc.CallOption) (*pb.Cart, error) {
	return &pb.Cart{Items: []*pb.CartItem{{ProductId: "product-1", Quantity: 1}}}, nil
}

func (staticCartClient) GetCart(context.Context, *pb.GetCartRequest, ...grpc.CallOption) (*pb.Cart, error) {
	return &pb.Cart{Items: []*pb.CartItem{{ProductId: "product-1", Quantity: 1}}}, nil
}

func (staticCartClient) EmptyCart(context.Context, *pb.EmptyCartRequest, ...grpc.CallOption) (*pb.Empty, error) {
	return &pb.Empty{}, nil
}

type synchronizedProductCatalogClient struct {
	started         chan struct{}
	shippingStarted chan struct{}
}

func (synchronizedProductCatalogClient) ListProducts(context.Context, *pb.Empty, ...grpc.CallOption) (*pb.ListProductsResponse, error) {
	return nil, fmt.Errorf("unexpected ListProducts call")
}

func (client synchronizedProductCatalogClient) GetProduct(context.Context, *pb.GetProductRequest, ...grpc.CallOption) (*pb.Product, error) {
	close(client.started)
	select {
	case <-client.shippingStarted:
		return &pb.Product{
			Id:       "product-1",
			PriceUsd: &pb.Money{CurrencyCode: "USD", Units: 10},
		}, nil
	case <-time.After(time.Second):
		return nil, fmt.Errorf("shipping quote did not start concurrently")
	}
}

func (synchronizedProductCatalogClient) SearchProducts(context.Context, *pb.SearchProductsRequest, ...grpc.CallOption) (*pb.SearchProductsResponse, error) {
	return nil, fmt.Errorf("unexpected SearchProducts call")
}

type passThroughCurrencyClient struct{}

func (passThroughCurrencyClient) GetSupportedCurrencies(context.Context, *pb.Empty, ...grpc.CallOption) (*pb.GetSupportedCurrenciesResponse, error) {
	return nil, fmt.Errorf("unexpected GetSupportedCurrencies call")
}

func (passThroughCurrencyClient) Convert(_ context.Context, request *pb.CurrencyConversionRequest, _ ...grpc.CallOption) (*pb.Money, error) {
	converted := *request.GetFrom()
	converted.CurrencyCode = request.GetToCode()
	return &converted, nil
}
