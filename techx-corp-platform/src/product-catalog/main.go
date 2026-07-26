// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "github.com/lib/pq"
	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	otelcodes "go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/propagation"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.38.0"
	"go.opentelemetry.io/otel/trace"

	otelhooks "github.com/open-feature/go-sdk-contrib/hooks/open-telemetry/pkg"
	flagd "github.com/open-feature/go-sdk-contrib/providers/flagd/pkg"
	"github.com/open-feature/go-sdk/openfeature"
	pb "github.com/opentelemetry/techx-corp/src/product-catalog/genproto/oteldemo"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"

	"github.com/XSAM/otelsql"
)

type productCatalog struct {
	pb.UnimplementedProductCatalogServiceServer
}

var (
	logger            *slog.Logger
	resource          *sdkresource.Resource
	initResourcesOnce sync.Once
	db                *sql.DB
	reg               metric.Registration
)

func init() {
	logger = otelslog.NewLogger("product-catalog")
}

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
		logger.Error(fmt.Sprintf("OTLP Trace gRPC Creation: %v", err))

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

func initDatabase() error {
	connStr := os.Getenv("DB_CONNECTION_STRING")
	if connStr == "" {
		return fmt.Errorf("DB_CONNECTION_STRING environment variable not set")
	}

	var err error
	db, err = otelsql.Open("postgres", connStr,
		otelsql.WithAttributes(semconv.DBSystemNamePostgreSQL),
		otelsql.WithSpanOptions(otelsql.SpanOptions{
			OmitConnResetSession: true,
			OmitRows:             true,
		}))
	if err != nil {
		return fmt.Errorf("failed to open database connection: %w", err)
	}

	// CDO-TBD1: pool sized for small pod + RDS Proxy/replica blips.
	// MaxOpen keeps fan-out bounded under HPA; MaxIdle reuses conns after failover.
	// ConnMaxLifetime recycles sockets so stale post-failover conns die quickly.
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)
	db.SetConnMaxIdleTime(2 * time.Minute)

	reg, err = otelsql.RegisterDBStatsMetrics(db, otelsql.WithAttributes(semconv.DBSystemNamePostgreSQL))
	if err != nil {
		return fmt.Errorf("failed to register database metrics: %w", err)
	}

	// Ping with retry so a brief blip at pod start does not crash-loop the process.
	pingCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := withDBRetry(pingCtx, "ping", func() error {
		return db.PingContext(pingCtx)
	}); err != nil {
		return fmt.Errorf("failed to ping database: %w", err)
	}

	logger.Info("Database connection established")
	return nil
}

