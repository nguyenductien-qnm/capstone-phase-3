// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"bytes"
	"context"
	"errors"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
)

func TestValidateIdempotencyKey(t *testing.T) {
	t.Parallel()
	for _, key := range []string{
		"550e8400-e29b-41d4-a716-446655440000",
		"loadtest:checkout_0001.retry-1",
	} {
		if err := validateIdempotencyKey(key); err != nil {
			t.Fatalf("expected %q to be valid: %v", key, err)
		}
	}

	for _, key := range []string{"short", "contains a space", strings.Repeat("x", 129)} {
		if err := validateIdempotencyKey(key); err == nil {
			t.Fatalf("expected %q to be invalid", key)
		}
	}
}

func TestIdempotencyKeyFromContextRequiresClientKey(t *testing.T) {
	t.Parallel()

	for name, ctx := range map[string]context.Context{
		"missing metadata": context.Background(),
		"missing key":      metadata.NewIncomingContext(context.Background(), metadata.Pairs("other", "value")),
		"blank key":        metadata.NewIncomingContext(context.Background(), metadata.Pairs(idempotencyMetadataKey, "  ")),
		"duplicate key": metadata.NewIncomingContext(
			context.Background(),
			metadata.Pairs(idempotencyMetadataKey, "checkout-key-one", idempotencyMetadataKey, "checkout-key-two"),
		),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := idempotencyKeyFromContext(ctx); err == nil {
				t.Fatal("missing client idempotency key must be rejected")
			}
		})
	}

	ctx := metadata.NewIncomingContext(
		context.Background(),
		metadata.Pairs(idempotencyMetadataKey, "550e8400-e29b-41d4-a716-446655440000"),
	)
	key, err := idempotencyKeyFromContext(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if key != "550e8400-e29b-41d4-a716-446655440000" {
		t.Fatalf("key = %q", key)
	}
}

func TestPlaceOrderValidatesClientKeyBeforePersistence(t *testing.T) {
	t.Parallel()
	service := &checkout{}
	request := &pb.PlaceOrderRequest{UserId: "user-1", UserCurrency: "USD"}

	if _, err := service.PlaceOrder(context.Background(), request); status.Code(err) != codes.InvalidArgument {
		t.Fatalf("missing key status = %v, want InvalidArgument", status.Code(err))
	}

	ctx := metadata.NewIncomingContext(
		context.Background(),
		metadata.Pairs(idempotencyMetadataKey, "550e8400-e29b-41d4-a716-446655440000"),
	)
	if _, err := service.PlaceOrder(ctx, request); status.Code(err) != codes.Unavailable {
		t.Fatalf("valid key without DB status = %v, want Unavailable", status.Code(err))
	}
}

func TestCheckoutRequestHashUsesSafePaymentFingerprint(t *testing.T) {
	t.Parallel()
	base := &pb.PlaceOrderRequest{
		UserId:       "user-1",
		UserCurrency: "USD",
		Email:        "buyer@example.test",
		Address:      &pb.Address{City: "Bangkok", Country: "TH"},
		CreditCard:   &pb.CreditCardInfo{CreditCardNumber: "4111111111111111", CreditCardCvv: 123},
	}
	first, err := checkoutRequestHash(base)
	if err != nil {
		t.Fatal(err)
	}

	changedCard := &pb.PlaceOrderRequest{
		UserId:       base.UserId,
		UserCurrency: base.UserCurrency,
		Email:        base.Email,
		Address:      base.Address,
		CreditCard:   &pb.CreditCardInfo{CreditCardNumber: "5555555555554444", CreditCardCvv: 999},
	}
	second, err := checkoutRequestHash(changedCard)
	if err != nil {
		t.Fatal(err)
	}
	if first == second {
		t.Fatal("a different card last-four must affect the conflict hash")
	}

	changedCVV := proto.Clone(base).(*pb.PlaceOrderRequest)
	changedCVV.CreditCard = &pb.CreditCardInfo{
		CreditCardNumber: "4111111111111111",
		CreditCardCvv:    999,
	}
	cvvHash, err := checkoutRequestHash(changedCVV)
	if err != nil {
		t.Fatal(err)
	}
	if first != cvvHash {
		t.Fatal("CVV must not affect the persisted conflict hash")
	}

	changedAddress := proto.Clone(base).(*pb.PlaceOrderRequest)
	changedAddress.Address = &pb.Address{City: "Chiang Mai", Country: "TH"}
	third, err := checkoutRequestHash(changedAddress)
	if err != nil {
		t.Fatal(err)
	}
	if first == third {
		t.Fatal("business request changes must affect the conflict hash")
	}
}

