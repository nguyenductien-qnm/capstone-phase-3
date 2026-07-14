# Postmortem / COE - INC-20260714-FLAGD - TF1

## Tóm tắt

Hệ thống bị thử nghiệm sự cố (tấn công giả lập) thông qua việc thay đổi cấu hình flagd trung tâm từ BTC, đi kèm việc khởi chạy các pod curl độc lập để kích hoạt lỗi. Sự cố gây lỗi diện rộng tại luồng Checkout/Payment do lỗi thanh toán và nghẽn hàng đợi Kafka đồng bộ, quá tải CPU khiến frontend scale-up, và dịch vụ giám sát Grafana bị sập (OOMKilled) do lượng dữ liệu giám sát tăng đột biến.

## Mức độ & ảnh hưởng khách

- **Severity**: Major (Ảnh hưởng trực tiếp đến tính sẵn sàng của luồng thanh toán và hệ thống giám sát).
- **Luồng bị ảnh hưởng**: Checkout / Payment / Kafka Queue / Observability (Grafana).
- **SLO bị ảnh hưởng**:
  - Tỷ lệ thanh toán thành công giảm mạnh trong thời gian tải (không đạt SLO checkout ≥ 99%).
  - Độ trễ phản hồi (storefront p95) tăng cao do luồng Checkout bị nghẽn đồng bộ tại bước ghi tin nhắn sang Kafka.
- **Thời gian kéo dài**: ~12 phút (từ 14:30 đến 14:42 ngày 14/07/2026).
- **Phạm vi ảnh hưởng**: Toàn bộ khách hàng thực hiện checkout và hệ thống giám sát của đội vận hành trong thời gian diễn ra sự cố.

## Timeline

| Thời điểm | Sự kiện (phát hiện / chẩn đoán / hành động / phục hồi)                                                                                                                                                                                                      |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **14:30** | BTC kích hoạt các flag sự cố trên server flagd trung tâm (`paymentFailure`, `kafkaQueueProblems`, `loadGeneratorFloodHomepage`, `emailMemoryLeak`...). Pod test `pf-19276` khởi chạy để giả lập lỗi thanh toán. Đồng thời hàng đợi Kafka bị spam gây nghẽn. |
| **14:31** | Pod test `mx-6980` chạy test rò rỉ bộ nhớ email. Pod `rt-15604` chạy test probe/rate limit. Phát hiện lỗi giao dịch hàng loạt từ log frontend.                                                                                                              |
| **14:32** | Pod test `rt1-17507` và `rt2-17507` chạy test. Horizontal Pod Autoscaler (HPA) tự động scale frontend từ 2 lên 3 replicas do CPU vượt ngưỡng chịu tải.                                                                                                      |
| **14:33** | Pod test `fr-22647` chạy giả lập flood homepage.                                                                                                                                                                                                            |
| **14:36** | Lượng log/metric sinh ra quá lớn từ đợt flood khiến Grafana vượt quá giới hạn tài nguyên bộ nhớ (`limits.memory: 300Mi`), bị **OOMKilled** và tự động khởi động lại 3 lần.                                                                                  |
| **14:37** | Lượng tải từ load-generator giảm xuống, HPA tự động scale down frontend từ 3 về lại 2 replicas.                                                                                                                                                             |
| **14:42** | BTC đưa cấu hình flagd trung tâm về mặc định (`off`). Các pod test tự giải phóng. Hệ thống tự phục hồi hoàn toàn.                                                                                                                                           |

## Nguyên nhân gốc

1.  **Lỗi Checkout/Payment**: Flag `paymentFailure` được kích hoạt làm dịch vụ Payment trả về lỗi logic (`Payment request failed. Invalid token. app.loyalty.level=gold`).
2.  **Nghẽn Hàng Đợi Kafka**: Flag `kafkaQueueProblems` làm chậm việc xử lý tin nhắn của consumer (lag spike) và spam tin nhắn gây nghẽn hàng đợi. Vì Checkout gọi `sendToPostProcessor` đồng bộ (blocking), luồng xử lý đơn hàng của Checkout bị treo khi đẩy tin nhắn vào `cs.KafkaProducerClient.Input()` và chờ phản hồi ở kênh `Successes()`, kéo sập SLO về độ trễ.
3.  **Sập Grafana**: Giới hạn bộ nhớ của Grafana quá thấp (`300Mi`), không đủ tài nguyên để Bleve-search index và xử lý dữ liệu OpenSearch/Prometheus đổ về dồn dập trong lúc hệ thống bị flood homepage.
4.  **Frontend delay khi scale**: Do pod frontend mới khởi chạy dưới tải nặng cần thời gian cấu hình và phản hồi, dẫn đến việc startup probe bị từ chối kết nối tạm thời.

## Loại sự cố

- **flagd BTC bơm vào** (sự cố giả lập để kiểm tra độ tin cậy của hệ thống).
- _Hướng xử lý_: Cải tiến hệ thống chịu được lỗi (resilience) qua fallback, retry, async processing và tối ưu hóa tài nguyên (Resource limits).

## Xử lý

- BTC tắt cấu hình sự cố về mặc định. Hệ thống tự phục hồi.
- **MTTD** (Thời gian phát hiện): ~2 phút (từ lúc bắt đầu lỗi đến lúc phát hiện lỗi trong log).
- **MTTR** (Thời gian phục hồi): ~12 phút.

## Việc theo sau

| Việc                                                                                                                                 | Chủ      | Hạn        | ADR liên quan |
| ------------------------------------------------------------------------------------------------------------------------------------ | -------- | ---------- | ------------- |
| Chuyển lời gọi `sendToPostProcessor` (ghi sang Kafka) trong Checkout thành bất đồng bộ (Goroutine) để cô lập lỗi hàng đợi            | CDO team | 15/07/2026 | ADR-PERF-005  |
| Tăng memory limit của Grafana lên `512Mi`/`1Gi` để tránh OOMKilled                                                                   | CDO team | 15/07/2026 | ADR-REL-004   |
| Bổ sung cơ chế Fallback tự động gọi `cs.paymentSvcClient` gốc khi phát hiện lỗi kết nối gRPC đến địa chỉ giả lập `badAddress`        | CDO team | 16/07/2026 | ADR-REL-005   |
| Điều chỉnh cấu hình `startupProbe` cho frontend (tăng `failureThreshold` và `initialDelaySeconds`) để pod khởi động an toàn dưới tải | CDO team | 15/07/2026 | ADR-REL-006   |
| Cấu hình Rate Limiting tại `frontend-proxy` để chặn bớt lưu lượng spam từ load-generator                                             | CDO team | 16/07/2026 | ADR-SEC-003   |

## Ký tên

- On-call team: TF1 Operations Team (CDO09).
- Ngày lập: 14/07/2026.
