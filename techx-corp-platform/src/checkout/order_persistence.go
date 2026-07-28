// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math/rand"
	"net"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
	"google.golang.org/protobuf/encoding/protojson"
)

const (
	idempotencyMetadataKey = "x-idempotency-key"
	dbRetryMaxAttempts     = 7
	// Six backoff waits (200ms 400ms 800ms 1.6s 3s 3s) spend up to 9s of the 10s
	// checkout deadline set in GrpcDeadline.ts, so the last attempt still fires
	// inside the request budget. A managed switchover blackout outlasting that is
	// no longer a retry problem: the caller's deadline is the ceiling.
	dbRetryBaseDelay = 200 * time.Millisecond
	dbRetryMaxDelay  = 3 * time.Second
	// Time reserved for the attempt that follows a wait. Sleeping right up to the
	// deadline burns the last attempt for nothing.
	dbRetryFinalAttemptBudget = 300 * time.Millisecond
)

var (
	errIdempotencyConflict = errors.New("idempotency key was already used with a different request")
	idempotencyKeyPattern  = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$`)
	orderIDNamespace       = uuid.MustParse("48e00b14-3f8a-4df6-8a70-5481e45cd9b0")
)

type orderSchemaPhase string

const (
	orderSchemaLegacy    orderSchemaPhase = "legacy"
	orderSchemaDualWrite orderSchemaPhase = "dual_write"
	orderSchemaWriteNew  orderSchemaPhase = "write_new"
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

func currentOrderSchemaPhase() orderSchemaPhase {
	switch orderSchemaPhase(strings.ToLower(strings.TrimSpace(os.Getenv("CHECKOUT_ORDER_SCHEMA_PHASE")))) {
	case orderSchemaDualWrite:
		return orderSchemaDualWrite
	case orderSchemaWriteNew:
		return orderSchemaWriteNew
	default:
		return orderSchemaLegacy
	}
}

func orderInsertSQL(phase orderSchemaPhase) string {
	switch phase {
	case orderSchemaDualWrite:
		return `
			INSERT INTO checkout.orders
				(order_id, user_id, currency_code, status,
				 order_metadata, order_payload, idempotency_key,
				 idempotency_request_hash, order_result)
			VALUES ($1, $2, $3, 'PROCESSING', $4, $4, $5, $6, $7)
			ON CONFLICT DO NOTHING`
	case orderSchemaWriteNew:
		return `
			INSERT INTO checkout.orders
				(order_id, user_id, currency_code, status,
				 order_payload, idempotency_key,
				 idempotency_request_hash, order_result)
			VALUES ($1, $2, $3, 'PROCESSING', $4, $5, $6, $7)
			ON CONFLICT DO NOTHING`
	default:
		return `
			INSERT INTO checkout.orders
				(order_id, user_id, currency_code, status, order_metadata)
			VALUES ($1, $2, $3, 'PROCESSING', $4)
			ON CONFLICT DO NOTHING`
	}
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

func (cs *checkout) findOrderByIdempotency(
	ctx context.Context,
	userID string,
	key string,
	requestHash string,
) (*pb.OrderResult, bool, error) {
	var storedHash string
	var storedResult []byte
	err := cs.dbPool.QueryRow(ctx, `
		SELECT idempotency_request_hash, order_result
		FROM checkout.orders
		WHERE user_id = $1 AND idempotency_key = $2
	`, userID, key).Scan(&storedHash, &storedResult)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	if storedHash != requestHash {
		return nil, true, errIdempotencyConflict
	}
	result, err := unmarshalOrderResult(storedResult)
	if err != nil {
		return nil, true, err
	}
	return result, true, nil
}

func (cs *checkout) findLegacyOrderByIdempotency(
	ctx context.Context,
	orderID string,
	requestHash string,
) (*pb.OrderResult, bool, error) {
	var metadataJSON []byte
	err := cs.dbPool.QueryRow(ctx, `
		SELECT COALESCE(
			NULLIF(to_jsonb(o) -> 'order_metadata', 'null'::jsonb),
			NULLIF(to_jsonb(o) -> 'order_payload', 'null'::jsonb),
			'null'::jsonb
		)
		FROM checkout.orders AS o
		WHERE order_id = $1
	`, orderID).Scan(&metadataJSON)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}

	result, err := orderResultFromLegacyMetadata(metadataJSON, requestHash)
	if err != nil {
		return nil, true, err
	}
	return result, true, nil
}

func orderResultFromLegacyMetadata(metadataJSON []byte, requestHash string) (*pb.OrderResult, error) {
	var metadata struct {
		Checkout struct {
			Idempotency struct {
				Version     int             `json:"version"`
				RequestHash string          `json:"requestHash"`
				OrderResult json.RawMessage `json:"orderResult"`
			} `json:"idempotency"`
		} `json:"_checkout"`
	}
	if err := json.Unmarshal(metadataJSON, &metadata); err != nil {
		return nil, fmt.Errorf("unmarshal legacy order metadata: %w", err)
	}
	envelope := metadata.Checkout.Idempotency
	if envelope.Version != 1 || envelope.RequestHash == "" || len(envelope.OrderResult) == 0 {
		return nil, fmt.Errorf("legacy order is missing a valid idempotency envelope")
	}
	if envelope.RequestHash != requestHash {
		return nil, errIdempotencyConflict
	}
	result, err := unmarshalOrderResult(envelope.OrderResult)
	if err != nil {
		return nil, err
	}
	return result, nil
}

func (cs *checkout) findPersistedOrder(
	ctx context.Context,
	phase orderSchemaPhase,
	record orderPersistenceRecord,
) (*pb.OrderResult, bool, error) {
	if phase != orderSchemaLegacy {
		result, found, err := cs.findOrderByIdempotency(
			ctx, record.UserID, record.IdempotencyKey, record.RequestHash,
		)
		if err != nil || found {
			return result, found, err
		}
	}

	// Rows created before the expand migration keep their replay envelope in
	// order_metadata, which backfill copies to order_payload. to_jsonb(row)
	// keeps this fallback valid before expand and after contract.
	return cs.findLegacyOrderByIdempotency(ctx, record.OrderID, record.RequestHash)
}

func (cs *checkout) persistOrderWithRetry(
	ctx context.Context,
	record orderPersistenceRecord,
) (*pb.OrderResult, error) {
	phase := currentOrderSchemaPhase()
	if existing, found, err := cs.findPersistedOrder(ctx, phase, record); err != nil {
		if errors.Is(err, errIdempotencyConflict) {
			return nil, err
		}
		if !isTransientDBError(err) {
			return nil, err
		}
	} else if found {
		return existing, nil
	}

	insertSQL := orderInsertSQL(phase)
	var lastErr error

	for attempt := 1; attempt <= dbRetryMaxAttempts; attempt++ {
		if err := ctx.Err(); err != nil {
			return nil, err
		}

		tx, err := cs.dbPool.Begin(ctx)
		if err != nil {
			lastErr = err
		} else {
			var tag pgconn.CommandTag
			var execErr error
			if phase == orderSchemaLegacy {
				tag, execErr = tx.Exec(ctx, insertSQL,
					record.OrderID,
					record.UserID,
					record.CurrencyCode,
					record.OrderMetadataJSON,
				)
			} else {
				tag, execErr = tx.Exec(ctx, insertSQL,
					record.OrderID,
					record.UserID,
					record.CurrencyCode,
					record.OrderMetadataJSON,
					record.IdempotencyKey,
					record.RequestHash,
					record.OrderResultJSON,
				)
			}
			if execErr != nil {
				rollbackTx(tx)
				lastErr = execErr
			} else if tag.RowsAffected() == 0 {
				rollbackTx(tx)
				existing, found, lookupErr := cs.reconcileCommittedOrder(phase, record)
				if lookupErr != nil {
					if errors.Is(lookupErr, errIdempotencyConflict) {
						return nil, lookupErr
					}
					lastErr = lookupErr
				} else if found {
					return existing, nil
				} else {
					lastErr = fmt.Errorf("idempotency winner is not visible yet")
				}
			} else {
				_, outboxErr := tx.Exec(ctx, `
					INSERT INTO checkout.outbox
						(aggregate_id, event_type, order_id, user_id)
					VALUES ($1, 'ORDER_PLACED', $1, $2)
				`, record.OrderID, record.UserID)
				if outboxErr != nil {
					rollbackTx(tx)
					lastErr = outboxErr
				} else if commitErr := tx.Commit(ctx); commitErr != nil {
					lastErr = commitErr
					existing, found, lookupErr := cs.reconcileCommittedOrder(phase, record)
					if lookupErr != nil {
						if errors.Is(lookupErr, errIdempotencyConflict) {
							return nil, lookupErr
						}
						lastErr = errors.Join(lastErr, lookupErr)
					} else if found {
						return existing, nil
					}
				} else {
					return record.OrderResult, nil
				}
			}
		}

		if !isTransientDBError(lastErr) || attempt == dbRetryMaxAttempts {
			break
		}
		if err := waitForDBRetry(ctx, attempt); err != nil {
			return nil, err
		}
	}

	return nil, fmt.Errorf("persist order after %d attempts: %w", dbRetryMaxAttempts, lastErr)
}

func (cs *checkout) reconcileCommittedOrder(
	phase orderSchemaPhase,
	record orderPersistenceRecord,
) (*pb.OrderResult, bool, error) {
	// The caller's deadline may fire immediately after PostgreSQL committed.
	// Use an independent read-only budget to determine that outcome.
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	return cs.findPersistedOrder(ctx, phase, record)
}

func rollbackTx(tx pgx.Tx) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	_ = tx.Rollback(ctx)
}

func waitForDBRetry(ctx context.Context, attempt int) error {
	delay := dbRetryBaseDelay * time.Duration(1<<uint(attempt-1))
	if delay > dbRetryMaxDelay {
		delay = dbRetryMaxDelay
	}
	half := delay / 2
	delay = half + time.Duration(rand.Int63n(int64(half)+1))

	// Never sleep past the caller's deadline, and stop once too little of it is
	// left to run another attempt.
	if deadline, ok := ctx.Deadline(); ok {
		remaining := time.Until(deadline) - dbRetryFinalAttemptBudget
		if remaining <= 0 {
			return context.DeadlineExceeded
		}
		if delay > remaining {
			delay = remaining
		}
	}

	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func isTransientDBError(err error) bool {
	if err == nil || errors.Is(err, errIdempotencyConflict) {
		return false
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}

	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) {
		return strings.HasPrefix(pgErr.Code, "08") ||
			pgErr.Code == "40001" ||
			pgErr.Code == "40P01" ||
			pgErr.Code == "57P01" ||
			pgErr.Code == "57P03"
	}

	var netErr net.Error
	if errors.As(err, &netErr) {
		return true
	}

	message := strings.ToLower(err.Error())
	for _, fragment := range []string{
		"connection reset",
		"connection refused",
		"broken pipe",
		"server closed",
		"unexpected eof",
		"failed to connect",
		"the database system is starting up",
		"the database system is in recovery mode",
		"idempotency winner is not visible yet",
	} {
		if strings.Contains(message, fragment) {
			return true
		}
	}
	return false
}
