// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"bytes"
	"errors"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
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
	payload, err := marshalOrderMetadata(req, nil, nil, nil, nil)
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
		if !strings.Contains(sql, "ON CONFLICT (user_id, idempotency_key)") {
			if tt.phase == orderSchemaLegacy {
				continue
			}
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