func TestMarshalOrderMetadataExcludesPaymentCard(t *testing.T) {
	t.Parallel()
	req := &pb.PlaceOrderRequest{
		UserId: "user-1",
		Email:  "buyer@example.test",
		CreditCard: &pb.CreditCardInfo{
			CreditCardNumber: "4111111111111111",
			CreditCardCvv:    123,
		},
	}
	resultJSON, err := marshalOrderResult(&pb.OrderResult{OrderId: "order-1"})
	if err != nil {
		t.Fatal(err)
	}
	payload, err := marshalOrderMetadata(req, nil, nil, nil, nil, "request-hash", resultJSON)
	if err != nil {
		t.Fatal(err)
	}
	for _, forbidden := range [][]byte{
		[]byte("4111111111111111"),
		[]byte("creditCard"),
		[]byte("credit_card"),
	} {
		if bytes.Contains(payload, forbidden) {
			t.Fatalf("persisted metadata contains payment data %q", forbidden)
		}
	}
	for _, required := range [][]byte{
		[]byte(`"_checkout"`),
		[]byte(`"requestHash":"request-hash"`),
		[]byte(`"orderId":"order-1"`),
	} {
		if !bytes.Contains(payload, required) {
			t.Fatalf("persisted metadata is missing idempotency data %q", required)
		}
	}
}

func TestIdempotentOrderIDIsStableAndKeyScoped(t *testing.T) {
	t.Parallel()
	first := idempotentOrderID("user-1", "checkout-key-1")
	if got := idempotentOrderID("user-1", "checkout-key-1"); got != first {
		t.Fatalf("same user and key returned %q, want %q", got, first)
	}
	if got := idempotentOrderID("user-1", "checkout-key-2"); got == first {
		t.Fatal("different keys must produce different order IDs")
	}
	if got := idempotentOrderID("user-2", "checkout-key-1"); got == first {
		t.Fatal("the same key for a different user must produce a different order ID")
	}
}

func TestLegacyMetadataReplaysStoredResultAndDetectsConflict(t *testing.T) {
	t.Parallel()
	req := &pb.PlaceOrderRequest{UserId: "user-1"}
	resultJSON, err := marshalOrderResult(&pb.OrderResult{OrderId: "order-1"})
	if err != nil {
		t.Fatal(err)
	}
	metadataJSON, err := marshalOrderMetadata(
		req, nil, nil, nil, nil, "request-hash", resultJSON,
	)
	if err != nil {
		t.Fatal(err)
	}

	result, err := orderResultFromLegacyMetadata(metadataJSON, "request-hash")
	if err != nil {
		t.Fatal(err)
	}
	if result.GetOrderId() != "order-1" {
		t.Fatalf("replayed order ID = %q, want order-1", result.GetOrderId())
	}
	if _, err := orderResultFromLegacyMetadata(metadataJSON, "different-hash"); !errors.Is(err, errIdempotencyConflict) {
		t.Fatalf("different request hash error = %v, want idempotency conflict", err)
	}
}

func TestOrderInsertSQLByPhase(t *testing.T) {
	t.Parallel()
	tests := []struct {
		phase   orderSchemaPhase
		wantOld bool
		wantNew bool
	}{
		{orderSchemaLegacy, true, false},
		{orderSchemaDualWrite, true, true},
		{orderSchemaWriteNew, false, true},
	}
	for _, tt := range tests {
		sql := orderInsertSQL(tt.phase)
		if got := strings.Contains(sql, "order_metadata"); got != tt.wantOld {
			t.Fatalf("phase %s old column=%v, want %v", tt.phase, got, tt.wantOld)
		}
		if got := strings.Contains(sql, "order_payload"); got != tt.wantNew {
			t.Fatalf("phase %s new column=%v, want %v", tt.phase, got, tt.wantNew)
		}
		if !strings.Contains(sql, "ON CONFLICT DO NOTHING") {
			t.Fatalf("phase %s is missing idempotency conflict handling", tt.phase)
		}
	}
}

func TestCurrentOrderSchemaPhaseFallsBackSafely(t *testing.T) {
	old := os.Getenv("CHECKOUT_ORDER_SCHEMA_PHASE")
	t.Cleanup(func() { _ = os.Setenv("CHECKOUT_ORDER_SCHEMA_PHASE", old) })

	_ = os.Setenv("CHECKOUT_ORDER_SCHEMA_PHASE", "unexpected")
	if got := currentOrderSchemaPhase(); got != orderSchemaLegacy {
		t.Fatalf("unexpected phase must fall back to legacy, got %s", got)
	}
}

func TestIsTransientDBError(t *testing.T) {
	t.Parallel()
	for _, code := range []string{"08006", "40001", "40P01", "57P01", "57P03"} {
		if !isTransientDBError(&pgconn.PgError{Code: code}) {
			t.Fatalf("SQLSTATE %s should be transient", code)
		}
	}
	if isTransientDBError(&pgconn.PgError{Code: "23505"}) {
		t.Fatal("unique violation must not be retried as a transient failure")
	}
	if isTransientDBError(errors.New("business validation failed")) {
		t.Fatal("business error must not be transient")
	}
}
