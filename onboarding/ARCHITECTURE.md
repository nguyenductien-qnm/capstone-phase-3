# Kiến trúc - TechX Corp Platform

Tài liệu onboarding. Đọc cái này để hiểu bạn đang tiếp quản cái gì trước khi đụng vào.

## Tổng quan

Storefront thương mại điện tử, kiến trúc **microservice polyglot** trên Kubernetes. Khách vào web → duyệt sản phẩm → xem review (có tóm tắt AI) → thêm giỏ → thanh toán. Phía sau là ~18 service viết bằng nhiều ngôn ngữ, giao tiếp chủ yếu qua **gRPC**, một hàng đợi **Kafka** cho luồng bất đồng bộ, và đầy đủ observability (metrics, logs, traces, dashboards).

Mọi request vào qua một cổng duy nhất: **frontend-proxy (Envoy)** ở port `8080`.

## Bản đồ service

| Service | Vai trò | Ngôn ngữ | Phụ thuộc chính |
|---|---|---|---|
| `frontend-proxy` | Envoy - cổng vào duy nhất (:8080), route tới frontend + observability UI | Envoy | tất cả |
| `frontend` | Storefront (web) | TypeScript / Next.js | các service gRPC bên dưới |
| `product-catalog` | Danh mục sản phẩm: list / get / **search** | Go | postgresql |
| `product-reviews` | Review sản phẩm + **tóm tắt AI** + hỏi-đáp AI | Python | postgresql, llm |
| `llm` | Backend AI (sinh tóm tắt review / trả lời) | Python | (mock, hoặc LLM thật khi AIO cắm) |
| `cart` | Giỏ hàng | .NET / C# | valkey-cart |
| `checkout` | Điều phối đặt hàng (gom cart, giá, ship, payment, email) | Go | cart, product-catalog, currency, shipping, quote, payment, email, kafka |
| `payment` | Xử lý thanh toán | Node.js | - |
| `shipping` | Tính phí + theo dõi ship | Rust | quote |
| `quote` | Báo giá ship | PHP | - |
| `currency` | Quy đổi tiền tệ | C++ | - |
| `email` | Gửi email xác nhận | Ruby | - |
| `recommendation` | Gợi ý sản phẩm | Python | product-catalog |
| `ad` | Quảng cáo theo ngữ cảnh | Java | - |
| `accounting` | Ghi sổ đơn hàng (consumer Kafka) | .NET / C# | kafka, postgresql |
| `fraud-detection` | Phát hiện gian lận (consumer Kafka) | Kotlin / JVM | kafka |
| `image-provider` | Phục vụ ảnh tĩnh | Nginx | - |
| `load-generator` | Sinh tải mô phỏng người dùng | Python / Locust | frontend-proxy |
| `flagd` | Feature flags (điều khiển nhánh hành vi) | flagd | nguồn cấu hình (xem RULES) |

## Các luồng chính (request flow)

- **Duyệt sản phẩm:** user → frontend → `product-catalog` (list/search/get) + `recommendation` + `ad`.
- **Trang sản phẩm - review + AI:** frontend → `product-reviews` → đọc review từ `postgresql` **và** gọi `llm` để sinh **tóm tắt AI**. Đây là tính năng AI trọng tâm của sản phẩm.
- **Giỏ hàng:** frontend → `cart` → `valkey-cart` (lưu state giỏ).
- **Đặt hàng:** frontend → `checkout` → gọi cart + product-catalog + currency + shipping/quote + payment + email, rồi **publish sự kiện đơn hàng lên Kafka**.
- **Sau đặt hàng (bất đồng bộ):** `accounting` và `fraud-detection` **consume** sự kiện từ Kafka.

## Data stores

| Store | Dùng bởi | Ghi chú |
|---|---|---|
| `postgresql` | product-catalog, product-reviews, accounting | DB quan hệ chính |
| `valkey-cart` | cart | Key-value (Redis-compatible) cho giỏ hàng |
| `kafka` | checkout (producer) → accounting, fraud-detection (consumer) | Hàng đợi luồng đơn hàng |

> Đây là baseline **in-cluster** (postgres/valkey/kafka chạy như pod). Việc chuyển sang managed (RDS / ElastiCache / MSK) là một cải tiến có thể được yêu cầu trong lúc vận hành.

## Observability (đã có sẵn)

Mọi service phát telemetry OpenTelemetry → **collector** → phân phối tới:
- **Prometheus** - metrics
- **Jaeger** - traces (distributed tracing)
- **OpenSearch** - logs
- **Grafana** - dashboards (điểm nhìn tổng hợp)

Truy cập qua `frontend-proxy`: mở `http://<host>:8080/grafana/`, `/jaeger/ui`, `/loadgen/`. Đây là công cụ chính để bạn hiểu hệ thống đang khỏe hay yếu ở đâu.

## Cách khám phá nhanh (khi hệ thống đã chạy)

1. Mở storefront `:8080` - đặt thử một đơn từ đầu tới cuối để thấy luồng thật.
2. Mở Grafana - xem dashboard service health, latency, error rate.
3. Mở Jaeger - trace một request checkout để thấy nó đi qua service nào.
4. `kubectl -n <ns> get pods` + đọc `values.yaml` của chart - hiểu cấu hình hiện tại (replicas, resources, probes, security...). Nhiều thứ ở đây **chưa tối ưu** - tìm ra chúng là việc của bạn.

Xem thêm: [SLO.md](SLO.md) (mục tiêu phải giữ) · [BUDGET.md](BUDGET.md) (ràng buộc chi phí) · [INCIDENT_HISTORY.md](INCIDENT_HISTORY.md) (sự cố đã từng xảy ra).
