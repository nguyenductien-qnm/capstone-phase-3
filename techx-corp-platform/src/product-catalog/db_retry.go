// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"math/rand"
	"strings"
	"time"
)

// CDO-TBD1: transient DB blip handling for RDS failover / replica restart.
// Retry only connection-class failures; never business errors (e.g. not found).

const (
	dbRetryMaxAttempts = 5
	dbRetryBaseDelay   = 100 * time.Millisecond
	dbRetryMaxDelay    = 2 * time.Second
)

// errProductNotFound is a non-retryable business miss.
var errProductNotFound = errors.New("product not found")

func withDBRetry(ctx context.Context, op string, fn func() error) error {
	var err error
	for attempt := 1; attempt <= dbRetryMaxAttempts; attempt++ {
		err = fn()
		if err == nil {
			return nil
		}
		if errors.Is(err, errProductNotFound) || !isTransientDBError(err) || attempt == dbRetryMaxAttempts {
			return err
		}

		delay := dbRetryDelay(attempt)
		logger.LogAttrs(ctx, slog.LevelWarn,
			fmt.Sprintf("transient DB error on %s (attempt %d/%d), retry in %s: %v",
				op, attempt, dbRetryMaxAttempts, delay, err),
			slog.String("op", op),
			slog.Int("attempt", attempt),
		)

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(delay):
		}
	}
	return err
}

func dbRetryDelay(attempt int) time.Duration {
	// Exponential: 100ms, 200ms, 400ms, 800ms, ... capped at max, plus jitter.
	exp := dbRetryBaseDelay * time.Duration(1<<uint(attempt-1))
	if exp > dbRetryMaxDelay {
		exp = dbRetryMaxDelay
	}
	jitter := time.Duration(rand.Int63n(int64(exp / 2)))
	return exp/2 + jitter
}

func isTransientDBError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, sql.ErrConnDone) || errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	// sql.ErrNoRows is business; wrapped as errProductNotFound before retry check.
	if errors.Is(err, sql.ErrNoRows) {
		return false
	}

	msg := strings.ToLower(err.Error())
	// Never retry logical "not found" strings from our wrappers.
	if strings.Contains(msg, "product not found") {
		return false
	}

	markers := []string{
		"driver: bad connection",
		"bad connection",
		"connection refused",
		"connection reset",
		"broken pipe",
		"server closed the connection",
		"conn closed",
		"connection timed out",
		"i/o timeout",
		"timeout exceeded",
		"unexpected eof",
		"eof",
		"no connection",
		"dial tcp",
		"too many connections",
		"remaining connection slots",
		"the database system is starting up",
		"the database system is in recovery mode",
		"could not connect",
		"network is unreachable",
	}
	for _, m := range markers {
		if strings.Contains(msg, m) {
			return true
		}
	}
	return false
}
