# AIOps Telemetry Audit

## Goal
Verify the local trace flow for the `techx-corp-platform` Docker Compose stack from browser --> frontend-proxy --> otel-collector --> jaeger.

This is based on a task delegation on Jira, which has a descriptionof the following (in Vietnamese).

```
# [AIOps-W1-T3 [TF1 - 51]] Audit hạ tầng Telemetry & Phân tích trace context

Mục tiêu & Phạm vi:

Đánh giá toàn diện đường ống telemetry hiện tại của hệ thống.

Context kỹ thuật & AIOps Learning:

Audit Telemetry Pipeline: Kiểm tra cấu hình OpenTelemetry Collector trong pod reviews để đảm bảo trace context không bị đứt đoạn khi đi qua frontend-proxy và Jaeger.

Phòng ngừa sự cố lịch sử (INC-3): Đảm bảo các span ghi nhận chính xác thời điểm sẵn sàng của service khi deploy (readiness gating) để tránh lỗi 503.
```

## Scope
- Local Docker Compose stack in `techx-corp-platform`
- Browser OTLP trace export path through `frontend-proxy`
- Collector trace pipeline to Jaeger
- Jaeger query API behavior and JSON payloads
- Trace context propagation from frontend to backend

## Current status
- Jaeger container is running and reachable via the local stack.
- `http://localhost:8080/jaeger/ui/api/services` returns service discovery JSON.
- `http://localhost:8080/jaeger/ui/api/traces?service=frontend&limit=1` returns live frontend trace JSON.
- Trace flow is validated end-to-end, but Jaeger logs still show an internal `localhost:4317` connection failure.
- OTLP HTTP `GET` on `/otlp-http/v1/traces` returns `405 Method Not Allowed`, which is expected for that endpoint.

## Readiness gating coverage
- The current audit primarily validates end-to-end trace flow and Jaeger query API reachability.
- It does not yet fully verify the INC-3 requirement that spans record service readiness timing and readiness gating behavior.
- Local Compose has partial readiness gating: `otel-collector` waits for `opensearch` health, but `jaeger` is only configured with `condition: service_started`.
- The audit should be expanded to explicitly confirm whether startup readiness is captured in spans and whether service-ready events prevent 503-level failures.

## Why containers must be running
A member of the team have tried to audit without explicitly composing the container stack. However, it is later known that it is much more intuitive to audit with containers running,
This audit depends on the Compose services running because:
- The frontend exports traces to a local OTLP endpoint exposed by the Envoy proxy.
- The collector must be active to receive OTLP traffic and export traces to Jaeger.
- Jaeger must be running to expose the query API and return actual stored trace data.
- The probe commands used in this audit hit live container endpoints, not static source code alone.

## What we started with
1. Started the local stack under `techx-corp-platform`.
2. Ensured `frontend-proxy`, `otel-collector`, and `jaeger` containers were running.
3. Confirmed the environment variables from `techx-corp-platform/.env` were available to the containers.

## Runtime verification steps
### Step 1: Confirm containers and network
- Confirm the Compose stack is running: `docker compose ps`.
- Verify the key services are up: `frontend-proxy`, `otel-collector`, `jaeger`.
- Ensure the internal Compose network is available so `frontend-proxy` can reach `otel-collector` and the collector can reach `jaeger`.

### Step 2: Browser exporter and proxy route
- The browser front-end sets `NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` from `.env`.
- The value is `http://localhost:8080/otlp-http/v1/traces` for the local stack.
- Envoy proxy config in `src/frontend-proxy/envoy.tmpl.yaml` routes `/otlp-http/` to the collector at `otel-collector:4318`.
- This confirms browser traces are sent through `frontend-proxy` rather than directly to the collector.

### Step 3: Collector pipeline
- `src/otel-collector/otelcol-config.yml` receives OTLP via HTTP and gRPC.
- The trace pipeline exports to Jaeger at `jaeger:4317`.
- A debug exporter is enabled to surface internal trace processing activity.

### Step 4: Jaeger API and evidence
- Jaeger is configured with `jaeger_query.base_path: /jaeger/ui` in `src/jaeger/config.yml`.
- The correct JSON API endpoints are:
  - `http://localhost:8080/jaeger/ui/api/services`
  - `http://localhost:8080/jaeger/ui/api/traces?service=frontend&limit=1`
