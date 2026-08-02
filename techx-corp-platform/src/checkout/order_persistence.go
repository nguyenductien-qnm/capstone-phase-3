// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"

	"github.com/google/uuid"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"google.golang.org/protobuf/encoding/protojson"
)

const (
	idempotencyMetadataKey = "x-idempotency-key"
)

var (
	errIdempotencyConflict = errors.New("idempotency key was already used with a different request")
	idempotencyKeyPattern  = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$`)
	orderIDNamespace       = uuid.MustParse("48e00b14-3f8a-4df6-8a70-5481e45cd9b0")
)

type orderPersistenceRecord struct {
	OrderID           string
	UserID            string
	CurrencyCode      string
	OrderMetadataJSON []byte
	OrderResultJSON   []byte
	OrderResult       *pb.OrderResult
	IdempotencyKey    string
	RequestHash       string
}

func validateIdempotencyKey(key string) error {
	if !idempotencyKeyPattern.MatchString(key) {
		return fmt.Errorf("must be 8-128 characters and contain only letters, digits, '.', '_', ':', or '-'")
	}
	return nil
}

func checkoutRequestHash(req *pb.PlaceOrderRequest) (string, error) {
	// Never persist or hash PAN/CVV. Last-four plus expiry distinguish the
	// payment method for idempotency without creating recoverable card data.
	card := req.GetCreditCard()
	canonical := struct {
		UserID              string      `json:"userId"`
		UserCurrency        string      `json:"userCurrency"`
		Address             *pb.Address `json:"address"`
		Email               string      `json:"email"`
		CardLastFour        string      `json:"cardLastFour"`
		CardExpirationYear  int32       `json:"cardExpirationYear"`
		CardExpirationMonth int32       `json:"cardExpirationMonth"`
	}{
		UserID:              req.GetUserId(),
		UserCurrency:        req.GetUserCurrency(),
		Address:             req.GetAddress(),
		Email:               req.GetEmail(),
		CardLastFour:        cardLastFour(card.GetCreditCardNumber()),
		CardExpirationYear:  card.GetCreditCardExpirationYear(),
		CardExpirationMonth: card.GetCreditCardExpirationMonth(),
	}
	payload, err := json.Marshal(canonical)
	if err != nil {
		return "", fmt.Errorf("marshal idempotency request: %w", err)
	}
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:]), nil
}

func cardLastFour(number string) string {
	if len(number) <= 4 {
		return number
	}
	return number[len(number)-4:]
}

func idempotentOrderID(userID string, key string) string {
	return uuid.NewSHA1(orderIDNamespace, []byte(userID+"\x00"+key)).String()
}

func marshalOrderMetadata(
	req *pb.PlaceOrderRequest,
	orderItems []*pb.OrderItem,
	cartItems []*pb.CartItem,
	shippingCost *pb.Money,
	total *pb.Money,
	requestHash string,
	orderResultJSON []byte,
) ([]byte, error) {
	type idempotencyEnvelope struct {
		Version     int             `json:"version"`
		RequestHash string          `json:"requestHash"`
		OrderResult json.RawMessage `json:"orderResult"`
	}
	sanitized := struct {
		UserID       string          `json:"userId"`
		UserCurrency string          `json:"userCurrency"`
		Address      *pb.Address     `json:"address"`
		Email        string          `json:"email"`
		OrderItems   []*pb.OrderItem `json:"orderItems"`
		CartItems    []*pb.CartItem  `json:"cartItems"`
		ShippingCost *pb.Money       `json:"shippingCostLocalized"`
		Total        *pb.Money       `json:"total"`
		Checkout     struct {
			Idempotency idempotencyEnvelope `json:"idempotency"`
		} `json:"_checkout"`
	}{
		UserID:       req.GetUserId(),
		UserCurrency: req.GetUserCurrency(),
		Address:      req.GetAddress(),
		Email:        req.GetEmail(),
		OrderItems:   orderItems,
		CartItems:    cartItems,
		ShippingCost: shippingCost,
		Total:        total,
	}
	sanitized.Checkout.Idempotency = idempotencyEnvelope{
		Version:     1,
		RequestHash: requestHash,
		OrderResult: json.RawMessage(orderResultJSON),
	}
	payload, err := json.Marshal(sanitized)
	if err != nil {
		return nil, fmt.Errorf("marshal sanitized order metadata: %w", err)
	}
	return payload, nil
}

func marshalOrderResult(result *pb.OrderResult) ([]byte, error) {
	payload, err := protojson.Marshal(result)
	if err != nil {
		return nil, fmt.Errorf("marshal order result: %w", err)
	}
	return payload, nil
}

func unmarshalOrderResult(payload []byte) (*pb.OrderResult, error) {
	var result pb.OrderResult
	if err := protojson.Unmarshal(payload, &result); err != nil {
		return nil, fmt.Errorf("unmarshal persisted order result: %w", err)
	}
	return &result, nil
}
