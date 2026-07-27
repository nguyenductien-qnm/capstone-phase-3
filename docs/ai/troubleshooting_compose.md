# Troubleshooting Local Docker Compose (AIE)

Tài liệu này ghi nhận lại các lỗi đã gặp phải trong quá trình khởi chạy môi trường local (chạy lệnh `docker-compose up -d`) và cách khắc phục để đảm bảo lần sau khởi động không gặp trục trặc.

## 1. Lỗi Build Image: "failed to parse platform"
- **Dấu hiệu lỗi:** Khi chạy lệnh compose, tiến trình Build bị dừng lại giữa chừng và ném ra lỗi: 
  `failed to parse platform : "" is an invalid OS component of "": OSAndVersion specifier component must match ... invalid argument`
- **Nguyên nhân:** Do các `Dockerfile` trong dự án có sử dụng biến `${BUILDPLATFORM}`, nhưng môi trường Docker trên máy chưa được bật BuildKit, hoặc biến này chưa được truyền vào context của Docker Compose. Điều này khiến một số service bị tịt không build và start được (như `shopping-copilot`, `frontend`, `cart`,...).
- **Cách khắc phục:** Luôn chạy lệnh xuất biến môi trường này trước khi compose:
  ```bash
  export DOCKER_BUILDKIT=1
  export BUILDPLATFORM=linux/amd64  # (hoặc linux/arm64 nếu dùng chip Apple Silicon M1/M2/M3)
  docker compose up -d
  ```

## 2. Lỗi Crash Container: `product-reviews` (ParamValidationError: RoleArn)
- **Dấu hiệu lỗi:** Khi kiểm tra lệnh `docker ps`, service `product-reviews` liên tục ở trạng thái `Restarting`. Xem log (`docker logs product-reviews`) thì thấy lỗi:
  ```
  botocore.exceptions.ParamValidationError: Parameter validation failed:
  Invalid length for parameter RoleArn, value: 15, valid min length: 20
  ```
- **Nguyên nhân:** Trong file `.env` ở thư mục gốc có dòng `BEDROCK_AWS_ROLE_ARN="<your-role-arn>"`. Mặc định khi chạy local, hệ thống AI sẽ đọc biến này. Do giá trị placeholder chỉ có 15 ký tự (AWS yêu cầu >= 20 ký tự chuẩn định dạng ARN), thư viện `boto3` đã bị crash ngay từ lúc khởi động khi cố gọi hàm `sts.assume_role`.
- **Cách khắc phục:** Khi dev ở môi trường local, ứng dụng sẽ dùng trực tiếp cấu hình AWS Credentials trên máy chứ không cần cơ chế Assume Role. Hãy mở file `.env` và comment dòng đó lại:
  ```env
  # BEDROCK_AWS_ROLE_ARN="<your-role-arn>"
  ```
  Sau đó khởi động lại service: `docker compose up -d product-reviews`.

---
*Lưu ý: Luôn kiểm tra lại `docker ps` sau khi compose để đảm bảo tất cả các container cốt lõi (frontend, shopping-copilot, product-reviews, v.v.) đều ở trạng thái `Up` và `Healthy`.*