func main() {
	lp := initLoggerProvider()
	defer func() {
		if err := lp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Logger Provider Shutdown: %v", err))
		}
		logger.Info("Shutdown logger provider")
	}()

	tp := initTracerProvider()
	defer func() {
		if err := tp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Tracer Provider Shutdown: %v", err))
		}
		logger.Info("Shutdown tracer provider")
	}()

	mp := initMeterProvider()
	defer func() {
		if err := mp.Shutdown(context.Background()); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down meter provider: %v", err))
		}
		logger.Info("Shutdown meter provider")
	}()

	// Initialize database connection
	if err := initDatabase(); err != nil {
		logger.Error(fmt.Sprintf("Error initializing database: %v", err))
		os.Exit(1)
	}
	defer func() {
		if db != nil {
			if err := db.Close(); err != nil {
				logger.Error(fmt.Sprintf("Error closing database connection: %v", err))
			} else {
				logger.Info("Database connection closed")
			}
		}
		if reg != nil {
			if err := reg.Unregister(); err != nil {
				logger.Error(fmt.Sprintf("Error unregistering database metrics: %v", err))
			} else {
				logger.Info("Database metrics unregistered")
			}
		}
	}()

	openfeature.AddHooks(otelhooks.NewTracesHook())
	provider, err := flagd.NewProvider()
	if err != nil {
		logger.Error(err.Error())
	}
	err = openfeature.SetProvider(provider)
	if err != nil {
		logger.Error(err.Error())
	}

	err = runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
	if err != nil {
		logger.Error(err.Error())
	}

	svc := &productCatalog{}
	var port string
	mustMapEnv(&port, "PRODUCT_CATALOG_PORT")

	logger.Info(fmt.Sprintf("Product Catalog gRPC server started on port: %s", port))

	ln, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		logger.Error(fmt.Sprintf("TCP Listen: %v", err))
	}

	srv := grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler()),
	)

	reflection.Register(srv)

	pb.RegisterProductCatalogServiceServer(srv, svc)

	healthcheck := health.NewServer()
	healthpb.RegisterHealthServer(srv, healthcheck)

	// CDO-80 (Option C): tách liveness khỏi readiness. Liveness luôn SERVING khi
	// process sống (không phụ thuộc Postgres) → Postgres giật không restart pod.
	healthcheck.SetServingStatus("liveness", healthpb.HealthCheckResponse_SERVING)
	healthcheck.SetServingStatus("", healthpb.HealthCheckResponse_SERVING) // tương thích ngược

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	// Readiness phản ánh dependency Postgres, cập nhật định kỳ: DB mất → NOT_SERVING
	// (pod bị kéo khỏi Endpoints) nhưng KHÔNG restart; DB hồi → SERVING trở lại.
	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()
		updateReadiness := func() {
			if db != nil && db.PingContext(ctx) == nil {
				healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_SERVING)
			} else {
				healthcheck.SetServingStatus("readiness", healthpb.HealthCheckResponse_NOT_SERVING)
			}
		}
		updateReadiness()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				updateReadiness()
			}
		}
	}()

	go func() {
		if err := srv.Serve(ln); err != nil {
			logger.Error(fmt.Sprintf("Failed to serve gRPC server, err: %v", err))
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	logger.Info("Product Catalog gRPC server stopped")
}

// productPictureSQLExpr maps DB columns into the protobuf Product.picture field.
//
// CDO-TBD2 expand-contract (picture → image_url):
//
//   - dual_read (default): COALESCE(image_url, picture) — safe after ADD COLUMN +
//     during backfill while both columns exist.
//   - read_new / image_url: only image_url — use after backfill and after DROP picture
//     (set env CATALOG_SCHEMA_PHASE=read_new before contract DROP).
//
// gRPC/API field name stays "picture" so frontend/proto do not need a rename.
func productPictureSQLExpr() string {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("CATALOG_SCHEMA_PHASE"))) {
	case "read_new", "image_url":
		return "p.image_url"
	default:
		// dual_read: prefer new column when set, else legacy picture
		return "COALESCE(NULLIF(BTRIM(p.image_url), ''), p.picture)"
	}
}

func productSelectSQL(where, order string) string {
	// where/order must be static trusted fragments (no user input interpolation).
	return fmt.Sprintf(`
			SELECT p.id, p.name, p.description, %s AS picture,
			       p.price_currency_code, p.price_units, p.price_nanos, p.categories
			FROM catalog.products p
			%s
			%s
		`, productPictureSQLExpr(), where, order)
}

func loadProductsFromDB(ctx context.Context) ([]*pb.Product, error) {
	if db == nil {
		return nil, fmt.Errorf("database connection not initialized")
	}

	q := productSelectSQL("", "ORDER BY p.id")
	var products []*pb.Product
	err := withDBRetry(ctx, "loadProducts", func() error {
		rows, qerr := db.QueryContext(ctx, q)
		if qerr != nil {
			return fmt.Errorf("failed to query products: %w", qerr)
		}
		defer rows.Close()

		parsed, perr := getProductsFromRows(ctx, rows)
		if perr != nil {
			return fmt.Errorf("failed to get products from rows: %w", perr)
		}
		products = parsed
		return nil
	})
	return products, err
}