- The UI page path `http://localhost:8080/jaeger/api/...` is not the API payload path; it serves the Jaeger UI page.
- Verified evidence:
  - `GET /jaeger/ui/api/services` returns JSON with service names including `frontend`.
  - `GET /jaeger/ui/api/traces?service=frontend&limit=1` returns trace JSON.
  - The returned trace includes frontend spans and backend spans such as `oteldemo.ProductCatalogService/GetProduct`.

### Live Jaeger evidence
- `docker compose ps jaeger` reports the `jaeger` container is up and mapped to host ports `65510->16686` and `65511->4317`.
- `GET /jaeger/ui/api/services` returned 18 services:
  - `currency`, `shipping`, `frontend`, `load-generator`, `product-catalog`, `checkout`, `recommendation`, `quote`, `payment`, `product-reviews`, `cart`, `image-provider`, `email`, `flagd`, `accounting`, `fraud-detection`, `ad`, `frontend-proxy`.
- `GET /jaeger/ui/api/traces?service=frontend&limit=1` returned a trace with:
  - `traceID`: `59de7b155aa6525d2e309107600a5708`
  - spans including:
    - `grpc.oteldemo.ProductCatalogService/GetProduct`
    - `GET /api/products/{productId}`
    - `GET`
    - `executing api route (pages) /api/products/[productId]/index`
- The trace metadata shows Node.js frontend service spans and gRPC backend spans from `product-catalog`.

### Jaeger log evidence
- The live Jaeger logs still show repeated internal gRPC connect failures to `127.0.0.1:4317` and `[::1]:4317`.
- The relevant message pattern is:
  - `grpc: addrConn.createTransport failed to connect to {Addr: "127.0.0.1:4317" ...} connection refused`
  - `grpc: addrConn.createTransport failed to connect to {Addr: "[::1]:4317" ...} connection refused`
  - `traces export: exporter export timeout: rpc error: code = Unavailable desc = connection error: desc = "transport: Error while dialing: dial tcp ... connect: connection refused"`
- This confirms Jaeger is alive and serving query APIs, while still reporting an internal exporter host mismatch.

### Step 5: OTLP endpoint behavior
- `GET http://localhost:8080/otlp-http/v1/traces` returns `405 Method Not Allowed`.
- This is expected because the OTLP trace endpoint requires POST requests for trace payloads.
- The 405 response is not evidence that tracing is broken.

## Findings
- The browser → frontend-proxy → collector → Jaeger trace flow is functioning.
- The browser exporter endpoint is correctly injected and routed through Envoy.
- Jaeger query API is reachable at `/jaeger/ui/api/` and returns valid JSON.
- `HTTP 405` on OTLP GET is normal for that endpoint.

## Issue discovered
- Jaeger logs show repeated `connection refused` to `127.0.0.1:4317`.
- That indicates Jaeger or one of its internal exporters is attempting to connect to localhost instead of the container hostname `jaeger`.
- This likely points to a configuration mismatch in `src/jaeger/config.yml` or a runtime env var override.

## Recommended test procedure
1. Start the Compose stack in `techx-corp-platform`.
2. Confirm service health:
   - `docker compose ps`
3. Verify proxy routing and collector reachability:
   - `curl -I http://localhost:8080/otlp-http/v1/traces`
   - `docker compose exec frontend-proxy curl -I http://otel-collector:4318/v1/traces`
4. Confirm Jaeger query API:
   - `curl -s http://localhost:8080/jaeger/ui/api/services | jq '.'`
   - `curl -s 'http://localhost:8080/jaeger/ui/api/traces?service=frontend&limit=1' | jq '.'`
5. Inspect Jaeger logs for exporter errors:
   - `docker compose logs jaeger | grep '127.0.0.1:4317'`
6. If needed, reproduce a trace by browsing the app and checking Jaeger for the new trace.

## Recommendations
- Keep the current browser/Envoy/collector/Jaeger flow because it is already validated.
- Fix the Jaeger internal exporter host mismatch to remove the `localhost:4317` connection errors.
- Add an automated health check for:
  - `http://localhost:8080/jaeger/ui/api/services`
  - `http://localhost:8080/otlp-http/v1/traces`
- Document the correct Jaeger API endpoints and the expected `405` response for OTLP GET.

## Notes
- This audit applies specifically to the local Docker Compose environment.
- Similar Helm or Kubernetes deployments should be reviewed separately for equivalent OTLP and Jaeger path behavior.
- The OTLP `405` response is a normal / protocol-level endpoint behavior, not a trace storage failure.
