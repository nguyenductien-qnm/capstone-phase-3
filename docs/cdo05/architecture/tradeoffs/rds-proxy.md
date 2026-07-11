# Architecture Trade-off: RDS Proxy for runtime database traffic

## Quyết định của nhóm

Nhóm quyết định để application runtime traffic đi qua **RDS Proxy** trước khi tới RDS PostgreSQL.

Lý do chính: hệ thống có failure mode đã biết là cạn database connection, nhiều service cùng dùng PostgreSQL, và khi scale/restart hàng loạt thì connection spike dễ đập thẳng vào RDS. RDS Proxy tạo một lớp bảo vệ tập trung trước database cho runtime traffic.

Tradeoff nhóm chấp nhận:

- Tăng chi phí AWS và thêm một network hop nhỏ.
- Thêm endpoint, security group, Secrets Manager integration và proxy metrics cần theo dõi.
- Session pinning có thể làm giảm hiệu quả multiplexing.
- App-side pooling vẫn bắt buộc; RDS Proxy không sửa được toàn bộ lỗi connection management trong app.

Phương án không chọn làm mặc định:

- **App services kết nối thẳng tới RDS**: chỉ dùng cho migration/admin path có kiểm soát, không dùng làm runtime path bình thường.

Nhóm sẽ xem xét lại nếu traffic nhỏ và ổn định, application-side pool đã được tune tốt, session pinning quá cao, hoặc cost/latency của proxy không tương xứng với lợi ích reliability.

## Bối cảnh

RDS đã được chọn để tách PostgreSQL khỏi EKS. Câu hỏi còn lại là app nên kết nối thẳng tới RDS hay đi qua proxy.

Workload hiện tại có các tín hiệu khiến RDS Proxy đáng chọn:

- Đã từng có incident cạn database connection.
- Nhiều service cùng dùng PostgreSQL.
- `product-reviews` có pattern mở PostgreSQL connection theo từng database call.
- Scale pod hoặc restart hàng loạt có thể tạo connection spike.
- Checkout là flow quan trọng hơn các tính năng best-effort.

## Các phương án

| Phương án | Vai trò | Kết luận |
|---|---|---|
| Kết nối thẳng RDS | App pool kết nối trực tiếp tới database endpoint. | Không chọn cho runtime default. |
| RDS Proxy -> RDS | App kết nối tới proxy endpoint, proxy quản lý backend connections. | Chọn cho runtime traffic. |

## Tradeoff chính

| Khía cạnh | Kết nối thẳng RDS | Đi qua RDS Proxy |
|---|---|---|
| Reliability | Đơn giản hơn nhưng connection spike đập thẳng vào DB. | Hấp thụ connection churn và giảm rủi ro connection storm. |
| Failover | App phải tự xử lý DNS/broken connection/retry tốt. | Proxy có thể giảm tác động failover bằng quản lý backend connections. |
| Chi phí | Rẻ hơn vì không có proxy. | Tốn thêm RDS Proxy capacity. |
| Latency | Ít một hop. | Thêm một hop nhỏ, chấp nhận được nếu ưu tiên reliability. |
| Vận hành | Ít resource và metric hơn. | Thêm endpoint, SG, secret, metric và pinning behavior. |
| Debug | Request path ngắn hơn. | Nhiều thành phần hơn nhưng nhìn rõ client vs database connection pressure. |
| Failure mode | Pool app cấu hình kém có thể làm cạn connection RDS. | Session pinning có thể làm multiplexing kém hiệu quả. |

## Rủi ro session pinning

RDS Proxy hiệu quả nhất khi multiplex được nhiều client connections lên ít database connections hơn. Một số hành vi PostgreSQL có thể pin client session vào một backend database connection:

- Session-level `SET`.
- Temporary table.
- Long-lived transaction.
- Cursor.
- Advisory lock.
- Prepared statement hoặc driver behavior gây pinning.

Nếu pinning cao, proxy vẫn có thể giúp connection admission và failover behavior, nhưng lợi ích giảm database connections sẽ thấp hơn.

## Guardrail vận hành

- Application pods kết nối tới RDS Proxy endpoint, không kết nối thẳng tới RDS instance endpoint trong runtime bình thường.
- Security group enforce app -> RDS Proxy -> RDS qua port `5432`.
- Không có đường runtime bình thường từ app pods đi thẳng tới RDS.
- Database credentials nằm trong AWS Secrets Manager.
- RDS và RDS Proxy nằm trong private subnet, không public.
- Connection pool phía app phải có limit explicit và được document.
- Có connection timeout và statement timeout rõ.

## Rollback và điều kiện đổi quyết định

Rollback kỹ thuật là trỏ app về RDS endpoint trực tiếp. Chỉ dùng rollback này nếu proxy gây sự cố rõ ràng và app pool đã được giới hạn để không tạo connection storm.

Quyết định nên đổi nếu validation cho thấy RDS Proxy không giảm được áp lực connection, session pinning quá cao, hoặc latency/cost vượt ngưỡng nhóm chấp nhận.

## Verification

Chạy load test cho hai đường:

1. App services -> RDS trực tiếp.
2. App services -> RDS Proxy -> RDS.

Đo các chỉ số:

- Checkout success rate.
- Storefront p95 latency.
- Latency của `product-catalog` và `product-reviews`.
- RDS `DatabaseConnections`, CPU và memory.
- RDS Proxy `ClientConnections`, `DatabaseConnections` và `DatabaseConnectionsBorrowLatency`.
- Metric session pinning của RDS Proxy.

Chấp nhận RDS Proxy nếu nó giảm áp lực database connection hoặc cải thiện behavior khi restart, scale-out hoặc failover test mà không gây latency/cost vượt ngưỡng.