func searchProductsFromDB(ctx context.Context, query string) ([]*pb.Product, error) {
	if db == nil {
		return nil, fmt.Errorf("database connection not initialized")
	}

	searchPattern := "%" + strings.ToLower(query) + "%"
	q := productSelectSQL(
		"WHERE LOWER(p.name) LIKE $1 OR LOWER(p.description) LIKE $1",
		"ORDER BY p.id",
	)
	var products []*pb.Product
	err := withDBRetry(ctx, "searchProducts", func() error {
		rows, qerr := db.QueryContext(ctx, q, searchPattern)
		if qerr != nil {
			return fmt.Errorf("failed to query products: %w", qerr)
		}
		defer rows.Close()

		parsed, perr := getProductsFromRows(ctx, rows)
		if perr != nil {
			return fmt.Errorf("failed to get products from rows: %w", perr)
		}
		products = parsed
		return nil
	})
	if err != nil {
		return nil, err
	}

	logger.LogAttrs(
		ctx,
		slog.LevelInfo,
		fmt.Sprintf("Found %d products from database", len(products)),
		slog.Int("products", len(products)),
	)

	return products, nil
}

type awsCredentials struct {
	AccessKeyId     string
	SecretAccessKey string
	SessionToken    string
	Expiration      time.Time
}

var (
	cachedBedrockCreds awsCredentials
	cachedCredsMutex   sync.Mutex
)

type assumeRoleResponse struct {
	XMLName          xml.Name `xml:"AssumeRoleResponse"`
	AssumeRoleResult struct {
		Credentials struct {
			AccessKeyId     string `xml:"AccessKeyId"`
			SecretAccessKey string `xml:"SecretAccessKey"`
			SessionToken    string `xml:"SessionToken"`
			Expiration      string `xml:"Expiration"`
		} `xml:"Credentials"`
	} `xml:"AssumeRoleResult"`
}

func signAWSV4WithCreds(req *http.Request, body []byte, region, service, accessKey, secretKey, sessionToken string) {
	now := time.Now().UTC()
	amzDate := now.Format("20060102T150405Z")
	req.Header.Set("X-Amz-Date", amzDate)
	if sessionToken != "" {
		req.Header.Set("X-Amz-Security-Token", sessionToken)
	}
	req.Header.Set("Host", req.URL.Host)

	hash := sha256.New()
	hash.Write(body)
	payloadHash := hex.EncodeToString(hash.Sum(nil))

	var headerKeys []string
	for k := range req.Header {
		headerKeys = append(headerKeys, strings.ToLower(k))
	}
	sort.Strings(headerKeys)

	var signedHeaders []string
	var canonicalHeaders string
	for _, k := range headerKeys {
		signedHeaders = append(signedHeaders, k)
		val := req.Header.Get(k)
		canonicalHeaders += k + ":" + strings.TrimSpace(val) + "\n"
	}

	canonicalURI := strings.ReplaceAll(req.URL.Path, ":", "%3A")

	canonicalRequest := req.Method + "\n" + canonicalURI + "\n" + req.URL.RawQuery + "\n" + canonicalHeaders + "\n" + strings.Join(signedHeaders, ";") + "\n" + payloadHash

	date := now.Format("20060102")
	credentialScope := date + "/" + region + "/" + service + "/aws4_request"

	hash = sha256.New()
	hash.Write([]byte(canonicalRequest))
	canonicalRequestHash := hex.EncodeToString(hash.Sum(nil))

	stringToSign := "AWS4-HMAC-SHA256\n" + amzDate + "\n" + credentialScope + "\n" + canonicalRequestHash

	mac := hmac.New(sha256.New, []byte("AWS4"+secretKey))
	mac.Write([]byte(date))
	kDate := mac.Sum(nil)

	mac = hmac.New(sha256.New, kDate)
	mac.Write([]byte(region))
	kRegion := mac.Sum(nil)

	mac = hmac.New(sha256.New, kRegion)
	mac.Write([]byte(service))
	kService := mac.Sum(nil)

	mac = hmac.New(sha256.New, kService)
	mac.Write([]byte("aws4_request"))
	kSigning := mac.Sum(nil)

	mac = hmac.New(sha256.New, kSigning)
	mac.Write([]byte(stringToSign))
	signature := hex.EncodeToString(mac.Sum(nil))

	authHeader := "AWS4-HMAC-SHA256 Credential=" + accessKey + "/" + credentialScope + ", SignedHeaders=" + strings.Join(signedHeaders, ";") + ", Signature=" + signature
	req.Header.Set("Authorization", authHeader)
}

