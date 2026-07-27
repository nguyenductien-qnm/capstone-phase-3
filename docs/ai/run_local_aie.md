# Hướng dẫn Khởi chạy Môi trường Local cho AI Services (AIE)

Tài liệu này cung cấp các bước **chuẩn nhất** để khởi chạy thành công cụm dịch vụ AI (bao gồm LLM, Copilot, Reviews) cùng với hệ thống Tracing và giao diện người dùng trên môi trường Local thông qua Docker Compose.

---

## 1. Chuẩn bị Môi trường (Bắt buộc)

Do dự án sử dụng tính năng đa nền tảng (multi-platform) trong `Dockerfile`, bạn bắt buộc phải có plugin `docker-buildx` cài đặt sẵn trên máy. Nếu chưa có, bạn có thể cài đặt bằng lệnh:

```bash
mkdir -p ~/.docker/cli-plugins/
curl -L https://github.com/docker/buildx/releases/download/v0.17.0/buildx-v0.17.0.linux-amd64 -o ~/.docker/cli-plugins/docker-buildx
chmod +x ~/.docker/cli-plugins/docker-buildx
```

## 2. Xử lý Lỗi AWS Role (Chỉ dành cho Local)

Service `product-reviews` sử dụng AWS Bedrock. Mặc định trong file `.env` cấu hình một giá trị giả (`<your-role-arn>`) cho biến `BEDROCK_AWS_ROLE_ARN`. Giá trị giả này sẽ làm crash ứng dụng ngay khi khởi động vì sai định dạng ARN.

Khi chạy ở Local, hệ thống sẽ tự động dùng quyền từ AWS Profile trên máy tính của bạn, do đó tính năng Assume Role là không cần thiết. Hãy comment biến này lại bằng cách mở file `.env` hoặc chạy lệnh:

```bash
sed -i 's/^BEDROCK_AWS_ROLE_ARN=.*/#BEDROCK_AWS_ROLE_ARN=/' .env
```

## 3. Lệnh Khởi động Chuẩn (AIE Case)

Hệ thống có rất nhiều service, nhưng để test và debug riêng mảng AI (kèm theo giao diện UI và hệ thống Tracing ngầm) **mà không cần phải sửa bất kỳ Dockerfile nào**, bạn chỉ cần gõ chính xác tổ hợp lệnh sau (Đã tự động override biến `$TARGETARCH` cho các service .NET và bật BuildKit):

```bash
BUILDPLATFORM=linux/amd64 TARGETARCH=x64 DOCKER_BUILDKIT=1 docker compose up -d \
  product-catalog \
  product-reviews \
  shopping-copilot \
  llm \
  ml-guard \
  currency \
  shipping \
  quote \
  cart \
  recommendation \
  postgresql \
  valkey-cart \
  flagd \
  otel-collector \
  jaeger \
  frontend \
  frontend-proxy
```

### 💡 Giải thích các nhóm dịch vụ:
- **Core AI:** `shopping-copilot`, `product-reviews`, `product-catalog`, `llm` (Mock LLM), `ml-guard`.
- **Dependencies (Cho Copilot Tool):** `currency` (Quy đổi tiền tệ), `shipping` & `quote` (Vận chuyển), `cart`, `recommendation`.
- **Infrastructure:** `postgresql` (chứa db pgvector), `valkey-cart` (Cache), `flagd` (Feature Flags).
- **Tracing & UI:** `otel-collector` (Thu thập vết), `jaeger` (Xem Tracing), `frontend` & `frontend-proxy` (Giao diện web).

## 4. Kiểm tra Trạng thái

Sau khi lệnh hoàn thành (có thể mất vài phút để build), hãy chạy lệnh:

```bash
docker ps
```

Đảm bảo tất cả các container trên đều ở trạng thái `Up` (và `Healthy`). Nếu có container nào bị `Restarting`, hãy xem log của nó (VD: `docker logs frontend-proxy`) để xử lý thêm.

## 5. Các lỗi phổ biến thường gặp & Cách khắc phục

### 5.1. Lỗi Build x64/arm64 trên service C++ (currency) hoặc .NET (cart)
- **Triệu chứng:** Khi chạy `docker compose up`, các service như `cart` (báo lỗi không thể restore package) hoặc `currency` (lỗi cmake) văng lỗi liên quan đến Target Architecture. 
- **Nguyên nhân:** Do `Dockerfile` sử dụng các tham số như `$TARGETARCH` được inject ngầm bởi BuildKit, nhưng Docker ở local phiên bản cũ hoặc plugin buildx không truyền qua được.
- **Khắc phục:** 
  1. Cài đặt `docker-buildx` bản mới (v0.17.0+).
  2. Bắt buộc truyền các tham số cấu hình khi chạy lệnh compose: `BUILDPLATFORM=linux/amd64 TARGETARCH=x64 DOCKER_BUILDKIT=1 docker compose up -d ...`

### 5.2. Lỗi frontend-proxy sập liên tục (Restarting) do lỗi cấu hình Envoy
- **Triệu chứng:** Container `frontend-proxy` (Envoy) liên tục restart. Chạy `docker logs frontend-proxy` thấy dòng lỗi `SocketAddressValidationError.Address: value length must be at least 1 characters`.
- **Nguyên nhân:** File `techx-corp-platform/.env` mặc định có cấu hình thiếu biến `SHOPPING_COPILOT_HOST` và `SHOPPING_COPILOT_PORT`. Mặc dù đã có biến `SHOPPING_COPILOT_ADDR=shopping-copilot:3552`, nhưng template config của Envoy (`envoy.tmpl.yaml`) lại fetch riêng 2 biến HOST và PORT. Nếu thiếu, Envoy nhận một giá trị rỗng cho trường address và crash.
- **Khắc phục:** Mở file `.env`, tìm dòng định nghĩa `SHOPPING_COPILOT_ADDR` và thêm 2 dòng sau vào ngay bên dưới:
  ```env
  SHOPPING_COPILOT_HOST=shopping-copilot
  SHOPPING_COPILOT_PORT=3552
  ```
  Sau đó, restart lại riêng `frontend-proxy` với lệnh:
  ```bash
  docker compose up -d --no-deps frontend-proxy
  ```