func signAWSV4(req *http.Request, body []byte, region, service string) {
	accessKey := os.Getenv("AWS_ACCESS_KEY_ID")
	secretKey := os.Getenv("AWS_SECRET_ACCESS_KEY")
	sessionToken := os.Getenv("AWS_SESSION_TOKEN")
	signAWSV4WithCreds(req, body, region, service, accessKey, secretKey, sessionToken)
}

func getBedrockCredentials(ctx context.Context, region string) (string, string, string, error) {
	roleArn := os.Getenv("BEDROCK_AWS_ROLE_ARN")
	if roleArn == "" || roleArn == "<your-role-arn>" {
		return os.Getenv("AWS_ACCESS_KEY_ID"), os.Getenv("AWS_SECRET_ACCESS_KEY"), os.Getenv("AWS_SESSION_TOKEN"), nil
	}

	cachedCredsMutex.Lock()
	if cachedBedrockCreds.AccessKeyId != "" && time.Now().Before(cachedBedrockCreds.Expiration.Add(-5*time.Minute)) {
		ak, sk, st := cachedBedrockCreds.AccessKeyId, cachedBedrockCreds.SecretAccessKey, cachedBedrockCreds.SessionToken
		cachedCredsMutex.Unlock()
		return ak, sk, st, nil
	}
	cachedCredsMutex.Unlock()

	externalId := os.Getenv("BEDROCK_AWS_EXTERNAL_ID")
	sessionName := os.Getenv("BEDROCK_AWS_ROLE_SESSION_NAME")
	if sessionName == "" {
		sessionName = "product-catalog-bedrock"
	}

	formData := url.Values{}
	formData.Set("Action", "AssumeRole")
	formData.Set("Version", "2011-06-15")
	formData.Set("RoleArn", roleArn)
	formData.Set("RoleSessionName", sessionName)
	if externalId != "" {
		formData.Set("ExternalId", externalId)
	}

	bodyStr := formData.Encode()
	bodyBytes := []byte(bodyStr)

	stsUrl := fmt.Sprintf("https://sts.%s.amazonaws.com/", region)
	req, err := http.NewRequestWithContext(ctx, "POST", stsUrl, bytes.NewReader(bodyBytes))
	if err != nil {
		return "", "", "", fmt.Errorf("failed to create sts request: %w", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	signAWSV4(req, bodyBytes, region, "sts")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", "", "", fmt.Errorf("sts assume-role request failed: %w", err)
	}
	defer resp.Body.Close()

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", "", "", fmt.Errorf("failed to read sts response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return "", "", "", fmt.Errorf("sts assume-role error %d: %s", resp.StatusCode, string(respBytes))
	}

	var parsedXML assumeRoleResponse
	if err := xml.Unmarshal(respBytes, &parsedXML); err != nil {
		return "", "", "", fmt.Errorf("failed to parse sts xml response: %w", err)
	}

	creds := parsedXML.AssumeRoleResult.Credentials
	if creds.AccessKeyId == "" {
		return "", "", "", fmt.Errorf("sts assume-role returned empty credentials")
	}

	expTime, _ := time.Parse(time.RFC3339, creds.Expiration)

	cachedCredsMutex.Lock()
	cachedBedrockCreds = awsCredentials{
		AccessKeyId:     creds.AccessKeyId,
		SecretAccessKey: creds.SecretAccessKey,
		SessionToken:    creds.SessionToken,
		Expiration:      expTime,
	}
	cachedCredsMutex.Unlock()

	return creds.AccessKeyId, creds.SecretAccessKey, creds.SessionToken, nil
}

func embedQuery(ctx context.Context, text string) ([]float64, error) {
	reqBody := map[string]interface{}{
		"inputText":  text,
		"dimensions": 1024,
		"normalize":  true,
	}
	bodyBytes, _ := json.Marshal(reqBody)

	region := os.Getenv("AWS_REGION")
	if region == "" {
		region = "us-east-1"
	}
	url := fmt.Sprintf("https://bedrock-runtime.%s.amazonaws.com/model/amazon.titan-embed-text-v2:0/invoke", region)

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("create req failed: %w", err)
	}

	accessKey, secretKey, sessionToken, err := getBedrockCredentials(ctx, region)
	if err != nil {
		return nil, fmt.Errorf("get bedrock creds failed: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	signAWSV4WithCreds(req, bodyBytes, region, "bedrock", accessKey, secretKey, sessionToken)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("http req failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("aws error %d: %s", resp.StatusCode, string(respBody))
	}

	var parsedResp struct {
		Embedding []float64 `json:"embedding"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsedResp); err != nil {
		return nil, fmt.Errorf("parse resp failed: %w", err)
	}
	return parsedResp.Embedding, nil
}

func formatVector(v []float64) string {
	parts := make([]string, len(v))
	for i, f := range v {
		parts[i] = fmt.Sprintf("%g", f)
	}
	return "[" + strings.Join(parts, ",") + "]"
}

func searchProductsFromDBSemantic(ctx context.Context, query string) ([]*pb.Product, error) {
	if db == nil {
		return nil, fmt.Errorf("database connection not initialized")
	}
	// Embed the query using Bedrock Titan
	embedding, err := embedQuery(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("embedding query failed: %w", err)
	}
	// Format embedding as pgvector literal
	vecLiteral := formatVector(embedding)
	q := productSelectSQL(
		"WHERE p.embedding IS NOT NULL",
		"ORDER BY p.embedding <=> $1::vector LIMIT 10",
	)
	var products []*pb.Product
	err = withDBRetry(ctx, "searchProductsSemantic", func() error {
		rows, qerr := db.QueryContext(ctx, q, vecLiteral)
		if qerr != nil {
			return fmt.Errorf("semantic search query failed: %w", qerr)
		}
		defer rows.Close()
		parsed, perr := getProductsFromRows(ctx, rows)
		if perr != nil {
			return fmt.Errorf("failed to parse semantic results: %w", perr)
		}
		products = parsed
		return nil
	})
	return products, err
}

func getProductFromDB(ctx context.Context, productID string) (*pb.Product, error) {
	if db == nil {
		return nil, fmt.Errorf("database connection not initialized")
	}

	q := productSelectSQL("WHERE p.id = $1", "")
	var product *pb.Product
	err := withDBRetry(ctx, "getProduct", func() error {
		row := db.QueryRowContext(ctx, q, productID)

		var id, name, description, picture, currencyCode, categoriesStr string
		var units int64
		var nanos int32

		if scanErr := row.Scan(&id, &name, &description, &picture, &currencyCode, &units, &nanos, &categoriesStr); scanErr != nil {
			if scanErr == sql.ErrNoRows {
				// Business miss — not a connection blip; do not retry.
				return errProductNotFound
			}
			return fmt.Errorf("failed to scan product row: %w", scanErr)
		}

		product = parseProductRow(id, name, description, picture, currencyCode, categoriesStr, units, nanos)
		return nil
	})
	if err != nil {
		return nil, err
	}
	return product, nil
}

func getProductsFromRows(ctx context.Context, rows *sql.Rows) ([]*pb.Product, error) {
	var products []*pb.Product

	for rows.Next() {
		var id, name, description, picture, currencyCode, categoriesStr string
		var units int64
		var nanos int32

		if err := rows.Scan(&id, &name, &description, &picture, &currencyCode, &units, &nanos, &categoriesStr); err != nil {
			return nil, fmt.Errorf("failed to scan product row: %w", err)
		}

		products = append(products, parseProductRow(id, name, description, picture, currencyCode, categoriesStr, units, nanos))
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating product rows: %w", err)
	}

	logger.LogAttrs(
		ctx,
		slog.LevelInfo,
		fmt.Sprintf("Found %d products from database", len(products)),
		slog.Int("products", len(products)),
	)

	return products, nil
}

func parseProductRow(id, name, description, picture, currencyCode, categoriesStr string, units int64, nanos int32) *pb.Product {
	// Parse comma-delimited categories string into slice
	var categories []string
	if categoriesStr != "" {
		categories = strings.Split(categoriesStr, ",")
		// Trim whitespace from each category
		for i, cat := range categories {
			categories[i] = strings.TrimSpace(cat)
		}
	}

	return &pb.Product{
		Id:          id,
		Name:        name,
		Description: description,
		Picture:     picture,
		PriceUsd: &pb.Money{
			CurrencyCode: currencyCode,
			Units:        units,
			Nanos:        nanos,
		},
		Categories: categories,
	}
}

func mustMapEnv(target *string, key string) {
	value, present := os.LookupEnv(key)
	if !present {
		logger.Error(fmt.Sprintf("Environment Variable Not Set: %q", key))
	}
	*target = value
}

func (p *productCatalog) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (p *productCatalog) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

func (p *productCatalog) ListProducts(ctx context.Context, req *pb.Empty) (*pb.ListProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	products, err := loadProductsFromDB(ctx)
	if err != nil {
		span.SetStatus(otelcodes.Error, err.Error())
		return nil, status.Errorf(codes.Internal, "failed to load products: %v", err)
	}

	span.SetAttributes(
		attribute.Int("app.products.count", len(products)),
	)
	return &pb.ListProductsResponse{Products: products}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("app.product.id", req.Id),
	)

	// GetProduct will fail on a specific product when feature flag is enabled
	if p.checkProductFailure(ctx, req.Id) {
		msg := "Error: Product Catalog Fail Feature Flag Enabled"
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Error(codes.Internal, msg)
	}

	found, err := getProductFromDB(ctx, req.Id)
	if err != nil {
		if errors.Is(err, errProductNotFound) {
			msg := fmt.Sprintf("Product Not Found: %s", req.Id)
			span.SetStatus(otelcodes.Error, msg)
			span.AddEvent(msg)
			return nil, status.Error(codes.NotFound, msg)
		}
		// After retries exhausted: real DB failure → Internal (not fake NotFound).
		msg := fmt.Sprintf("Product Catalog DB error for %s: %v", req.Id, err)
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Error(codes.Internal, msg)
	}

	span.AddEvent("Product Found")
	span.SetAttributes(
		attribute.String("app.product.id", req.Id),
		attribute.String("app.product.name", found.Name),
	)

	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "Product Found",
		slog.String("app.product.name", found.Name),
		slog.String("app.product.id", req.Id),
	)

	return found, nil
}

func (p *productCatalog) SearchProducts(ctx context.Context, req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	var result []*pb.Product
	var err error
	searchMode := "keyword"

	// Try semantic search first if enabled
	if os.Getenv("SEMANTIC_SEARCH_ENABLED") == "true" {
		result, err = searchProductsFromDBSemantic(ctx, req.Query)
		if err == nil && len(result) > 0 {
			searchMode = "semantic"
		} else {
			if err != nil {
				logger.Warn(fmt.Sprintf("Semantic search failed, falling back to keyword: %v", err))
			}
			result, err = searchProductsFromDB(ctx, req.Query)
		}
	} else {
		result, err = searchProductsFromDB(ctx, req.Query)
	}

	if err != nil {
		span.SetStatus(otelcodes.Error, err.Error())
		return nil, status.Errorf(codes.Internal, "failed to search products: %v", err)
	}

	span.SetAttributes(
		attribute.Int("app.products_search.count", len(result)),
		attribute.String("app.search.mode", searchMode),
	)
	return &pb.SearchProductsResponse{Results: result}, nil
}

func (p *productCatalog) checkProductFailure(ctx context.Context, id string) bool {
	if id != "OLJCESPC7Z" {
		return false
	}

	client := openfeature.NewClient("productCatalog")
	failureEnabled, _ := client.BooleanValue(
		ctx, "productCatalogFailure", false, openfeature.EvaluationContext{},
	)
	return failureEnabled
}
